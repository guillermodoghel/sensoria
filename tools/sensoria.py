#!/usr/bin/env python3
"""SENSORIA: compile setup.toml + looks/*.toml into WLED config, back up and push the three controllers.

  sensoria.py build                 # -> build/ (presets, palettes, cfg patches, simulator)
  sensoria.py backup [dev ...]      # pull cfg/presets/palettes from the devices -> backups/<date>/
  sensoria.py push [dev ...]        # show what would be sent (dry run)
  sensoria.py push --apply [dev ...]
  sensoria.py status                # who answers, uptime, current preset
  sensoria.py ota [dev] [--apply]   # flash firmware/dist/*.bin over the air (default: sub-orbe-b, to test it first)
  sensoria.py wifi [--apply]        # rename the wifi networks (red.ap → red.ap_propuesto) in a safe order

dev = sub-orbe-a | sub-orbe-b | diana (default: all). B and DIANA live only on SUB ORBE A's AP, so reaching them
means hopping the laptop's wifi to that AP and back; every hop restores the home network on exit.
"""
import argparse, contextlib, copy, datetime, json, math, pathlib, subprocess, sys, time, tomllib, urllib.request, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
WLED_FX = json.loads((ROOT / "data/wled-0.15-effects.json").read_text())
CUSTOM_FX = json.loads((ROOT / "data/sensoria-effects.json").read_text())   # effects of our own firmware
WLED_PAL = json.loads((ROOT / "data/wled-0.15-palettes.json").read_text())
PAL_ALIAS = {"default": 0, "color1": 2, "colors12": 3, "gradient": 4, "colors-only": 5}
GROUPS = ("grandes", "chicos", "diana")


def load(preview=False):
    """Looks and sequences for the controllers. Looks that need our firmware are left out (and the sequence they
    replace is kept) until [firmware] says it is installed; preview=True returns those looks for the simulator."""
    setup = tomllib.loads((ROOT / "setup.toml").read_text())
    data = tomllib.loads((ROOT / "looks" / f"{setup['proyecto']['look_activo']}.toml").read_text())
    fw = {k for k, v in setup.get("firmware", {}).items() if v is True}
    looks = [lk for lk in data["look"] if lk.get("requiere_firmware", None) in fw | {None}]
    replaced = {lk["id"] for lk in looks if lk.get("requiere_firmware")}
    sequences = [sq for sq in data.get("secuencia", []) if sq.get("reemplazo_firmware") not in replaced]
    if preview:
        return [lk for lk in data["look"] if lk.get("requiere_firmware") and lk not in looks]
    return setup, looks, sequences


# ------------------------------------------------------------------ compile

