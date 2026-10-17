"""SUB ORBE A's WLED JSON API, wherever it is. WLED_URL is a comma-separated list of addresses to try (default: the
fixed IP in LaSedeFA, then mDNS, which works on any network both are on); the one that answered last is tried first."""
import json, os, urllib.request

CANDIDATES = [u.strip().rstrip("/") for u in
              os.environ.get("WLED_URL", "http://192.168.68.50,http://sub-orbe-a.local").split(",") if u.strip()]
_base = None


def call(path, obj=None, timeout=3):
    """GET (or POST obj as JSON) path on the controller. Raises OSError/ValueError if no address answers."""
    global _base
    order = [_base] + [c for c in CANDIDATES if c != _base] if _base else CANDIDATES
    data = json.dumps(obj).encode() if obj is not None else None
    err = None
    for base in order:
        req = urllib.request.Request(base + path, data, {"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read() or b"null")
        except (OSError, ValueError) as e:   # URLError/timeout are OSError; bad JSON is ValueError
            err = e
            continue
        _base = base
        return out
    raise err


def where():
    return _base or ", ".join(CANDIDATES)
