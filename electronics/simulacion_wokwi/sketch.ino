/*
 * Simulación Interactiva en Wokwi — Mini-Pro 4-DOF (`B2 Stealth`)
 * ===============================================================
 * Corre la lógica real del firmware `minipro_b2_stealth.ino` (I2C 0x40 +
 * Adafruit_PWMServoDriver + interpolador quíntico 100 Hz) sobre un ESP32-S3
 * conectado al chip custom `PCA9685` y los 5 servos virtuales (J1..J4 + Pinza).
 *
 * Pines I2C idénticos a Seeed Studio XIAO ESP32-S3:
 *   SDA = GPIO 5 (D4) · SCL = GPIO 6 (D5)
 *
 * Comandos por Monitor Serial (115200 baud):
 *   SWEEP  -> Recorre articulación por articulación (J1 -> J2 -> J3 -> J4 -> Pinza)
 *   HERO   -> Pose Héroe CAD v3.1 (0°, 68°, -96°, 28°, 16 mm)
 *   HOME   -> Reposo vertical (0°, 90°, -90°, 0°, 18 mm)
 *   CENTER -> Centra CH0..CH3 a 1500 µs (90° físico) para atornillar horns
 *   M q1 q2 q3 q4 grip [ms] -> Movimiento quíntico suave
 *   G q1 q2 q3 q4 grip      -> Movimiento directo
 *   RELAX  -> Apaga PWM de todos los servos
 *   STATUS -> Imprime estado actual
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

static const int      I2C_SDA_PIN  = 5;     // D4 en XIAO ESP32-S3
static const int      I2C_SCL_PIN  = 6;     // D5 en XIAO ESP32-S3
static const uint8_t  PCA9685_ADDR = 0x40;
static const float    SERVO_FREQ   = 50.0f;
static const uint32_t CTRL_DT_MS   = 10;    // 100 Hz

struct ServoAxisConfig {
  uint8_t  ch;
  float    q_min, q_max, q_home, q_hero, zero_deg;
  uint16_t us_min, us_max;
};

static const ServoAxisConfig AXES[5] = {
  { 0,  -90.0f,  90.0f,   0.0f,   0.0f,   90.0f, 550, 2450 }, // J1 Base
  { 1,   15.0f, 165.0f,  90.0f,  68.0f,    0.0f, 550, 2450 }, // J2 Hombro
  { 2, -135.0f,  45.0f, -90.0f, -96.0f,  135.0f, 550, 2450 }, // J3 Codo
  { 3,  -90.0f,  90.0f,   0.0f,  28.0f,   90.0f, 550, 2450 }, // J4 Muñeca
  { 4,    0.0f,  30.0f,  18.0f,  16.0f,   40.0f, 600, 2400 }, // Pinza SG90 (3°/mm)
};

Adafruit_PWMServoDriver pca(PCA9685_ADDR);

float curQ[5]    = { 0.0f, 68.0f, -96.0f, 28.0f, 16.0f };
float startQ[5]  = { 0.0f, 68.0f, -96.0f, 28.0f, 16.0f };
float targetQ[5] = { 0.0f, 68.0f, -96.0f, 28.0f, 16.0f };

bool     relaxed     = false;
bool     moving      = false;
uint32_t moveStartMs = 0;
float    moveDurMs   = 900.0f;
uint32_t lastCtrlMs  = 0;

// Secuencia SWEEP articulación por articulación (igual al video demo)
struct SweepStep { float q[5]; float durMs; const char *label; };
static const SweepStep SWEEP_SEQ[] = {
  { {   0,  68, -96,  28, 16 }, 800,  "Pose Héroe inicial" },
  { {  65,  68, -96,  28, 16 }, 900,  "J1 Base -> +65 deg" },
  { { -65,  68, -96,  28, 16 }, 1200, "J1 Base -> -65 deg" },
  { {   0,  68, -96,  28, 16 }, 800,  "J1 Base -> 0 deg" },
  { {   0, 115, -96,  28, 16 }, 900,  "J2 Hombro -> +115 deg" },
  { {   0,  42, -96,  28, 16 }, 1100, "J2 Hombro -> +42 deg" },
  { {   0,  68, -96,  28, 16 }, 800,  "J2 Hombro -> +68 deg" },
  { {   0,  68, -30,  28, 16 }, 900,  "J3 Codo -> -30 deg" },
  { {   0,  68,-125,  28, 16 }, 1100, "J3 Codo -> -125 deg" },
  { {   0,  68, -96,  28, 16 }, 800,  "J3 Codo -> -96 deg" },
  { {   0,  68, -96,  70, 16 }, 800,  "J4 Muñeca -> +70 deg" },
  { {   0,  68, -96, -55, 16 }, 1000, "J4 Muñeca -> -55 deg" },
  { {   0,  68, -96,  28, 16 }, 800,  "J4 Muñeca -> +28 deg" },
  { {   0,  68, -96,  28, 28 }, 600,  "Pinza -> 28 mm (Abierta)" },
  { {   0,  68, -96,  28,  2 }, 700,  "Pinza -> 2 mm (Cerrada)" },
  { {   0,  68, -96,  28, 16 }, 600,  "Pinza -> 16 mm (Pose Héroe)" },
};
static const int SWEEP_LEN = sizeof(SWEEP_SEQ) / sizeof(SWEEP_SEQ[0]);
bool sweepActive = false;
int  sweepIdx    = 0;

static float clampF(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

static uint16_t logicalToUs(int i, float q) {
  const ServoAxisConfig &a = AXES[i];
  float qc = clampF(q, a.q_min, a.q_max);
  float sdeg = (i == 4) ? (a.zero_deg + qc * 3.0f) : (a.zero_deg + qc);
  sdeg = clampF(sdeg, 0.0f, 180.0f);
  return (uint16_t)(a.us_min + (sdeg / 180.0f) * (a.us_max - a.us_min));
}

static void writeUs(int i, uint16_t us) {
  uint16_t ticks = (uint16_t)clampF((float)us * 4096.0f / 20000.0f, 80.0f, 600.0f);
  pca.setPWM(AXES[i].ch, 0, ticks);
}

static void applyAll() {
  if (relaxed) return;
  for (int i = 0; i < 5; i++) writeUs(i, logicalToUs(i, curQ[i]));
}

static void relaxAll() {
  relaxed = true;
  moving = false;
  sweepActive = false;
  for (int i = 0; i < 5; i++) pca.setPWM(AXES[i].ch, 0, 4096); // FULL_OFF
  Serial.println("[OK] RELAX: PWM apagado en CH0..CH4");
}

static void startMove(const float q[5], float durMs) {
  relaxed = false;
  for (int i = 0; i < 5; i++) {
    startQ[i]  = curQ[i];
    targetQ[i] = clampF(q[i], AXES[i].q_min, AXES[i].q_max);
  }
  moveDurMs   = durMs < 50.0f ? 50.0f : durMs;
  moveStartMs = millis();
  moving      = true;
}

static void printStatus() {
  Serial.printf("[STATUS] q=(%.1f, %.1f, %.1f, %.1f) deg | pinza=%.1f mm | %s\n",
                curQ[0], curQ[1], curQ[2], curQ[3], curQ[4],
                relaxed ? "RELAX" : "ACTIVO");
}

static void handleCmd(String line) {
  line.trim();
  if (!line.length()) return;
  String up = line;
  up.toUpperCase();

  if (up == "SWEEP") {
    sweepActive = true;
    sweepIdx = 0;
    Serial.printf("[SWEEP] %s\n", SWEEP_SEQ[0].label);
    startMove(SWEEP_SEQ[0].q, SWEEP_SEQ[0].durMs);
  } else if (up == "HERO") {
    sweepActive = false;
    float q[5] = { 0, 68, -96, 28, 16 };
    startMove(q, 900);
    Serial.println("[OK] Moviendo a Pose Héroe");
  } else if (up == "HOME") {
    sweepActive = false;
    float q[5] = { 0, 90, -90, 0, 18 };
    startMove(q, 900);
    Serial.println("[OK] Moviendo a HOME");
  } else if (up == "CENTER") {
    sweepActive = false;
    relaxed = false;
    moving = false;
    for (int i = 0; i < 4; i++) writeUs(i, 1500);
    writeUs(4, logicalToUs(4, 15.0f));
    Serial.println("[OK] CENTER: CH0..CH3 en 1500 us (90 deg mecánico)");
  } else if (up == "RELAX") {
    relaxAll();
  } else if (up == "STATUS") {
    printStatus();
  } else if (up.startsWith("M ") || up.startsWith("G ")) {
    sweepActive = false;
    float q[5] = { curQ[0], curQ[1], curQ[2], curQ[3], curQ[4] };
    float dur = up.startsWith("G ") ? 80.0f : 900.0f;
    int n = sscanf(line.c_str() + 2, "%f %f %f %f %f %f", &q[0], &q[1], &q[2], &q[3], &q[4], &dur);
    if (n >= 5) {
      startMove(q, dur);
      Serial.printf("[OK] Target=(%.1f, %.1f, %.1f, %.1f, %.1fmm) en %.0f ms\n",
                    q[0], q[1], q[2], q[3], q[4], dur);
    } else {
      Serial.println("[ERR] Uso: M q1 q2 q3 q4 grip [ms]");
    }
  } else {
    Serial.println("[HELP] Comandos: SWEEP | HERO | HOME | CENTER | M q1 q2 q3 q4 g [ms] | RELAX | STATUS");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== MINI-PRO 4-DOF (B2 STEALTH) — SIMULADOR WOKWI ===");

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.beginTransmission(PCA9685_ADDR);
  if (Wire.endTransmission() == 0) {
    Serial.println("[OK] PCA9685 detectado en I2C 0x40 (SDA=GPIO5, SCL=GPIO6)");
  } else {
    Serial.println("[ERR] PCA9685 NO detectado en 0x40 — revisa cables SDA/SCL");
  }

  pca.begin();
  pca.setOscillatorFrequency(25000000);
  pca.setPWMFreq(SERVO_FREQ);
  delay(20);

  // Arranca automáticamente el recorrido SWEEP para ver cada articulación en vivo
  Serial.println("[INFO] Iniciando barrido SWEEP automático (escribe HERO, HOME, CENTER, RELAX o M ...)");
  handleCmd("SWEEP");
}

void loop() {
  while (Serial.available()) {
    String ln = Serial.readStringUntil('\n');
    handleCmd(ln);
  }

  uint32_t now = millis();
  if (now - lastCtrlMs >= CTRL_DT_MS) {
    lastCtrlMs = now;
    if (moving && !relaxed) {
      float u = clampF((float)(now - moveStartMs) / moveDurMs, 0.0f, 1.0f);
      float s = u * u * u * (10.0f - 15.0f * u + 6.0f * u * u); // Quíntico mínimo-jerk
      for (int i = 0; i < 5; i++) curQ[i] = startQ[i] + s * (targetQ[i] - startQ[i]);
      applyAll();
      if (u >= 1.0f) {
        moving = false;
        if (sweepActive) {
          sweepIdx++;
          if (sweepIdx < SWEEP_LEN) {
            Serial.printf("[SWEEP] %s\n", SWEEP_SEQ[sweepIdx].label);
            startMove(SWEEP_SEQ[sweepIdx].q, SWEEP_SEQ[sweepIdx].durMs);
          } else {
            sweepActive = false;
            Serial.println("[OK] SWEEP completado. Escribe SWEEP, HERO, CENTER, M 45 80 -70 0 25, o RELAX.");
          }
        }
      }
    }
  }
}
