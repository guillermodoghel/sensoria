# Notas técnicas de WLED (0.15.1) aprendidas en este proyecto

## Presets y playlists
- **Playlist con `psave`:** hay que mandar `"o": true`. Si no, WLED guarda el estado actual en vez del objeto `playlist`.
- **Caché de `presets.json`:** después de subirlo por `/upload`, WLED sigue usando la copia vieja en memoria. Hay que aplicar otro preset primero y después el editado. `sensoria.py push` ya lo hace.
- **Editar presets:** es más confiable editar `presets.json` y subirlo de una vez que hacer muchos `psave`, porque A se cae seguido con requests sueltos.
- **Segmentos sobrantes:** un preset guardado con pocos segmentos no borra los que sobran. Por eso cada preset lista `{"id":N,"stop":0}` hasta el segmento 19.

## Efectos
- **`fade_out` y el color 2:** el fade va hacia `col[1]`. Si `col[1]` es un color, el segmento entero se llena de ese color. Dejarlo en negro.
- **Segmentos superpuestos:** funcionan, y todos dibujan sobre el mismo buffer en orden de id. Un efecto que hace fade sobre lo que hay (Plasmoid) puede ir arriba de otro que pinta todo (Strobe) sin taparlo; al revés sí lo tapa. El segmento de id más alto se dibuja arriba, y con `o2` (overlay) Two Dots no pinta el fondo. Así se hacen los "puntitos" sobre un efecto de audio.
- **Two Dots:** pone dos puntos opuestos en el anillo. El color 1 y el color 2 son los puntos; si el color 2 es igual al color 3, los dos puntos salen con el color 1. El fondo es el color 3. `ix` es el tamaño.
- **Gravcentric:** la punta es gris (casi blanco). **Waterfall:** en cada pico pinta `CHSV(92,92,92)`, un verde pálido. Ninguno de los dos respeta la regla de colores.
- **Noisemeter y Gravcenter:** dependen de dónde arranca la tira. En anillos colgados al azar se ven como manchas en lugares random.

## Paletas custom
- **Formato:** `palette0.json` a `palette9.json` en el FS, con este contenido: `{"palette":[pos,r,g,b, …]}`.
- **IDs:** `palette0` es la 255, `palette1` la 254, y así.
- **Carga:** se cargan al subirlas, sin reiniciar. `/json/info` → `cpalcount` dice cuántas hay.
- **Cortes duros:** van con dos paradas pegadas (120 y 136).

## ABL (límite de corriente)
- **Modo por bus (`prl`):** si `hw.led.ledma` es 0, el límite vale por bus (`ins[].maxpwr`) y el `maxpwr` global no hace nada.
- **DIANA:** 500/1000/1500/2000 mA por anillo (5 A en total), porque la fuente es de 12 V 3 A con un step-down a 5 V.

## AudioReactive
- **Configuración:** `um.AudioReactive.config = {squelch, gain, AGC}` por `/json/cfg`. Aplica sin reiniciar.
- **AGC Vivid:** normaliza la señal muy agresivo y deja todo saturado sin importar el volumen.

## Red
- **Notificaciones UDP:** no funcionan desde A (solo AP: el notifier no conecta). Por eso B y DIANA reciben por DDP.
- **A por LaSedeFA:** a veces deja de contestar por minutos (192.168.68.50). El respaldo es entrar por su AP, `4.3.2.1`.
- **`cfg.json`:** no se baja directo; usar `/json/cfg`. Las contraseñas de wifi no vienen (solo `pskl`, el largo).
- **Contraseña wifi de DIANA:** solo se pudo borrar desde el form `/settings/wifi`, no por `/json/cfg`.
- **Laptop:** tiene una sola placa wifi. Entrar al AP de A corta internet, así que cada operación en B o DIANA es: conectar, hacer, volver a LaSedeFA.
- **iwd:** ignora `[IPv4]` estático en `ORBITAS A.open`. La autoconexión de las redes de los WLED está apagada a propósito; solo LaSedeFA se conecta sola.
