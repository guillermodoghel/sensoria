#pragma once
#include "wled.h"

/*
 * SENSORIA's own effects for WLED 0.15.1. Stock WLED runs every segment on its own, so rings can't take turns or
 * share an event; these effects share state between all the segments that run them.
 *
 * Strobe Fase  a strobe whose flash sits at a chosen point of the cycle; giving each ring its own phase makes them
 *              flash one after another.
 * Anillo Azar  on each kick, one ring of the group (picked at random, never the same twice in a row) flashes.
 *              Idea from warrolight's randomShapes (github.com/PampaWarro/warrolight).
 * Onda Radial  each kick sends a wave from the center outward; every ring lights up whole when the wave passes its
 *              radius, so it doesn't matter how the rings hang or where each strip starts.
 *              Idea from warrolight's sound-waves.
 *
 * Kicks are AudioReactive's samplePeak, gated by warrolight's musicFlash curve: bass below the threshold counts as
 * nothing and the rest is squared, because dim LEDs already look bright and soft passages would light everything.
 */

#define SENSORIA_WRAP (strip.paletteBlend == 1 || strip.paletteBlend == 3)

static um_data_t *sensoriaAudio() {
  um_data_t *um_data;
  if (!UsermodManager::getUMData(&um_data, USERMOD_ID_AUDIOREACTIVE)) um_data = simulateSound(SEGMENT.soundSim);
  return um_data;
}

// kick strength 0..1, or 0 when there is no kick this frame (custom3 = threshold, 0..31 -> 0..80 % of the bass level)
static float sensoriaKick(um_data_t *um_data) {
  if (!*(uint8_t *)um_data->u_data[3]) return 0.0f;
  uint8_t *fft = (uint8_t *)um_data->u_data[2];
  float bass = (fft[0] + fft[1] + fft[2]) / 765.0f;
  float cut = SEGMENT.custom3 * 0.8f / 31.0f;
  if (bass <= cut) return 0.0f;
  float v = (bass - cut) / (1.0f - cut);
  return v * v > 1.0f ? 1.0f : v * v;
}

static void sensoriaFill(float level) {
  if (level > 0.01f) {
    uint8_t bri = level >= 1.0f ? 255 : level * 255;
    for (unsigned i = 0; i < SEGLEN; i++)
      SEGMENT.setPixelColor(i, color_fade(SEGMENT.color_from_palette(i, true, SENSORIA_WRAP, 0), bri));
  } else if (!SEGMENT.check2) {
    SEGMENT.fill(SEGCOLOR(1));
  }
}

/*
 *   speed     period: 50 ms + (255 - speed) * 20 ms
 *   intensity flash length as a fraction of the period (at least one frame)
 *   custom1   phase: where in the period this segment flashes (0..255 = 0..100 %)
 *   check2    overlay: when off, leave the pixels alone instead of painting color 2
 */
static uint16_t mode_strobe_fase(void) {
  uint32_t cycle = 50 + (255 - SEGMENT.speed) * 20;
  uint32_t onTime = FRAMETIME + ((cycle * SEGMENT.intensity) >> 8);
  uint32_t phase = (cycle * SEGMENT.custom1) >> 8;
  uint32_t t = (strip.now + cycle - phase) % cycle;
  if (t < onTime) {
    for (unsigned i = 0; i < SEGLEN; i++) SEGMENT.setPixelColor(i, SEGMENT.color_from_palette(i, true, SENSORIA_WRAP, 0));
  } else if (!SEGMENT.check2) {
    SEGMENT.fill(SEGCOLOR(1));
  }
  return FRAMETIME;
}
static const char _data_FX_MODE_STROBE_FASE[] PROGMEM = "Strobe Fase@Periodo,Duracion,Fase,,,,Overlay;!,!;!;01;sx=197,ix=27,c1=0";

/*
 *   speed     how fast the flash fades (decay 30..540 ms)
 *   custom1   minimum time between flashes (60..1080 ms)
 *   custom2   group (custom2 / 32): each group picks its own ring, e.g. ORBE = 0, DIANA = 1
 *   custom3   kick threshold
 */
struct SensoriaAzar { uint32_t frame, seen, members, t0; int8_t chosen, last; float level; };
static SensoriaAzar sensoriaAzar[8];

