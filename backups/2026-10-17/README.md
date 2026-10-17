# ORBITAS WLED backup 2026-10-17

- A/ master 192.168.68.50 (LaSedeFA) / 4.3.2.1 (AP "ORBITAS A"): 6 rings + DDP to B (.200) and BULLSEYE (.201)
- B/ 4.3.2.200 pure DDP receiver
- C/ BULLSEYE 4.3.2.201 pure DDP receiver, per-bus ABL 500/1000/1500/2000 (12V 3A + stepdown)

Files: cfg.json (from /json/cfg), presets.json, palette*.json (custom palettes 255/254/253), ledmap.json, json_info/json_state (reference only).
A playlist 30 "Techno Oscuro" = presets 10-19, 10 min each, boot ps 30.
presets_OLD_techno_10-21.json = previous preset set; mkpresets.py = script that built 10-19.

Restore on a device (from its folder):
  curl -F "data=@presets.json;filename=/presets.json" http://IP/upload
  curl -F "data=@palette0.json;filename=/palette0.json" http://IP/upload   # etc.
  curl -X POST -H 'Content-Type: application/json' -d @cfg.json http://IP/json/cfg
  (wifi passwords are not included in cfg.json; re-enter them in /settings/wifi)
