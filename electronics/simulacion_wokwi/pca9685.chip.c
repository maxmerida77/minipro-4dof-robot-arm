/*
 * Wokwi Custom Chip — NXP PCA9685 (I2C 0x40, 50 Hz PWM para Servos CH0..CH4)
 * ==========================================================================
 * 100% compatible con la librería oficial `Adafruit_PWMServoDriver` y el
 * firmware real `firmware/minipro_b2_stealth/minipro_b2_stealth.ino`.
 *
 * Implementa:
 *   - Dirección I2C 0x40 (MODE1 + auto-incremento AI, MODE2, PRE_SCALE)
 *   - Registros LED0..LED4 (0x06..0x19) y ALL_LED (0xFA..0xFD, incl. FULL_OFF)
 *   - Generación real de pulsos PWM 50 Hz (500..2500 µs) sobre CH0..CH4
 */

#include "wokwi-api.h"
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define PCA9685_ADDR     0x40
#define NUM_CH           5
#define REG_MODE1        0x00
#define REG_MODE2        0x01
#define REG_LED0_ON_L    0x06
#define REG_ALL_ON_L     0xFA
#define REG_ALL_OFF_H    0xFD
#define REG_PRESCALE     0xFE

typedef struct chip_state chip_state_t;

typedef struct {
  chip_state_t *parent;
  uint8_t ch;
} ch_ctx_t;

struct chip_state {
  uint8_t regs[256];
  uint8_t reg_ptr;
  bool    expect_reg_addr;

  pin_t   ch_pins[NUM_CH];
  timer_t frame_timer;
  timer_t pulse_timers[NUM_CH];
  ch_ctx_t ch_ctx[NUM_CH];
  uint32_t period_us;
};

static uint32_t calc_period_us(uint8_t prescale) {
  // f_pwm = 25 MHz / (4096 * (prescale + 1)) -> T_us = 4096 * (prescale + 1) / 25
  uint32_t p = (uint32_t)4096 * ((uint32_t)prescale + 1) / 25;
  if (p < 5000)  p = 5000;
  if (p > 40000) p = 40000;
  return p;
}

static uint32_t calc_channel_pulse_us(chip_state_t *c, uint8_t ch) {
  // Si está en SLEEP (MODE1 bit 4), sin salida
  if (c->regs[REG_MODE1] & 0x10) return 0;

  uint8_t base = (uint8_t)(REG_LED0_ON_L + ch * 4);
  uint16_t on_val  = (uint16_t)c->regs[base + 0] | ((uint16_t)(c->regs[base + 1] & 0x1F) << 8);
  uint16_t off_val = (uint16_t)c->regs[base + 2] | ((uint16_t)(c->regs[base + 3] & 0x1F) << 8);

  // Bit 12 (0x1000) en OFF = FULL_OFF (usado por RELAX)
  if (off_val & 0x1000) return 0;
  if (on_val & 0x1000)  return c->period_us;

  uint16_t on12  = on_val & 0x0FFF;
  uint16_t off12 = off_val & 0x0FFF;
  uint16_t ticks = (off12 >= on12) ? (off12 - on12) : (4096 - on12 + off12);
  if (ticks == 0) return 0;

  return (uint32_t)(((uint64_t)ticks * (uint64_t)c->period_us) / 4096ULL);
}

static void on_pulse_end(void *user_data) {
  ch_ctx_t *ctx = (ch_ctx_t *)user_data;
  pin_write(ctx->parent->ch_pins[ctx->ch], LOW);
}

static void on_pwm_frame(void *user_data) {
  chip_state_t *c = (chip_state_t *)user_data;
  for (uint8_t ch = 0; ch < NUM_CH; ch++) {
    uint32_t pw = calc_channel_pulse_us(c, ch);
    if (pw >= 200 && pw < c->period_us - 200) {
      pin_write(c->ch_pins[ch], HIGH);
      timer_start(c->pulse_timers[ch], pw, false);
    } else if (pw >= c->period_us - 200) {
      pin_write(c->ch_pins[ch], HIGH);
    } else {
      pin_write(c->ch_pins[ch], LOW);
    }
  }
}

