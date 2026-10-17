import json, sys, time, urllib.request
D, A = sys.argv[1], "http://192.168.68.50"
fx = json.load(open(D + "/a_effects.json"))
F = lambda n: fx.index(n)
R, M, B, K = [255,0,0], [255,0,255], [0,0,255], [0,0,0]
RM, RB, MB, P1 = 255, 254, 253, 2   # custom palettes; 2 = "Color 1" only
BRI = 140
# (id, name, palette, color1, (fx outer rings 0,4,5, sx, ix), (fx inner rings 1-3, sx, ix))
P = [
 (10, "Pulso Grave",  P1, R, ("Gravcenter",110,170), ("Gravcentric",140,200)),
 (11, "Frecuencias",  RM, R, ("Freqmap",180,60),     ("Gravfreq",120,180)),
 (12, "Ruido Medio",  RB, R, ("Midnoise",150,160),   ("Noisemove",140,150)),
 (13, "Plasma Violeta", MB, M, ("Plasmoid",90,180),  ("Juggles",140,110)),
 (14, "Cascada",      RM, R, ("Waterfall",200,128),  ("Pixelwave",160,90)),
 (15, "Matriz",       P1, R, ("Matripix",200,90),    ("Gravcenter",120,160)),
 (16, "Latido",       MB, M, ("Pixelwave",180,80),   ("Gravcentric",150,200)),
 (17, "Movimiento",   RB, R, ("Noisemove",140,160),  ("Juggles",180,90)),
 (18, "Vumetro",      RM, R, ("Noisemeter",160,140), ("Noisemeter",160,140)),
 (19, "Grave Azul",   RB, B, ("Gravcentric",140,190),("Midnoise",150,150)),
]
def post(path, obj):
    r = urllib.request.Request(A + path, json.dumps(obj).encode(), {"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=10).read().decode()
post("/json/state", {"pl": -1})
for pid, name, pal, c1, outer, inner in P:
    segs = []
    for i in range(7):
        if i == 6: f, sx, ix, rev = "Noisemeter", 20, 110, True
        elif i in (0, 4, 5): (f, sx, ix), rev = outer, False
        else: (f, sx, ix), rev = inner, False
        segs.append({"id": i, "on": True, "bri": 255, "fx": F(f), "sx": sx, "ix": ix, "pal": pal,
                     "col": [c1, K, K], "rev": rev, "mi": False})
    post("/json/state", {"on": True, "bri": BRI, "transition": 7, "seg": segs})
    time.sleep(0.5)
    print(pid, name, post("/json/state", {"psave": pid, "n": name, "ib": True, "sb": True}))
    time.sleep(1.5)
for pid in (20, 21):
    print("del", pid, post("/json/state", {"pdel": pid})); time.sleep(1)
ids = [p[0] for p in P]
print("pl30", post("/json/state", {"psave": 30, "n": "Techno Oscuro", "on": True,
      "playlist": {"ps": ids, "dur": [6000]*10, "transition": [30]*10, "repeat": 0, "end": 0, "r": False}}))
time.sleep(1.5)
print("boot", post("/json/cfg", {"def": {"ps": 30, "on": True, "bri": BRI}}))
time.sleep(1)
print("start", post("/json/state", {"ps": 30}))
