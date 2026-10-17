#!/bin/sh
# Build SENSORIA's WLED for the Gledopto Elite controllers (GL-C-618WL "Elite 4D-EXMU"): WLED 0.15.1 with Gledopto's
# small fork changes (Ethernet type 13, relay/button/mic defaults, brand), which is what the boards ship with
# (their cfg has ethernet type 13, which only Gledopto's build knows), plus SENSORIA's Strobe Fase effect.
# Gledopto's changes are taken from github.com/GLEDOPTO/WLED (branch gledopto-0.15.3 vs wled v0.15.3).
# Output: firmware/dist/sensoria-*.bin (with Strobe Fase) and plain-*.bin (without it, to go back)
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
git checkout -q -- wled00/usermods_list.cpp wled00/const.h wled00/network.cpp wled00/data/settings_wifi.htm
mkdir -p usermods/strobe_fase
cp ../usermod_strobe_fase/usermod_strobe_fase.h usermods/strobe_fase/
python3 - <<'PY'
p = "wled00/usermods_list.cpp"; s = open(p).read()
s = s.replace('#include "wled.h"\n', '#include "wled.h"\n#ifdef USERMOD_STROBE_FASE\n  #include "../usermods/strobe_fase/usermod_strobe_fase.h"\n#endif\n', 1)
s = s.replace("void registerUsermods()\n{", "void registerUsermods()\n{\n  #ifdef USERMOD_STROBE_FASE\n  UsermodManager::add(new UsermodStrobeFase());\n  #endif", 1)
assert "new UsermodStrobeFase" in s, "registerUsermods() not found"
open(p, "w").write(s)

# Gledopto fork changes (same as GLEDOPTO/WLED gledopto-0.15.3)
def patch(path, old, new):
    s = open(path).read()
    assert old in s, f"{path}: {old[:40]!r} not found"
    open(path, "w").write(s.replace(old, new, 1))
patch("wled00/const.h", "#define WLED_NUM_ETH_TYPES        13", "#define WLED_NUM_ETH_TYPES        14")
patch("wled00/const.h", "#define WLED_ETH_LILYGO_T_POE_PRO 12\n",
      "#define WLED_ETH_LILYGO_T_POE_PRO 12\n#define WLED_ETH_GLEDOPTO         13\n")
patch("wled00/network.cpp", """    ETH_CLOCK_GPIO0_OUT	// eth_clk_mode
  }
};""", """    ETH_CLOCK_GPIO0_OUT	// eth_clk_mode
  },

  // Gledopto Series With Ethernet
  {
    1,                    // eth_address,
    5,                    // eth_power,
    23,                   // eth_mdc,
    33,                   // eth_mdio,
    ETH_PHY_LAN8720,      // eth_type,
    ETH_CLOCK_GPIO0_IN	 // eth_clk_mode
  },
};""")
patch("wled00/data/settings_wifi.htm", '<option value="1">WT32-ETH01</option>\n',
      '<option value="1">WT32-ETH01</option>\n\t\t\t\t<option value="13">Gledopto</option>\n')
PY
cat > platformio_override.ini <<'INI'
[platformio]
default_envs = sensoria

[env:sensoria]
extends = env:esp32_eth
board = esp32dev
build_unflags = ${env:esp32_eth.build_unflags} -D RLYPIN=-1 -D BTNPIN=-1
build_flags = ${common.build_flags} ${esp32.build_flags} ${esp32.AR_build_flags}
  -D WLED_RELEASE_NAME=\"ESP32_Ethernet\" -D WLED_USE_ETHERNET -D WLED_ETH_DEFAULT=13
  -D SERVERNAME=\"WLED-Gledopto\"
  -D RLYPIN=18 -D RLYMDE=true -D BTNPIN=17 -D BTNTYPE=2
  -D UM_AUDIOREACTIVE_ENABLE=true -D SR_DMTYPE=5 -D I2S_SDPIN=32 -D I2S_WSPIN=15 -D I2S_CKPIN=-1 -D MCLK_PIN=-1
  -D USERMOD_STROBE_FASE

; same firmware without our effect: equivalent to what the boards ship with, for going back
[env:sensoria_plain]
extends = env:sensoria
build_unflags = ${env:sensoria.build_unflags} -D USERMOD_STROBE_FASE
INI
../.venv/bin/pio run -e sensoria -e sensoria_plain
mkdir -p ../dist
rm -f ../dist/*.bin
cp .pio/build/sensoria/firmware.bin ../dist/sensoria-wled-0.15.1-gledopto-ESP32_Ethernet.bin
cp .pio/build/sensoria_plain/firmware.bin ../dist/plain-wled-0.15.1-gledopto-ESP32_Ethernet.bin
ls -la ../dist/
