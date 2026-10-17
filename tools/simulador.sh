#!/bin/sh
# Abre el simulador SENSORIA en local: ahí el navegador permite micrófono y audio de la PC.
# Chrome no lista el "monitor" de PipeWire como entrada, así que se crea una fuente virtual Audio_PC que lo copia
# (temporal: se va al reiniciar, o con `pactl unload-module module-remap-source`).
cd "$(dirname "$0")/.."
python3 tools/sensoria.py build >/dev/null || exit 1
if ! pactl list sources short 2>/dev/null | grep -q audio_pc; then
  sink=$(pactl get-default-sink 2>/dev/null)
  [ -n "$sink" ] && pactl load-module module-remap-source master="$sink.monitor" source_name=audio_pc \
    source_properties=device.description=Audio_PC >/dev/null
fi
PORT=8765
if ! curl -s -o /dev/null "http://127.0.0.1:$PORT/"; then
  (cd build/simulador-local && nohup python3 -m http.server $PORT --bind 127.0.0.1 >/dev/null 2>&1 &)
  sleep 0.5
fi
xdg-open "http://127.0.0.1:$PORT/" >/dev/null 2>&1 &
