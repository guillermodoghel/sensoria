# Próximo deploy (en la obra)

Objetivo: subir el setup SENSORIA completo, es decir los nombres, los looks agnósticos con la DIANA en 4 segmentos y las paletas nuevas.

## Antes
1. **Revisar los looks en el simulador:** `tools/simulador.sh`, entrada "Audio_PC" o micrófono. Ajustar `looks/agnosticos.toml` y volver a compilar.
2. **Conectar la laptop a LaSedeFA** y correr `python3 tools/sensoria.py status`. Tienen que responder los tres.

## Deploy
```sh
python3 tools/sensoria.py backup          # snapshot de cómo está todo antes de tocar
python3 tools/sensoria.py push            # revisar el plan (dry run)
python3 tools/sensoria.py push --apply    # A: paletas + presets + cfg (nombre, boot, audio) · B: nombre · DIANA: nombre + ABL
python3 tools/sensoria.py status
```

## Después
1. **Cargar el preset 1 "Test anillos"** y comprobar que cada anillo prende de su color:
   - **ORBE:** A-XL rojo, B-XL magenta, B-L amarillo, A-M verde, A-XS azul, B-S celeste.
   - **DIANA:** D1 rojo, D2 verde, D3 azul, D4 magenta, del centro hacia afuera.

   Si alguno no coincide, corregir `setup.toml` (orden o pin) y volver a hacer el push.
2. **Pasar la playlist con música real** y ajustar sensibilidades. Los cambios van en el repo, nunca a mano en WLED, así el repo sigue siendo la fuente de verdad.
3. **Commit** con el backup nuevo.

## Opcional (decidir en la obra)
- **Renombrar el AP a `SENSORIA`:** ver `docs/naming.md`. Primero se cambia el wifi de B y de DIANA, después el AP de A, y por último `red.ap` en `setup.toml`.
- **AP de respaldo de DIANA:** pasar de `BULLSEYE` a `DIANA`, desde `/settings/wifi` de DIANA.

## Volver atrás
`backups/<fecha>/orbitas-a/` tiene `presets.json`, `cfg.json` y las paletas. Para restaurar:
- **Presets y paletas:** subirlos con `/upload`.
- **Configuración:** postear `cfg.json` a `/json/cfg`.