class Compiler:
    def __init__(self, setup):
        self.s = setup
        self.rings = sorted(setup["anillo"], key=lambda r: r["seg"])
        start = 0
        for r in self.rings:
            r["start"], r["stop"] = start, start + r["leds"]
            start += r["leds"]
        self.total = start
        self.colors = setup["colores"]
        self.custom = {p["nombre"]: 255 - i for i, p in enumerate(setup["paleta"])}
        self.orbit_rings = [r for r in self.rings if r["grupo"] != "diana"]
        self.diana_rings = [r for r in self.rings if r["grupo"] == "diana"]

    def group(self, name):
        if name == "puntitos":
            return self.orbit_rings, self.s["segmentos"]["puntitos_orbitas"]
        if name == "puntitos_diana":
            return self.diana_rings, self.s["segmentos"]["puntitos_diana"]
        return [r for r in self.rings if r["grupo"] == name], None

    def color(self, c):
        if isinstance(c, str):
            if c not in self.colors:
                sys.exit(f"color desconocido: {c}")
            return list(self.colors[c])
        return list(c)

    def cols(self, c):
        # "rojo" -> [rojo, negro, negro]; ["azul","celeste","azul"] -> three colors. col[1] is the background
        # most WLED fades go toward, so it stays black unless a look sets it on purpose.
        if isinstance(c, str):
            return [self.color(c), [0, 0, 0], [0, 0, 0]]
        out = [self.color(x) for x in c]
        return (out + [[0, 0, 0]] * 3)[:3]

    def pal(self, p):
        if isinstance(p, int):
            return p
        if p in self.custom:
            return self.custom[p]
        if p in PAL_ALIAS:
            return PAL_ALIAS[p]
        low = [x.lower() for x in WLED_PAL]
        if p.lower() in low:
            return low.index(p.lower())
        sys.exit(f"paleta desconocida: {p}")

    @staticmethod
    def fx(name):
        if isinstance(name, int):
            return name
        if name in CUSTOM_FX:
            return CUSTOM_FX[name]
        if name not in WLED_FX:
            sys.exit(f"efecto desconocido: {name}")
        return WLED_FX.index(name)

    def segment(self, sid, ring, p, look, name):
        return {"id": sid, "start": ring["start"], "stop": ring["stop"], "grp": 1, "spc": 0, "of": 0, "on": True,
                "frz": False, "bri": p.get("opacidad", 255), "cct": 127, "set": 0, "n": name,
                "col": self.cols(p.get("color", look.get("color", "rojo"))),
                "fx": self.fx(p.get("fx", "Solid")), "sx": p.get("sx", 128), "ix": p.get("ix", 128),
                "pal": self.pal(p.get("paleta", look.get("paleta", "color1"))),
                "c1": p.get("c1", 128), "c2": p.get("c2", 128), "c3": p.get("c3", 16), "sel": False, "rev": p.get("rev", False), "mi": False,
                "o1": False, "o2": p.get("o2", False), "o3": False, "si": 0, "m12": 0}

    def preset(self, look):
        segs = {}
        for gname in GROUPS + ("puntitos", "puntitos_diana"):
            if gname not in look:
                continue
            spec = look[gname]
            rings, overlay_base = self.group(gname)
            for k, ring in enumerate(rings):
                p = {key: (v[k] if isinstance(v, list) and key != "color" else v)
                     for key, v in spec.items() if key != "colores"}
                if "colores" in spec:          # one color per ring
                    p["color"] = spec["colores"][k]
                if overlay_base is None:
                    sid, name = ring["seg"], ring["nombre"]
                else:
                    idx = (self.orbit_rings if gname == "puntitos" else self.diana_rings).index(ring)
                    sid, name = overlay_base + idx, "·" + ring["nombre"]
                    p["o2"] = True
                segs[sid] = self.segment(sid, ring, p, look, name)
        for r in self.rings:
            if r["seg"] not in segs:
                sys.exit(f"look {look['id']} no define el anillo {r['nombre']}")
        seg_list = [segs[i] for i in sorted(segs)] + [
            {"id": i, "stop": 0} for i in range(self.s["segmentos"]["max"] + 1) if i not in segs]
        return {"n": look["nombre"], "on": True, "bri": look.get("brillo", self.s["proyecto"]["brillo"]),
                "transition": 7, "mainseg": 0, "seg": seg_list}

    def sequence(self, sq):
        """Expand a [[secuencia]] into step presets + a playlist that walks them."""
        n = math.lcm(len(sq["orbe"]), len(sq["diana"]))
        steps, presets = [], {}
        for k in range(n):
            white = {sq["orbe"][k % len(sq["orbe"])], sq["diana"][k % len(sq["diana"])]}
            look = {"id": sq["preset_base"] + k, "nombre": f"{sq['nombre']} {k + 1}", "paleta": "color1",
                    "puntitos": sq["fondo"], "puntitos_diana": sq["fondo_diana"]}
            for g in GROUPS:
                rings, _ = self.group(g)
                look[g] = {"fx": "Solid", "colores": [sq["blanco"] if r["nombre"] in white else "negro" for r in rings]}
            presets[str(look["id"])] = self.preset(look)
            steps.append(look["id"])
        presets[str(sq["id"])] = {"n": sq["nombre"], "on": True, "playlist": {
            "ps": steps, "dur": [round(sq["paso_s"] * 10)] * n, "transition": [0] * n, "repeat": 0, "end": 0, "r": False}}
        return presets

    def presets(self, looks, sequences=()):
        """All presets: looks, sequence steps, the main playlist and the boot playlist.
        A playlist can't contain another playlist, so a sequence joins the main one by chaining: the main playlist
        runs once and ends on the sequence, which repeats for its duration and ends back on the main playlist."""
        out = {"0": {}}
        for lk in looks:
            out[str(lk["id"])] = self.preset(lk)
        pl = self.s["proyecto"]["playlist"]
        chain = []
        for sq in sequences:
            seq = self.sequence(sq)
            body = seq[str(sq["id"])]["playlist"]
            if sq.get("duracion_s"):
                cycle = sum(body["dur"]) / 10
                body["repeat"] = max(1, round(sq["duracion_s"] / cycle))
                chain.append(sq["id"])
            out.update(seq)
        playable = [lk for lk in looks if lk.get("playlist", True) and lk["id"] != self.s["proyecto"]["arranque"]["test"]]
        ids = [lk["id"] for lk in playable]
        out[str(pl["id"])] = {"n": pl["nombre"], "on": True, "playlist": {
            "ps": ids, "dur": [lk.get("duracion_s", pl["duracion_s"]) * 10 for lk in playable],
            "transition": [pl["transicion_s"] * 10] * len(ids), "repeat": 1 if chain else 0,
            "end": chain[0] if chain else 0, "r": False}}
        for i, sid in enumerate(chain):
            out[str(sid)]["playlist"]["end"] = chain[i + 1] if i + 1 < len(chain) else pl["id"]
        ar = self.s["proyecto"]["arranque"]
        out[str(ar["id"])] = {"n": "Arranque", "on": True, "playlist": {
            "ps": [ar["test"]], "dur": [ar["segundos"] * 10], "transition": [0], "repeat": 1, "end": pl["id"], "r": False}}
        return out

    def palettes(self):
        out = {}
        for i, p in enumerate(self.s["paleta"]):
            a, b = (self.color(c) for c in p["colores"])
            out[f"palette{i}.json"] = {"palette": [0, *a, 120, *a, 136, *b, 255, *b]}
        return out

    def cfg_patches(self):
        pr, au, c = self.s["proyecto"], self.s["audio"], self.s["controlador"]
        diana_abl = {str(r["leds"]): r["abl_ma"] for r in self.diana_rings}
        return {
            "sub-orbe-a": {"id": {"name": c["sub-orbe-a"]["nombre"], "mdns": c["sub-orbe-a"]["mdns"]},
                          "def": {"ps": pr["arranque"]["id"], "on": True, "bri": pr["brillo"]},
                          "um": {"AudioReactive": {"config": {"squelch": au["squelch"], "gain": au["ganancia"], "AGC": au["agc"]}}}},
            "sub-orbe-b": {"id": {"name": c["sub-orbe-b"]["nombre"], "mdns": c["sub-orbe-b"]["mdns"]}},
            "diana": {"id": {"name": c["diana"]["nombre"], "mdns": c["diana"]["mdns"]},
                      "_abl_por_bus": diana_abl, "_abl_total": c["diana"]["abl_ma"]},
        }


