#pragma once
#include "wled.h"

/*
 * SENSORIA — "Strobe Fase": a strobe whose flash sits at a chosen point of the cycle.
 * Stock WLED strobes all start their cycle at the same instant (phase = millis % cycle), so rings can't take turns.
 * Giving each ring segment its own phase (custom1) makes them flash one after another.
 *
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
    for (unsigned i = 0; i < SEGLEN; i++) SEGMENT.setPixelColor(i, SEGMENT.color_from_palette(i, true, (strip.paletteBlend == 1 || strip.paletteBlend == 3), 0));
  } else if (!SEGMENT.check2) {
    SEGMENT.fill(SEGCOLOR(1));
  }
  return FRAMETIME;
}
static const char _data_FX_MODE_STROBE_FASE[] PROGMEM = "Strobe Fase@Periodo,Duracion,Fase,,,,Overlay;!,!;!;01;sx=197,ix=27,c1=0";

class UsermodStrobeFase : public Usermod {
  public:
    void setup() override {
      uint8_t id = strip.addEffect(255, &mode_strobe_fase, _data_FX_MODE_STROBE_FASE);
      DEBUG_PRINTF_P(PSTR("Strobe Fase effect id %u\n"), id);
    }
    void loop() override {}
    uint16_t getId() override { return USERMOD_ID_UNSPECIFIED; }
};
