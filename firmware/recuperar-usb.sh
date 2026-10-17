#!/bin/sh
# Recover a Gledopto Elite (GL-C-618WL) over USB-C when it doesn't boot after an OTA.
# Writes only the program: config and presets (the filesystem at 0x310000) are kept.
#
#   firmware/recuperar-usb.sh                 # flashes dist/plain-*.bin (0.15.1 Gledopto, as shipped)
#   firmware/recuperar-usb.sh archivo.bin     # any other app image (e.g. Gledopto's GL-C-618WL_0.15.4_ESP32_Ethernet.bin)
#
# The board's USB chip is a WCH CH343/CH9102: Linux sees it as /dev/ttyACM* (or /dev/ttyUSB*). Reading it needs the
# uucp group on Arch (sudo usermod -aG uucp $USER, then log in again) or running this with sudo.
# If esptool can't connect, unplug, hold the board's button, plug in again and retry.
set -e
cd "$(dirname "$0")"
BIN=${1:-$(ls dist/plain-*.bin | head -1)}
PORT=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | head -1)
[ -n "$PORT" ] || { echo "no veo la placa por USB (¿cable de datos? ¿enchufada?)"; exit 1; }
[ -r "$PORT" ] && [ -w "$PORT" ] || { echo "sin permiso sobre $PORT: sumate al grupo uucp o corré con sudo"; exit 1; }
[ -x .venv/bin/esptool.py ] || .venv/bin/pip install -q esptool
echo "placa en $PORT · grabando $BIN"
# after an OTA the bootloader boots the second app slot; erasing otadata sends it back to app0, where we write
.venv/bin/esptool.py --chip esp32 --port "$PORT" --baud 460800 erase_region 0xe000 0x2000
.venv/bin/esptool.py --chip esp32 --port "$PORT" --baud 460800 write_flash 0x10000 "$BIN"
echo "listo: desenchufá el USB, alimentala normal y entrá por su AP o por 4.3.2.x"
