# Nombres y estructura

## Jerarquía

```
SENSORIA                          la instalación
├── ORBE                          los 6 anillos colgados como giroscopio
│   ├── SUB ORBE A  (maestro)      A-XL · A-M · A-XS
│   └── SUB ORBE B  (receptor)     B-S · B-XL · B-L
└── DIANA          (receptor)     D1 · D2 · D3 · D4   (centro → afuera)
```

- **ORBE** es la pieza física (los 6 anillos del giroscopio). Está conformado por **SUB ORBE A** y **SUB ORBE B**, los dos controladores que lo manejan, con 3 anillos cada uno. Antes se llamaban ORBITAS A y ORBITAS B, y los wifi todavía conservan esos nombres.
- **Anillos del ORBE:** se nombran `<controlador>-<talle>`, con XL 186 LEDs, L 146, M 110, S 73 y XS 37. El nombre dice a qué controlador y a qué ficha va cada anillo, y qué tamaño tiene, sin depender de cómo está colgado.
- **Anillos de DIANA:** se numeran D1 a D4, del centro hacia afuera, porque ahí la posición radial sí importa.
- **Grupos para los looks:**
  - **GRANDES:** A-XL, B-XL, B-L.
  - **CHICOS:** A-M, A-XS, B-S.
  - **DIANA:** D1 a D4.

## Controladores

| | SUB ORBE A | SUB ORBE B | DIANA |
|---|---|---|---|
| Nombre en WLED (`id.name`) | SUB ORBE A | SUB ORBE B | DIANA |
| mDNS | `sub-orbe-a` | `sub-orbe-b` | `diana` |
| IP en LaSedeFA | 192.168.68.50 (fija) | — | — |
| IP en el AP de A | 4.3.2.1 | 4.3.2.200 (fija) | 4.3.2.201 (fija) |
| AP (nombre actual del wifi) | `ORBITAS A` (siempre activo) | `ORBITAS B` (respaldo) | `BULLSEYE` → renombrar `DIANA` |
| Límite de corriente (ABL) | 15 A | 15 A | 5 A (500/1000/1500/2000 por anillo) |

## Segmentos en SUB ORBE A

| id | nombre | LEDs (tira virtual) | qué es |
|---|---|---|---|
| 0 | A-XL | 0–185 | anillo 186, pin 16 de A |
| 1 | A-M | 186–295 | anillo 110, pin 12 de A |
| 2 | A-XS | 296–332 | anillo 37, pin 4 de A |
| 3 | B-S | 333–405 | anillo 73, pin 12 de B |
| 4 | B-XL | 406–591 | anillo 186, pin 4 de B |
| 5 | B-L | 592–737 | anillo 146, pin 2 de B |
| 6–9 | D1–D4 | 738–1103 | anillos de DIANA (37/73/110/146) |
| 10–15 | ·A-XL … ·B-L | igual que 0–5 | "puntitos" en overlay sobre cada anillo del ORBE |
| 16–19 | ·D1 … ·D4 | igual que 6–9 | "puntitos" en overlay sobre DIANA |

Los presets que no usan puntitos llevan `{"id":10..19,"stop":0}`, así al cambiar de preset desaparecen los segmentos de overlay.

## IDs de presets

| rango | uso |
|---|---|
| 1–9 | utilidades (1 = Test anillos: cada anillo de un color para identificar el cableado) |
| 10–29 | looks (10–19 en la playlist; fuera de la playlist: 22 Celeste, 23 Strobo) |
| 30–39 | playlists (30 = Techno Oscuro, 10 min por look, arranca al prender · 31 = Strobo Ola) |
| 40–59 | pasos de secuencias (40–51 = los 12 pasos de Strobo Ola) |

**Colores del preset 1 (Test anillos):**
- **ORBE:** A-XL rojo, B-XL magenta, B-L amarillo, A-M verde, A-XS azul, B-S celeste.
- **DIANA:** D1 rojo, D2 verde, D3 azul, D4 magenta.

## Pendiente: renombrar los wifi (en la obra)

| Wifi | Hoy | Nuevo |
|---|---|---|
| AP principal (lo levanta SUB ORBE A) | `ORBITAS A` | `SUB ORBE A` |
| Respaldo de SUB ORBE B | `ORBITAS B` | `SUB ORBE B` |
| Respaldo de DIANA | `BULLSEYE` | `DIANA` |

Orden para no perder a nadie:
1. **En SUB ORBE B y en DIANA:** cambiar el wifi al que se conectan, de `ORBITAS A` a `SUB ORBE A`, y de paso su AP de respaldo. Desde ese momento quedan desconectados, y se los ve por su AP de respaldo.
2. **En SUB ORBE A:** renombrar el AP a `SUB ORBE A`. B y DIANA se reconectan solos.
3. **En `setup.toml`:** `red.ap = "SUB ORBE A"`.
4. **En la laptop:** con `iwctl`, olvidar `ORBITAS A` y dejar la red nueva sin conexión automática, como las demás redes de los WLED.