def cmd_build(_args):
    setup, looks, sequences = load()
    comp = Compiler(setup)
    presets = comp.presets(looks, sequences)
    a = BUILD / "sub-orbe-a"
    a.mkdir(parents=True, exist_ok=True)
    (a / "presets.json").write_text(json.dumps(presets, separators=(",", ":")))
    for name, data in comp.palettes().items():
        (a / name).write_text(json.dumps(data))
    for dev, patch in comp.cfg_patches().items():
        (BUILD / dev).mkdir(parents=True, exist_ok=True)
        (BUILD / dev / "cfg.patch.json").write_text(json.dumps(patch, indent=1))
    sim = build_simulator(comp, presets, setup, load(preview=True))
    pl = presets[str(setup["proyecto"]["playlist"]["id"])]["playlist"]["ps"]
    print(f"build/ listo: {len(looks)} looks, {len(sequences)} secuencias, playlist {pl}, {len(comp.palettes())} paletas, {comp.total} LEDs")
    print(f"simulador: {sim}")


def build_simulator(comp, presets, setup, preview=()):
    sim = []
    main_pl, boot = setup["proyecto"]["playlist"]["id"], setup["proyecto"]["arranque"]["id"]
    presets = dict(presets)
    for lk in preview:   # firmware-only looks, shown in the simulator before the firmware is installed
        presets[str(lk["id"])] = comp.preset({**lk, "nombre": lk["nombre"] + " (firmware)"})
    step_ids = {i for k, p in presets.items() if "playlist" in p and int(k) not in (main_pl, boot) for i in p["playlist"]["ps"]}
    for k, p in presets.items():
        if int(k) == boot:
            continue
        if "playlist" in p and int(k) != main_pl:   # a sequence: the simulator walks its steps itself
            sim.append({"id": int(k), "n": p["n"], "seq": p["playlist"]["ps"], "dur": p["playlist"]["dur"][0] * 100})
            continue
        if "seg" not in p:
            continue
        segs = [{f: s[f] for f in ("id", "start", "stop", "fx", "sx", "ix", "c1", "c2", "c3", "pal", "col", "bri", "rev", "o2")}
                for s in p["seg"] if s.get("stop", 0)]
        sim.append({"id": int(k), "n": p["n"], "bri": p["bri"], "seg": segs, **({"hidden": True} if int(k) in step_ids else {})})
    sim.sort(key=lambda x: (x["id"] < 10, x["id"]))
    pl = presets[str(main_pl)]["playlist"]["ps"]
    html = (ROOT / "simulator/template.html").read_text()
    html = html.replace("__PRESETS__", json.dumps(sim, separators=(",", ":"))).replace("__PLAYLIST__", json.dumps(pl))
    out = BUILD / "simulador.html"
    out.write_text(html)
    local = BUILD / "simulador-local" / "index.html"
    local.parent.mkdir(exist_ok=True)
    local.write_text('<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" '
                     'content="width=device-width,initial-scale=1,viewport-fit=cover"><style>[hidden]{display:none!important}'
                     'body{margin:0}</style></head><body>\n' + html + "\n</body></html>\n")
    return out


