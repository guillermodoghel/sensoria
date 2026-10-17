# Historial

## 2026-10-16
- **ORBITAS:** A como maestro con DDP hacia B (4.3.2.200). 6 segmentos, uno por anillo. Micrófono PDM en A.
- **BULLSEYE (hoy DIANA):** pasa a ser receptor DDP puro en 4.3.2.201. Sin presets, sin 2D, con ledmap identidad.
- **A en LaSedeFA:** también se conecta como cliente, con IP 192.168.68.50/22, y su AP queda siempre activo.
- **Primer set de presets:** 10–21, techno oscuro con paleta "Color Gradient" en rojos y violetas. Playlist 30 al arrancar.
- **Preset 22 "Celeste":** paleta Colors Only, azul + celeste. De acá sale la regla de usar solo colores puros.

## 2026-10-17
- **Fuente de BULLSEYE quemada:** se reemplaza por una de 12 V 3 A con step-down a 5 V. El ABL pasa de 15 A a 5 A, repartido por bus (500/1000/1500/2000).
- **Nuevos presets 10–19:** colores puros sobre fondo negro, con 3 paletas custom de corte duro (rojo/magenta, rojo/azul, magenta/azul). Brillo 140. Playlist 30, 10 min cada uno, arranca al prender.
- **Puntitos orbitando** (Two Dots en overlay, celestes) sobre un fondo Plasmoid en los presets 15 "Órbitas" y 19 "Órbitas Azul".
- **AudioReactive a los defaults de WLED:** squelch 2 → 10, ganancia 160 → 60, AGC Vivid → Normal.
- **Laptop:** solo LaSedeFA queda con autoconexión.
- **Backup completo** de los 3 controladores (`backups/2026-10-17/`).
- **Simulador 3D** con presets reales, audio demo, carga de temas y entrada en vivo (micrófono o audio de la PC).
- **Nombres:** BULLSEYE pasa a llamarse DIANA y se arma el proyecto SENSORIA. Anillos A-XL…B-L, D1…D4. Grupos GRANDES, CHICOS y DIANA.
- **Propuesta "agnósticos"** (`looks/agnosticos.toml`):
  - **ORBITAS:** efectos que no dependen de cómo cuelgan los anillos.
  - **DIANA:** 4 segmentos, uno por anillo, con efectos que resaltan los círculos.
  - **Estado:** todavía no subida.

**Lo que está cargado en los controladores hoy** es el set de presets del 2026-10-17 (ver `backups/2026-10-17/orbitas-a/presets.json`): DIANA como un solo segmento (6) con Noisemeter invertido, y los puntitos en los segmentos 7–12.
