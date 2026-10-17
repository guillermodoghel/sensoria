#!/usr/bin/env python3
"""ORBE SENSORIAL BOT: Telegram bot that lets the public drive SENSORIA through SUB ORBE A's WLED JSON API.

  random on   -> apply the random playlist (setup.toml proyecto.playlist, id 30)
  pausa       -> stop the playlist and keep the current look
  siguiente   -> next look of the playlist
  efectos     -> pick one of the looks of the random playlist (read live from the controller, so new looks show up
                 after a push without touching the bot)

Long polling (no inbound port or public URL needed). Standard library only. Config comes from the environment:
TELEGRAM_TOKEN (required), WLED_URL (see wled.py), RANDOM_PLAYLIST, COOLDOWN_S.
"""
import json, logging, os, time, urllib.error, urllib.request

import wled as controller

TOKEN = os.environ["TELEGRAM_TOKEN"]
RANDOM_PL = int(os.environ.get("RANDOM_PLAYLIST", "30"))
COOLDOWN = float(os.environ.get("COOLDOWN_S", "3"))   # per user, so a crowd can't hammer the controller
API = f"https://api.telegram.org/bot{TOKEN}/"

log = logging.getLogger("orbe-bot")


class Offline(Exception):
    pass


def http(url, obj=None, timeout=8):
    data = json.dumps(obj).encode() if obj is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"null")


# ------------------------------------------------------------------ WLED

def wled(path, obj=None):
    try:
        return controller.call(path, obj)
    except (OSError, ValueError) as e:
        log.warning("WLED %s: %s", path, e)
        raise Offline from e


_presets = {"t": 0, "data": {}}


def presets():
    """presets.json from the controller, cached for a minute."""
    if time.time() - _presets["t"] > 60 or not _presets["data"]:
        _presets["data"] = {int(k): v for k, v in wled("/presets.json").items() if k != "0"}
        _presets["t"] = time.time()
    return _presets["data"]


def looks():
    """(id, name) of the looks in the random playlist, in playlist order."""
    p = presets()
    ids = p.get(RANDOM_PL, {}).get("playlist", {}).get("ps", [])
    return [(i, p[i].get("n", f"Look {i}")) for i in dict.fromkeys(ids) if i in p]


def name(ps):
    return presets().get(ps, {}).get("n", f"preset {ps}") if ps and ps > 0 else "ninguno"


def state():
    s = wled("/json/state")
    return s.get("ps", -1), s.get("pl", -1), s


def random_on():
    wled("/json/state", {"ps": RANDOM_PL})


def pause():
    """Stop the playlist and keep what is on. Re-applying the current preset is a no-op in WLED (ps == currentPreset
    is ignored), but setting a segment's fx from the API unloads the playlist (json.cpp), so set it to what it is."""
    ps, pl, s = state()
    if pl < 0:
        return False
    seg = next((g for g in s.get("seg", []) if g.get("id") == s.get("mainseg", 0)), s["seg"][0])
    wled("/json/state", {"seg": [{"id": seg["id"], "fx": seg["fx"]}]})
    return True


def apply(ps):
    wled("/json/state", {"ps": ps})   # applying a preset unloads the playlist


# ------------------------------------------------------------------ Telegram

def tg(method, **params):
    try:
        return http(API + method, params, timeout=60)
    except urllib.error.HTTPError as e:
        log.warning("Telegram %s: %s %s", method, e.code, e.read()[:200])
    except OSError as e:
        log.warning("Telegram %s: %s", method, e)


MENU = {"inline_keyboard": [
    [{"text": "🎲 Random", "callback_data": "random"}, {"text": "⏸ Pausa", "callback_data": "pausa"}],
    [{"text": "⏭ Siguiente", "callback_data": "siguiente"}, {"text": "🎨 Efectos", "callback_data": "efectos"}],
    [{"text": "ℹ️ Estado", "callback_data": "estado"}],
]}

