# ORBE SENSORIAL BOT

Bot de Telegram para que la gente maneje SENSORIA desde el celular. Le habla a SUB ORBE A por la API JSON de WLED: prueba `192.168.68.50` (IP fija en LaSedeFA) y después `sub-orbe-a.local` (mDNS), así anda en cualquier red donde estén los dos (`bot/wled.py`).

- **🎲 Random** (`/random`): aplica la playlist 30 (Techno Oscuro, aleatoria).
- **⏸ Pausa** (`/pausa`): corta la playlist y deja el look que está.
- **⏭ Siguiente** (`/siguiente`): pasa al próximo look de la playlist.
- **🎨 Efectos** (`/efectos`): botones con los looks de la playlist 30. Se leen en vivo del controlador, así que después de un `push` aparecen solos.
- **ℹ️ Estado** (`/estado`): look actual y si el random está andando.

Cada persona puede mandar un comando cada 3 s (`COOLDOWN_S`).

## Dónde corre

En la Raspberry Pi 5 `rp5-guille` (`ssh pi@192.168.68.49` en LaSedeFA). Usa long polling, así que no hace falta abrir puertos ni un dominio.

- **Código:** `/opt/orbe-bot/orbe_bot.py`, solo con la librería estándar de Python.
- **Servicio:** `orbe-bot.service` (`journalctl -u orbe-bot -f` para ver los logs).
- **Config:** `/etc/orbe-bot.env` (modo 600). El token **no** va al repo.
  ```
  TELEGRAM_TOKEN=123456:ABC...
  # WLED_URL=http://otra-ip,http://sub-orbe-a.local   (opcional: direcciones a probar, en orden)
  ```

## Vista en vivo: https://orbe.doghel.com.ar

El simulador en modo "en vivo": cada 2 s lee el estado de SUB ORBE A y muestra el look que está andando en la obra, si el random está activo o en pausa, y "Sin conexión" si no la encuentra. El audio es simulado (sin sonido), solo para que se vea el efecto; los looks, colores y brillo son los reales.

- **Página:** `build/vista/index.html`, que sale de `simulator/template.html` con `LIVE = true` (`sensoria.py build`).
- **Servidor:** `bot/orbe_web.py` en `:8080` (`orbe-web.service`). Sirve la página y `api/state`, un resumen de `/json/state` cacheado 1,5 s. Solo lee, no cambia nada de la obra.
- **Túnel:** Cloudflare Tunnel `orbe` (`cloudflared.service`, config en `/etc/cloudflared/config.yml`, copia en `bot/cloudflared.yml`; las credenciales `/etc/cloudflared/<id>.json` no van al repo) → `orbe.doghel.com.ar` → `localhost:8080`. En La Sede también se ve en `http://192.168.68.49:8080`.

## Actualizar

```sh
python3 tools/sensoria.py build
scp -r bot/orbe_bot.py bot/orbe_web.py bot/wled.py build/vista pi@rp5-guille.local:/tmp/ && ssh pi@rp5-guille.local \
  'sudo install -m 755 /tmp/orbe_bot.py /tmp/orbe_web.py /tmp/wled.py /opt/orbe-bot/ && sudo rm -rf /opt/orbe-bot/vista &&
   sudo cp -r /tmp/vista /opt/orbe-bot/ && sudo chmod -R a+rX /opt/orbe-bot && sudo systemctl restart orbe-bot orbe-web'
```

## Detalle de WLED

Para pausar no alcanza con volver a mandar `{"ps": <actual>}`: WLED lo ignora si es el preset que ya está. El bot manda el mismo `fx` al segmento principal, y eso descarga la playlist sin cambiar nada de lo que se ve (`json.cpp`).

## Plug and play

Al enchufarla, la Pi se conecta sola a la red que encuentre (cable por DHCP, o wifi `alien`, `LaSedeFA` con IP fija `.49`, `la office 2.4Ghz`) y los tres servicios arrancan solos. El túnel sale para afuera, así que no hace falta abrir puertos ni tocar el router: con internet, `orbe.doghel.com.ar` y el bot andan. Una red wifi nueva hay que agregarla (`sudo nmcli dev wifi connect "<ssid>" password "<clave>"`), o enchufar cable.