# ------------------------------------------------------------------ network

def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


@contextlib.contextmanager
def wifi(setup, ssid):
    """Join `ssid` for the duration of the block, then go back to the home network."""
    iface, home = setup["red"]["interfaz"], setup["red"]["casa"]
    if ssid is None:
        yield
        return
    for _ in range(3):
        sh("iwctl", "station", iface, "connect", ssid)
        for _ in range(15):
            if "inet 4.3.2." in sh("ip", "-4", "addr", "show", iface):
                break
            time.sleep(1)
        else:
            continue
        break
    else:
        sh("iwctl", "station", iface, "connect", home)
        raise RuntimeError(f"no pude conectarme a {ssid}")
    try:
        yield
    finally:
        sh("iwctl", "station", iface, "connect", home)
        time.sleep(3)


def http(url, data=None, ctype="application/json", tries=5, timeout=10):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype} if data is not None else {})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except Exception as e:  # WLED on a loaded ESP32 drops requests now and then
            last = e
            time.sleep(2)
    raise RuntimeError(f"{url}: {last}")


def get_json(base, path):
    return json.loads(http(base + path)[1])


def post_json(base, path, obj):
    return http(base + path, json.dumps(obj).encode())


def upload(base, name, content: bytes):
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"/{name}\"\r\n"
            f"Content-Type: application/json\r\n\r\n").encode() + content + f"\r\n--{b}--\r\n".encode()
    return http(base + "/upload", body, f"multipart/form-data; boundary={b}")


def reachable(url):
    try:
        urllib.request.urlopen(url + "/json/info", timeout=4)
        return True
    except Exception:
        return False


def route(setup, dev):
    """(ssid to join or None, base url). SUB ORBE A is tried on the home LAN first."""
    c = setup["controlador"][dev]
    if c.get("lan") and reachable("http://" + c["lan"]):
        return None, "http://" + c["lan"]
    return setup["red"]["ap"], "http://" + c["ap_ip"]


def by_route(setup, devs):
    groups = {}
    for d in devs:
        ssid, base = route(setup, d)
        groups.setdefault(ssid, []).append((d, base))
    return groups


# ------------------------------------------------------------------ commands

def cmd_backup(args):
    setup = load()[0]
    out = ROOT / "backups" / datetime.date.today().isoformat()
    for ssid, items in by_route(setup, args.dev).items():
        with wifi(setup, ssid):
            for dev, base in items:
                d = out / dev
                d.mkdir(parents=True, exist_ok=True)
                for path, name in (("/json/cfg", "cfg.json"), ("/presets.json", "presets.json"),
                                   ("/json/info", "json_info"), ("/json/state", "json_state")):
                    (d / name).write_bytes(http(base + path)[1])
                for extra in ("palette0.json", "palette1.json", "palette2.json", "palette3.json", "palette4.json", "ledmap.json"):
                    try:
                        (d / extra).write_bytes(http(base + "/" + extra, tries=1)[1])
                    except RuntimeError:
                        pass
                print(f"{dev}: backup en {d.relative_to(ROOT)}")