static uint16_t mode_anillo_azar(void) {
  um_data_t *um_data = sensoriaAudio();
  uint8_t id = strip.getCurrSegmentId();
  SensoriaAzar &g = sensoriaAzar[SEGMENT.custom2 >> 5];
  if (g.frame != strip.now) {  // first ring of the group in this frame: settle members and maybe pick
    g.frame = strip.now;
    g.members = g.seen | (1u << id);
    g.seen = 0;
    float kick = sensoriaKick(um_data);
    if (kick > 0.0f && strip.now - g.t0 > 60u + SEGMENT.custom1 * 4u) {
      int n = __builtin_popcount(g.members);
      int pick = -1;
      for (int tries = 0; tries < 8; tries++) {
        uint32_t m = g.members;
        for (int k = random8(n); k > 0; k--) m &= m - 1;  // drop the lowest set bits to land on the k-th member
        pick = __builtin_ctz(m);
        if (pick != g.last || n < 2) break;
      }
      g.chosen = g.last = pick;
      g.t0 = strip.now;
      g.level = 0.35f + 0.65f * kick;
    }
  }
  g.seen |= 1u << id;
  float tau = 30.0f + (255 - SEGMENT.speed) * 2.0f;
  sensoriaFill(id == g.chosen ? g.level * expf(-(float)(strip.now - g.t0) / tau) : 0.0f);
  return FRAMETIME;
}
static const char _data_FX_MODE_ANILLO_AZAR[] PROGMEM = "Anillo Azar@Caida,,Separacion,Grupo,Umbral,,Overlay;!,!;!;01v;sx=160,c1=40,c2=0,c3=12";

/*
 *   speed     wave speed (0.4..4 radius units per second; the outermost ring is at radius 1)
 *   intensity wave thickness
 *   custom1   minimum time between waves (60..1080 ms)
 *   custom2   this ring's radius (0..255 = center..outermost)
 *   custom3   kick threshold
 */
struct SensoriaWave { uint32_t t0; float strength; };
static SensoriaWave sensoriaWaves[8];
static uint8_t sensoriaWaveCount = 0;
static uint32_t sensoriaWaveFrame = 0, sensoriaWaveLast = 0;

static uint16_t mode_onda_radial(void) {
  um_data_t *um_data = sensoriaAudio();
  if (sensoriaWaveFrame != strip.now) {  // once per frame, shared by every ring running this effect
    sensoriaWaveFrame = strip.now;
    while (sensoriaWaveCount && strip.now - sensoriaWaves[0].t0 > 3000) {
      memmove(sensoriaWaves, sensoriaWaves + 1, (sensoriaWaveCount - 1) * sizeof(SensoriaWave));
      sensoriaWaveCount--;
    }
    float kick = sensoriaKick(um_data);
    if (kick > 0.0f && strip.now - sensoriaWaveLast > 60u + SEGMENT.custom1 * 4u) {
      sensoriaWaveLast = strip.now;
      if (sensoriaWaveCount == 8) {
        memmove(sensoriaWaves, sensoriaWaves + 1, 7 * sizeof(SensoriaWave));
        sensoriaWaveCount = 7;
      }
      sensoriaWaves[sensoriaWaveCount++] = {strip.now, kick};
    }
  }
  float r = SEGMENT.custom2 / 255.0f;
  float vel = 0.4f + SEGMENT.speed * 3.6f / 255.0f;
  float width = 0.08f + SEGMENT.intensity * 0.5f / 255.0f;
  float level = 0.0f;
  for (uint8_t i = 0; i < sensoriaWaveCount; i++) {
    const SensoriaWave &w = sensoriaWaves[i];
    float radius = (strip.now - w.t0) / 1000.0f * vel * (0.6f + 0.8f * w.strength);
    float d = fabsf(radius - r);
    float fadeOut = 1.0f - radius / 1.4f;
    if (d < width && fadeOut > 0.0f) level += w.strength * (1.0f - d / width) * fadeOut;
  }
  sensoriaFill(level);
  return FRAMETIME;
}
static const char _data_FX_MODE_ONDA_RADIAL[] PROGMEM = "Onda Radial@Velocidad,Ancho,Separacion,Radio,Umbral,,Overlay;!,!;!;01v;sx=120,ix=60,c1=30,c2=128,c3=12";

class UsermodStrobeFase : public Usermod {
  public:
    void setup() override {
      // registered in this order they take the first free slots of 0.15.1: 53, 142, 151 (data/sensoria-effects.json)
      strip.addEffect(255, &mode_strobe_fase, _data_FX_MODE_STROBE_FASE);
      strip.addEffect(255, &mode_anillo_azar, _data_FX_MODE_ANILLO_AZAR);
      strip.addEffect(255, &mode_onda_radial, _data_FX_MODE_ONDA_RADIAL);
    }
    void loop() override {}
    uint16_t getId() override { return USERMOD_ID_UNSPECIFIED; }
};
