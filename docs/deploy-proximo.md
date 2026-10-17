# Próximo deploy (en la obra)

Objetivo: dejar SENSORIA con todo lo nuevo.
- **Nombres:** SUB ORBE A, SUB ORBE B y DIANA.
- **Looks:** los agnósticos, con la DIANA en 4 segmentos y las paletas nuevas.
- **Brillo:** 25%.
- **Arranque:** 5 s de Test anillos y después la playlist techno.
- **Estrobos:** de 30 s dentro de la playlist.
- **Firmware propio** (efecto Strobe Fase).
- **Wifi:** los nombres nuevos.

Cada paso deja todo andando, así que se puede cortar en cualquier punto.

## 0. Antes de empezar
- **Red de la laptop:** conectada a LaSedeFA, con los tres controladores prendidos.
- **Status:** `python3 tools/sensoria.py status`. Tienen que responder los tres.
- **Backup:** `python3 tools/sensoria.py backup`, para guardar cómo está todo antes de tocar. Commitear.

## 1. Config y looks (sin firmware nuevo)
```sh
python3 tools/sensoria.py push            # revisar el plan
python3 tools/sensoria.py push --apply
```
- **SUB ORBE A recibe:**
  - las 5 paletas y `presets.json` (looks 10–19, 22, 23; Strobo Ola como secuencia 31 con pasos 40–51; Test anillos 1; playlists 30 y 32);
  - la configuración: nombre, arranque en la 32, brillo 64 y audio con los defaults.
- **SUB ORBE B recibe:** el nombre.
- **DIANA recibe:** el nombre y el límite de corriente por anillo.
- **Al terminar:** el script aplica el preset 32 (Arranque).

**Verificar:**
1. **Test anillos.** Durante 5 s cada anillo tiene que prender de su color:
   - **ORBE:** A-XL rojo, B-XL magenta, B-L amarillo, A-M verde, A-XS azul, B-S celeste.
   - **DIANA:** D1 rojo, D2 verde, D3 azul, D4 magenta, del centro hacia afuera.

   Si alguno no coincide, corregir el orden o el pin en `setup.toml` y volver a hacer el push.
2. **Arranque de la playlist:** después de los 5 s tiene que empezar "Techno Oscuro" con Plasma Rojo.
3. **Cadena de playlists:** el final de la playlist (Strobo y Strobo Ola) se puede probar rápido. En la interfaz de WLED, editar la playlist 30 y poner 10 s por look, o aplicar el 23 y después la 31 a mano. Strobo Ola tiene que pasar sola a la 30 cuando termina; si no pasa, avisar.
4. **Fondo del Strobo:** en el 23 tiene que verse el plasma de fondo entre destellos.

## 2. Firmware propio (Strobe Fase)
El binario está en `firmware/dist/`. Para recompilarlo: `firmware/build.sh`. Es el WLED 0.15.1 "ESP32_Ethernet" oficial más el efecto 53, "Strobe Fase". La configuración y los presets no se tocan.
```sh
python3 tools/sensoria.py ota sub-orbe-b --apply    # primero en B: mismo hardware, si algo sale mal solo se apaga un receptor
python3 tools/sensoria.py ota sub-orbe-a --apply    # si B volvió bien y lista "Strobe Fase (id 53)"
```
**Después:**
1. **Activar el firmware en la config:** `[firmware] strobe_fase = true` en `setup.toml`.
2. **Volver a subir:** `push --apply`. Strobo Ola pasa a ser el preset 24, un solo destello por anillo, y la secuencia de presets 31 deja de usarse.
3. **Verificar el 24:** de a un anillo por vez, de adentro hacia afuera, ORBE y DIANA cada uno a su ritmo, con el plasma de fondo.

**Si algo sale mal:**
- **B no vuelve después del OTA:** conectarlo por USB y flashear el bin oficial `WLED_0.15.1_ESP32_Ethernet.bin` desde install.wled.me.
- **Para volver atrás sin USB:** en `http://<ip>/update` subir el bin oficial.

## 3. Nombres de los wifi
```sh
python3 tools/sensoria.py wifi            # muestra el plan
python3 tools/sensoria.py wifi --apply
```
El script hace los cambios en este orden:
1. **SUB ORBE B y DIANA:** pasan a buscar `SUB ORBE A` y renombran sus AP de respaldo a `SUB ORBE B` y `DIANA`. Se reinician y quedan esperando.
2. **SUB ORBE A:** renombra su AP a `SUB ORBE A` y se reinicia.
3. **Laptop:** se conecta a la red nueva y chequea los tres. Actualiza `red.ap` en `setup.toml` y apaga la autoconexión de la red nueva.

**Si B o DIANA no vuelven:** aparecen sus AP de respaldo (`SUB ORBE B` / `DIANA`). Conectarse a ese AP, entrar a `4.3.2.1` y revisar el wifi en `/settings/wifi`.

## 4. Cierre
- `python3 tools/sensoria.py backup` y commit. `setup.toml` queda con `red.ap` y `firmware.strobe_fase` actualizados.
- Pasar la playlist con música real y ajustar sensibilidades en `looks/agnosticos.toml`, nunca a mano en WLED.