def cmd_push(args):
    setup = load()[0]
    cmd_build(args)
    plan = []
    if "sub-orbe-a" in args.dev:
        a = BUILD / "sub-orbe-a"
        plan += [("sub-orbe-a", "upload", p.name, p.read_bytes()) for p in sorted(a.glob("palette*.json"))]
        plan += [("sub-orbe-a", "upload", "presets.json", (a / "presets.json").read_bytes()),
                 ("sub-orbe-a", "cfg", None, json.loads((BUILD / "sub-orbe-a/cfg.patch.json").read_text())),
                 ("sub-orbe-a", "start", None, setup["proyecto"]["arranque"]["id"])]
    if "sub-orbe-b" in args.dev:
        plan.append(("sub-orbe-b", "cfg", None, json.loads((BUILD / "sub-orbe-b/cfg.patch.json").read_text())))
    if "diana" in args.dev:
        plan.append(("diana", "cfg", None, json.loads((BUILD / "diana/cfg.patch.json").read_text())))
    for dev, kind, name, payload in plan:
        size = f" ({len(payload)} bytes)" if isinstance(payload, bytes) else ""
        print(f"  {dev:10} {kind:6} {name or ''}{size}" + ("" if isinstance(payload, (bytes, int)) else " " + json.dumps(payload)[:160]))
    if not args.apply:
        print("dry run: agregá --apply para mandarlo (antes corré `backup`)")
        return
    for ssid, items in by_route(setup, args.dev).items():
        with wifi(setup, ssid):
            for dev, base in items:
                for d, kind, name, payload in plan:
                    if d != dev:
                        continue
                    if kind == "upload":
                        upload(base, name, payload)
                    elif kind == "cfg":
                        patch = {k: v for k, v in payload.items() if not k.startswith("_")}
                        if "_abl_por_bus" in payload:  # per-bus ABL needs the full bus list from the device
                            led = get_json(base, "/json/cfg")["hw"]["led"]
                            for b in led["ins"]:
                                b["maxpwr"] = payload["_abl_por_bus"].get(str(b["len"]), b.get("maxpwr", 0))
                            patch["hw"] = {"led": {"maxpwr": payload["_abl_total"], "ins": led["ins"]}}
                        post_json(base, "/json/cfg", patch)
                    elif kind == "start":
                        # WLED keeps serving a cached presets.json right after an upload: touching another preset
                        # first makes it re-read the file before the playlist starts
                        post_json(base, "/json/state", {"ps": 1})
                        time.sleep(2)
                        post_json(base, "/json/state", {"ps": payload})
                    print(f"  ok {dev} {kind} {name or ''}")
                    time.sleep(1)


def cmd_status(args):
    setup = load()[0]
    for ssid, items in by_route(setup, args.dev).items():
        with wifi(setup, ssid):
            for dev, base in items:
                try:
                    i, st = get_json(base, "/json/info"), get_json(base, "/json/state")
                    print(f"{dev:10} {base:22} {i['name']:14} up {i['uptime']//60} min  fps {i['leds'].get('fps')}  "
                          f"ps {st.get('ps')} pl {st.get('pl')}  {i['leds'].get('pwr')} mA")
                except RuntimeError as e:
                    print(f"{dev:10} {base:22} sin respuesta ({e})")


def wait_up(base, secs=90):
    t0 = time.time()
    while time.time() - t0 < secs:
        if reachable(base):
            return True
        time.sleep(3)
    return False


