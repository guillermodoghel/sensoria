# SENSORIA

Instalación de luz audio-reactiva: **ORBITAS**, seis anillos LED colgados como un giroscopio, y **DIANA**, cuatro anillos concéntricos. Todo lo maneja WLED en tres controladores Gledopto ESP32.

Este repo es la fuente de verdad del setup: hardware, red, looks (presets), paletas y config de audio están en archivos de texto. `tools/sensoria.py` los compila y los sube a los controladores. También hace backups y arma un simulador 3D.

## El setup

| Controlador | Rol | Red | Anillos (LEDs · pin) |
|---|---|---|---|
| **ORBITAS A** | maestro: corre todos los efectos y escucha el micrófono | `192.168.68.50` en LaSedeFA · AP `ORBITAS A` en `4.3.2.1` | A-XL (186 · 16), A-M (110 · 12), A-XS (37 · 4) |
| **ORBITAS B** | receptor DDP | `4.3.2.200` dentro del AP de A | B-S (73 · 12), B-XL (186 · 4), B-L (146 · 2) |
| **DIANA** (ex BULLSEYE) | receptor DDP | `4.3.2.201` dentro del AP de A | D1 centro (37 · 2), D2 (73 · 4), D3 (110 · 16), D4 afuera (146 · 12) |

ORBITAS A arma una tira virtual de 1104 LEDs (A, después B, después DIANA) y manda por DDP la parte de B y de DIANA. B y DIANA no tienen presets propios.

**Grupos que usan los looks:**
- **GRANDES:** A-XL, B-XL y B-L. Los dos XL son los que se cruzan.
- **CHICOS:** A-M, A-XS y B-S.
- **DIANA:** D1 a D4, del centro hacia afuera.

Detalle de nombres, segmentos e IDs en [docs/naming.md](docs/naming.md).

## Reglas de diseño (aprendidas en la obra)

- **Solo colores puros:** rojo, verde, azul, celeste, magenta, amarillo, con cada canal en 0 o 255. Las mezclas se ven lavadas o blancas en estas tiras.
- **Fondo negro:** el color 2 de cada segmento va en negro, porque muchos efectos de WLED hacen el fade hacia ese color.
- **Poco blanco y poco flash:** ilumina demasiado el lugar. Evitar Gravcentric (deja un punto gris en la punta), Waterfall (verde pálido en cada golpe), Puddles y DJ Light.
- **ORBITAS no depende de la orientación:** los anillos cuelgan en cualquier ángulo y cada tira arranca en un punto distinto. Usar texturas (Plasmoid, Noisemove), puntos que recorren el anillo (Juggles, Freqpixels, Ripple Peak) y "puntitos" orbitando.
- **DIANA resalta los círculos:** un segmento por anillo. Cada círculo se cierra con el volumen (el centro es el más sensible), o los anillos alternan colores, o llevan puntitos girando.
- **Micrófono con los defaults de WLED:** squelch 10, ganancia 60, AGC normal. Con AGC "vivid" y ganancia 160 saturaba todo.

## Uso

```sh
python3 tools/sensoria.py build            # compila a build/ (presets.json, paletas, parches de cfg, simulador)
python3 tools/sensoria.py status           # quién responde, uptime, preset actual
python3 tools/sensoria.py backup           # baja cfg/presets/paletas de los 3 → backups/<fecha>/
python3 tools/sensoria.py push             # muestra qué mandaría (dry run)
python3 tools/sensoria.py push --apply     # lo manda (hacé backup antes)
tools/simulador.sh                         # abre el simulador local (con micrófono / audio de la PC)
```

- **Cómo llega a cada controlador:** a ORBITAS A entra por LaSedeFA y, si no contesta, por su AP. A B y a DIANA solo se llega desde el AP de A, así que el script cambia el wifi de la laptop a `ORBITAS A` y lo devuelve a LaSedeFA al terminar.
- **Look que se sube:** el de `proyecto.look_activo` en `setup.toml`, que apunta a un archivo de `looks/`.

## Simulador

`build/simulador.html` es una vista 3D (three.js) de los 10 anillos con ports en JavaScript de los efectos de audio de WLED 0.15. Trae una señal simulada, un loop de techno, carga de temas y entrada en vivo.

- **Versión publicada:** https://claude.ai/artifact/9BdjZfhymKRCNAsPNh1YfV. Ahí el navegador bloquea el micrófono.
- **Versión local:** `tools/simulador.sh` sirve `build/simulador-local/` en `127.0.0.1:8765`. Ahí anda el micrófono y el audio de la PC. Chrome no lista el "monitor" de PipeWire, así que el script crea una entrada virtual `Audio_PC` con `pactl`.
- **Del simulador a la obra:** el botón "Copiar JSON" exporta el estado en formato `/json/state` de WLED.

## Carpetas

- `setup.toml`: hardware, red, anillos, audio, colores y paletas.
- `looks/`: un archivo de looks por set. `agnosticos.toml` es la propuesta actual.
- `tools/sensoria.py`: compilar, backup, push y status.
- `simulator/template.html`: fuente del simulador; `build` le inyecta los presets.
- `backups/`: snapshots de los tres controladores.
- `docs/`: nombres, notas técnicas de WLED, historial y plan de deploy.
- `data/`: listas de efectos y paletas de WLED 0.15.1 (el índice es el ID).