static bool on_i2c_connect(void *user_data, uint32_t address, bool read) {
  chip_state_t *c = (chip_state_t *)user_data;
  (void)address;
  if (!read) {
    c->expect_reg_addr = true;
  }
  return true;
}

static uint8_t on_i2c_read(void *user_data) {
  chip_state_t *c = (chip_state_t *)user_data;
  uint8_t val = c->regs[c->reg_ptr];
  if (c->regs[REG_MODE1] & 0x20) {
    c->reg_ptr++;
  }
  return val;
}

static bool on_i2c_write(void *user_data, uint8_t data) {
  chip_state_t *c = (chip_state_t *)user_data;
  if (c->expect_reg_addr) {
    c->reg_ptr = data;
    c->expect_reg_addr = false;
    return true;
  }

  uint8_t reg = c->reg_ptr;
  c->regs[reg] = data;

  // ALL_LED_ON/OFF (0xFA..0xFD) se refleja en todos los canales CH0..CH4
  if (reg >= REG_ALL_ON_L && reg <= REG_ALL_OFF_H) {
    uint8_t off = (uint8_t)(reg - REG_ALL_ON_L);
    for (uint8_t ch = 0; ch < NUM_CH; ch++) {
      c->regs[REG_LED0_ON_L + ch * 4 + off] = data;
    }
  }

  // Cambio de frecuencia PWM (PRE_SCALE)
  if (reg == REG_PRESCALE) {
    c->period_us = calc_period_us(data);
    timer_start(c->frame_timer, c->period_us, true);
  }

  // Auto-incremento de puntero (bit AI = 0x20 en MODE1)
  if (c->regs[REG_MODE1] & 0x20) {
    c->reg_ptr++;
  }
  return true;
}

static void on_i2c_disconnect(void *user_data) {
  (void)user_data;
}

void chip_init(void) {
  chip_state_t *c = (chip_state_t *)calloc(1, sizeof(chip_state_t));
  c->regs[REG_MODE1]    = 0x11; // SLEEP=1 por defecto al arrancar (estándar NXP)
  c->regs[REG_MODE2]    = 0x04;
  c->regs[REG_PRESCALE] = 0x79; // 121 -> ~50 Hz
  c->period_us          = 20000;

  const char *ch_names[NUM_CH] = { "CH0", "CH1", "CH2", "CH3", "CH4" };
  for (uint8_t ch = 0; ch < NUM_CH; ch++) {
    c->ch_pins[ch] = pin_init(ch_names[ch], OUTPUT);
    pin_write(c->ch_pins[ch], LOW);
    c->ch_ctx[ch].parent = c;
    c->ch_ctx[ch].ch     = ch;
    const timer_config_t pt_cfg = {
      .callback  = on_pulse_end,
      .user_data = &c->ch_ctx[ch],
    };
    c->pulse_timers[ch] = timer_init(&pt_cfg);
  }

  const i2c_config_t i2c_cfg = {
    .user_data  = c,
    .address    = PCA9685_ADDR,
    .scl        = pin_init("SCL", INPUT_PULLUP),
    .sda        = pin_init("SDA", INPUT_PULLUP),
    .connect    = on_i2c_connect,
    .read       = on_i2c_read,
    .write      = on_i2c_write,
    .disconnect = on_i2c_disconnect,
  };
  i2c_init(&i2c_cfg);

  const timer_config_t frame_cfg = {
    .callback  = on_pwm_frame,
    .user_data = c,
  };
  c->frame_timer = timer_init(&frame_cfg);
  timer_start(c->frame_timer, c->period_us, true);

  printf("[Wokwi PCA9685] Listo en I2C 0x%02X (50 Hz PWM en CH0..CH4)\n", PCA9685_ADDR);
}