def cmd_ota(args):
    """Flash our firmware over the air. Try it on sub-orbe-b first: same hardware, and if it fails to boot only a
    receiver goes dark (recovery is a USB flash of the official 0.15.1 ESP32_Ethernet bin)."""
    setup = load()[0]
    binf = ROOT / setup["firmware"]["bin"]
    if not binf.exists():
        sys.exit(f"falta {binf}: corré firmware/build.sh")
    data = binf.read_bytes()
    print(f"firmware {binf.name} ({len(data)} bytes) → {', '.join(args.dev)}")
    if not args.apply:
        print("dry run: agregá --apply para flashear")
        return
    for ssid, items in by_route(setup, args.dev).items():
        with wifi(setup, ssid):
            for dev, base in items:
                info = get_json(base, "/json/info")
                if info.get("release") != "ESP32_Ethernet" or info.get("arch") != "esp32":
                    print(f"{dev}: release {info.get('release')} / {info.get('arch')}: no coincide, no flasheo")
                    continue
                b = uuid.uuid4().hex
                body = (f"--{b}\r\nContent-Disposition: form-data; name=\"update\"; filename=\"firmware.bin\"\r\n"
                        f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
                print(f"{dev}: subiendo…")
                http(base + "/update", body, f"multipart/form-data; boundary={b}", tries=1, timeout=180)
                time.sleep(10)
                if not wait_up(base):
                    print(f"{dev}: NO volvió después de 90 s — revisar (recuperación por USB con el bin oficial)")
                    continue
                fx = get_json(base, "/json/effects")
                ok = len(fx) > 53 and fx[53] == "Strobe Fase"
                print(f"{dev}: volvió, versión {get_json(base, '/json/info')['ver']}, Strobe Fase {'OK (id 53)' if ok else 'NO ESTÁ'}")


def cmd_wifi(args):
    """Rename the wifi networks to red.ap_propuesto / aps_respaldo_propuestos without stranding anyone:
    receivers first (they drop off and wait on their fallback AP), then the master's AP, then check."""
    setup = load()[0]
    red, ctl = setup["red"], setup["controlador"]
    old, new, fb = red["ap"], red["ap_propuesto"], red.get("aps_respaldo_propuestos", {})
    if old == new:
        sys.exit(f"red.ap ya es {new}")
    print(f"1. sub-orbe-b y diana: cliente de '{old}' → '{new}', AP de respaldo → {fb}, reinicio")
    print(f"2. sub-orbe-a: AP '{old}' → '{new}', reinicio")
    print(f"3. laptop a '{new}', chequear sub-orbe-b y diana, actualizar setup.toml (red.ap)")
    if not args.apply:
        print("dry run: agregá --apply (hacelo en la obra, con los tres prendidos)")
        return
    with wifi(setup, old):
        for dev in ("sub-orbe-b", "diana"):
            base = "http://" + ctl[dev]["ap_ip"]
            ins = get_json(base, "/json/cfg")["nw"]["ins"][0]
            patch = {"nw": {"ins": [{"ssid": new, "ip": ins["ip"], "gw": ins["gw"], "sn": ins["sn"]}]}}
            if dev in fb:
                patch["ap"] = {"ssid": fb[dev]}
            post_json(base, "/json/cfg", patch)
            post_json(base, "/json/state", {"rb": True})
            print(f"  {dev}: listo, reiniciando")
    ssid, base = route(setup, "sub-orbe-a")
    with wifi(setup, ssid):
        post_json(base, "/json/cfg", {"ap": {"ssid": new}})
        post_json(base, "/json/state", {"rb": True})
        print("  sub-orbe-a: AP renombrado, reiniciando")
    time.sleep(45)
    setup["red"]["ap"] = new
    with wifi(setup, new):
        for dev in ("sub-orbe-a", "sub-orbe-b", "diana"):
            base = "http://" + ctl[dev]["ap_ip"]
            print(f"  {dev}: {'OK' if wait_up(base, 60) else 'NO RESPONDE'} en {base}")
    sh("iwctl", "known-networks", new, "set-property", "AutoConnect", "no")
    toml = ROOT / "setup.toml"
    toml.write_text(toml.read_text().replace(f'ap = "{old}"', f'ap = "{new}"', 1))
    print(f"setup.toml: red.ap = \"{new}\" (commitealo)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    for name in ("backup", "push", "status", "ota", "wifi"):
        p = sub.add_parser(name)
        p.add_argument("dev", nargs="*", default=["sub-orbe-b"] if name == "ota" else ["sub-orbe-a", "sub-orbe-b", "diana"])
        if name in ("push", "ota", "wifi"):
            p.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    {"build": cmd_build, "backup": cmd_backup, "push": cmd_push, "status": cmd_status, "ota": cmd_ota,
     "wifi": cmd_wifi}[args.cmd](args)


if __name__ == "__main__":
    main()
