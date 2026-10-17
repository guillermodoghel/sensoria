#!/usr/bin/env python3
"""Vista en vivo de SENSORIA: serves the simulator in live mode (build/vista/) and api/state, a summary of SUB ORBE A's
/json/state that the page polls. Read only: nothing here changes the work. The state is cached for a moment so many
viewers mean one request to the controller.

Config from the environment: WLED_URL (see wled.py), RANDOM_PLAYLIST, WEB_PORT, WEB_ROOT.
"""
import functools, http.server, json, logging, os, pathlib, threading, time

import wled as controller

RANDOM_PL = int(os.environ.get("RANDOM_PLAYLIST", "30"))
PORT = int(os.environ.get("WEB_PORT", "8080"))
ROOT = pathlib.Path(os.environ.get("WEB_ROOT", pathlib.Path(__file__).resolve().parent / "vista"))

log = logging.getLogger("orbe-web")
_lock = threading.Lock()
_cache = {"t": 0, "data": None}
_presets = {"t": 0, "data": {}}


def summary():
    with _lock:
        if time.time() - _cache["t"] < 1.5:
            return _cache["data"]
        try:
            st = controller.call("/json/state")
            if time.time() - _presets["t"] > 60:
                _presets["data"], _presets["t"] = controller.call("/presets.json"), time.time()
            name = lambda i: _presets["data"].get(str(i), {}).get("n", f"preset {i}") if i and i > 0 else "—"
            ps, pl = st.get("ps", -1), st.get("pl", -1)
            mode = ("apagada" if not st.get("on") else "🎲 random" if pl == RANDOM_PL
                    else f"secuencia {name(pl)}" if pl >= 0 else "⏸ pausa")
            data = {"online": True, "ps": ps, "pl": pl, "name": name(ps), "mode": mode,
                    "on": st.get("on"), "bri": st.get("bri"), "seg": st.get("seg", [])}
        except (OSError, ValueError) as e:
            log.warning("WLED: %s", e)
            data = {"online": False}
        _cache.update(t=time.time(), data=data)
        return data


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/state":
            body = json.dumps(summary()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, *a):
        pass


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), functools.partial(Handler, directory=str(ROOT)))
    log.info("vista en vivo on :%s, WLED %s, files %s", PORT, controller.where(), ROOT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