HELP = ("Hola! Soy el bot del ORBE SENSORIAL ✨\n"
        "Desde acá podés manejar las luces del ORBE y la DIANA:\n\n"
        "🎲 /random: los efectos van cambiando solos\n"
        "⏸ /pausa: se queda en el efecto que está\n"
        "⏭ /siguiente: pasa al próximo efecto\n"
        "🎨 /efectos: elegís vos el efecto\n"
        "ℹ️ /estado: qué está sonando ahora")


def status_text():
    ps, pl, _ = state()
    if pl == RANDOM_PL:
        mode = "🎲 random"
    elif pl >= 0:
        mode = f"secuencia {name(pl)}"
    else:
        mode = "⏸ pausado"
    return f"Ahora: {name(ps)} ({mode})"


def effects_keyboard():
    rows, row = [], []
    for i, n in looks():
        row.append({"text": n, "callback_data": f"fx:{i}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    rows += [row] if row else []
    rows.append([{"text": "🎲 Volver al random", "callback_data": "random"}])
    return {"inline_keyboard": rows}


def handle(cmd):
    """Run a command; returns (text, keyboard)."""
    if cmd in ("start", "ayuda", "help"):
        return HELP, MENU
    if cmd == "random":
        random_on()
        return "🎲 Random activado: los efectos van a ir cambiando solos.", MENU
    if cmd == "pausa":
        if not pause():
            return f"Ya estaba en pausa. {status_text()}", MENU
        time.sleep(0.3)
        return f"⏸ Pausado. {status_text()}", MENU
    if cmd == "siguiente":
        _, pl, _ = state()
        if pl < 0:
            return "El random está en pausa: usá 🎲 Random o elegí un efecto.", MENU
        wled("/json/state", {"np": True})
        time.sleep(0.5)
        return f"⏭ {status_text()}", MENU
    if cmd == "efectos":
        return "Elegí un efecto (pausa el random):", effects_keyboard()
    if cmd == "estado":
        return status_text(), MENU
    if cmd.startswith("fx:"):
        ps = int(cmd[3:])
        if ps not in dict(looks()):
            return "Ese efecto ya no está.", effects_keyboard()
        apply(ps)
        return f"🎨 {name(ps)} (random en pausa, 🎲 para volver)", MENU
    return HELP, MENU


last_seen = {}


def on_update(u):
    if "callback_query" in u:
        q = u["callback_query"]
        user, chat, cmd = q["from"]["id"], q["message"]["chat"]["id"], q.get("data", "")
        tg("answerCallbackQuery", callback_query_id=q["id"])
    elif "message" in u and u["message"].get("text", "").startswith("/"):
        m = u["message"]
        user, chat = m["from"]["id"], m["chat"]["id"]
        cmd = m["text"][1:].split()[0].split("@")[0].lower()
    else:
        return
    read_only = cmd in ("start", "ayuda", "help", "estado", "efectos")
    if not read_only and time.time() - last_seen.get(user, 0) < COOLDOWN:
        tg("sendMessage", chat_id=chat, text="Despacio 🙂 esperá unos segundos.")
        return
    last_seen[user] = time.time() if not read_only else last_seen.get(user, 0)
    try:
        text, kb = handle(cmd)
    except Offline:
        text, kb = "😴 La orbe no responde ahora. Probá en un ratito.", MENU
    log.info("user %s: %s", user, cmd)
    tg("sendMessage", chat_id=chat, text=text, reply_markup=kb)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    tg("setMyCommands", commands=[
        {"command": "random", "description": "Los efectos cambian solos"},
        {"command": "pausa", "description": "Quedarse en el efecto actual"},
        {"command": "siguiente", "description": "Próximo efecto"},
        {"command": "efectos", "description": "Elegir un efecto"},
        {"command": "estado", "description": "Qué está andando"},
    ])
    log.info("ORBE SENSORIAL BOT up, WLED %s", controller.where())
    offset = None
    while True:
        r = tg("getUpdates", offset=offset, timeout=50, allowed_updates=["message", "callback_query"])
        if not r or not r.get("ok"):
            time.sleep(5)
            continue
        for u in r["result"]:
            offset = u["update_id"] + 1
            try:
                on_update(u)
            except Exception:
                log.exception("update %s", u.get("update_id"))


if __name__ == "__main__":
    main()
