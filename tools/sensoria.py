#!/usr/bin/env python3
"""SENSORIA: compile setup.toml + looks/*.toml into WLED config, back up and push the three controllers.

  sensoria.py build                 # -> build/ (presets, palettes, cfg patches, simulator)
  sensoria.py backup [dev ...]      # pull cfg/presets/palettes from the devices -> backups/<date>/
  sensoria.py push [dev ...]        # show what would be sent (dry run)
  sensoria.py push --apply [dev ...]
  sensoria.py status                # who answers, uptime, current preset

dev = sub-orbe-a | sub-orbe-b | diana (default: all). B and DIANA live only on SUB ORBE A's AP, so reaching them
means hopping the laptop's wifi to that AP and back; every hop restores the home network on exit.
"""
import argparse, contextlib, copy, datetime, json, pathlib, subprocess, sys, time, tomllib, urllib.request, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
WLED_FX = json.loads((ROOT / "data/wled-0.15-effects.json").read_text())
WLED_PAL = json.loads((ROOT / "data/wled-0.15-palettes.json").read_text())
PAL_ALIAS = {"default": 0, "color1": 2, "colors12": 3, "gradient": 4, "colors-only": 5}
GROUPS = ("grandes", "chicos", "diana")


def load():
    setup = tomllib.loads((ROOT / "setup.toml").read_text())
    looks = tomllib.loads((ROOT / "looks" / f"{setup['proyecto']['look_activo']}.toml").read_text())["look"]
    return setup, looks


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
        if name not in WLED_FX:
            sys.exit(f"efecto desconocido: {name}")
        return WLED_FX.index(name)

    def segment(self, sid, ring, p, look, name):
        return {"id": sid, "start": ring["start"], "stop": ring["stop"], "grp": 1, "spc": 0, "of": 0, "on": True,
                "frz": False, "bri": p.get("opacidad", 255), "cct": 127, "set": 0, "n": name,
                "col": self.cols(p.get("color", look.get("color", "rojo"))),
                "fx": self.fx(p.get("fx", "Solid")), "sx": p.get("sx", 128), "ix": p.get("ix", 128),
                "pal": self.pal(p.get("paleta", look.get("paleta", "color1"))),
                "c1": p.get("c1", 128), "c2": 128, "c3": 16, "sel": False, "rev": p.get("rev", False), "mi": False,
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

    def presets(self, looks):
        out = {"0": {}}
        for lk in looks:
            out[str(lk["id"])] = self.preset(lk)
        pl = self.s["proyecto"]["playlist"]
        ids = [lk["id"] for lk in looks if lk.get("playlist", True)]
        out[str(pl["id"])] = {"n": pl["nombre"], "on": True, "playlist": {
            "ps": ids, "dur": [pl["duracion_s"] * 10] * len(ids), "transition": [pl["transicion_s"] * 10] * len(ids),
            "repeat": 0, "end": 0, "r": False}}
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
                          "def": {"ps": pr["playlist"]["id"], "on": True, "bri": pr["brillo"]},
                          "um": {"AudioReactive": {"config": {"squelch": au["squelch"], "gain": au["ganancia"], "AGC": au["agc"]}}}},
            "sub-orbe-b": {"id": {"name": c["sub-orbe-b"]["nombre"], "mdns": c["sub-orbe-b"]["mdns"]}},
            "diana": {"id": {"name": c["diana"]["nombre"], "mdns": c["diana"]["mdns"]},
                      "_abl_por_bus": diana_abl, "_abl_total": c["diana"]["abl_ma"]},
        }


def cmd_build(_args):
    setup, looks = load()
    comp = Compiler(setup)
    presets = comp.presets(looks)
    a = BUILD / "sub-orbe-a"
    a.mkdir(parents=True, exist_ok=True)
    (a / "presets.json").write_text(json.dumps(presets, separators=(",", ":")))
    for name, data in comp.palettes().items():
        (a / name).write_text(json.dumps(data))
    for dev, patch in comp.cfg_patches().items():
        (BUILD / dev).mkdir(parents=True, exist_ok=True)
        (BUILD / dev / "cfg.patch.json").write_text(json.dumps(patch, indent=1))
    sim = build_simulator(comp, presets)
    pl = presets[str(setup["proyecto"]["playlist"]["id"])]["playlist"]["ps"]
    print(f"build/ listo: {len(looks)} looks, playlist {pl}, {len(comp.palettes())} paletas, {comp.total} LEDs")
    print(f"simulador: {sim}")


def build_simulator(comp, presets):
    sim = []
    for k, p in presets.items():
        if "seg" not in p:
            continue
        segs = [{f: s[f] for f in ("id", "start", "stop", "fx", "sx", "ix", "pal", "col", "bri", "rev", "o2")}
                for s in p["seg"] if s.get("stop", 0)]
        sim.append({"id": int(k), "n": p["n"], "bri": p["bri"], "seg": segs})
    sim.sort(key=lambda x: (x["id"] < 10, x["id"]))
    pl = next(p for p in presets.values() if "playlist" in p)["playlist"]["ps"]
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
    setup, _ = load()
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
    setup, _ = load()
    cmd_build(args)
    plan = []
    if "sub-orbe-a" in args.dev:
        a = BUILD / "sub-orbe-a"
        plan += [("sub-orbe-a", "upload", p.name, p.read_bytes()) for p in sorted(a.glob("palette*.json"))]
        plan += [("sub-orbe-a", "upload", "presets.json", (a / "presets.json").read_bytes()),
                 ("sub-orbe-a", "cfg", None, json.loads((BUILD / "sub-orbe-a/cfg.patch.json").read_text())),
                 ("sub-orbe-a", "start", None, setup["proyecto"]["playlist"]["id"])]
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
    setup, _ = load()
    for ssid, items in by_route(setup, args.dev).items():
        with wifi(setup, ssid):
            for dev, base in items:
                try:
                    i, st = get_json(base, "/json/info"), get_json(base, "/json/state")
                    print(f"{dev:10} {base:22} {i['name']:14} up {i['uptime']//60} min  fps {i['leds'].get('fps')}  "
                          f"ps {st.get('ps')} pl {st.get('pl')}  {i['leds'].get('pwr')} mA")
                except RuntimeError as e:
                    print(f"{dev:10} {base:22} sin respuesta ({e})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    for name in ("backup", "push", "status"):
        p = sub.add_parser(name)
        p.add_argument("dev", nargs="*", default=["sub-orbe-a", "sub-orbe-b", "diana"])
        if name == "push":
            p.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    {"build": cmd_build, "backup": cmd_backup, "push": cmd_push, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()
