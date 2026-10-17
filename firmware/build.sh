#!/bin/sh
# Build SENSORIA's WLED: official 0.15.1 "esp32_eth" (release name ESP32_Ethernet, with AudioReactive, same as the
# controllers run) plus the Strobe Fase effect. Output: firmware/dist/sensoria-wled-0.15.1-ESP32_Ethernet.bin
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q platformio; }
# WLED bundles its web UI with node before compiling; use a local copy (official tarball, checksum verified)
if ! command -v node >/dev/null; then
  if [ ! -x .node/bin/node ]; then
    V=v20.18.0; mkdir -p .node-dl && (cd .node-dl && curl -sfLO https://nodejs.org/dist/$V/node-$V-linux-x64.tar.xz \
      && curl -sfLO https://nodejs.org/dist/$V/SHASUMS256.txt \
      && grep " node-$V-linux-x64.tar.xz\$" SHASUMS256.txt | sha256sum -c - \
      && mkdir -p ../.node && tar -xJf node-$V-linux-x64.tar.xz -C ../.node --strip-components=1); rm -rf .node-dl
  fi
  PATH="$PWD/.node/bin:$PATH"; export PATH
fi
[ -d .wled ] || git clone -q --depth 1 --branch v0.15.1 https://github.com/wled/WLED.git .wled
cd .wled
git checkout -q -- wled00/usermods_list.cpp
mkdir -p usermods/strobe_fase
cp ../usermod_strobe_fase/usermod_strobe_fase.h usermods/strobe_fase/
python3 - <<'PY'
p = "wled00/usermods_list.cpp"; s = open(p).read()
s = s.replace('#include "wled.h"\n', '#include "wled.h"\n#ifdef USERMOD_STROBE_FASE\n  #include "../usermods/strobe_fase/usermod_strobe_fase.h"\n#endif\n', 1)
s = s.replace("void registerUsermods()\n{", "void registerUsermods()\n{\n  #ifdef USERMOD_STROBE_FASE\n  UsermodManager::add(new UsermodStrobeFase());\n  #endif", 1)
assert "new UsermodStrobeFase" in s, "registerUsermods() not found"
open(p, "w").write(s)
PY
cat > platformio_override.ini <<'INI'
[platformio]
default_envs = sensoria

[env:sensoria]
extends = env:esp32_eth
build_flags = ${env:esp32_eth.build_flags} -D USERMOD_STROBE_FASE
INI
../.venv/bin/pio run -e sensoria
mkdir -p ../dist
cp .pio/build/sensoria/firmware.bin ../dist/sensoria-wled-0.15.1-ESP32_Ethernet.bin
ls -la ../dist/
