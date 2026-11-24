/*
 * Simulación Interactiva en Wokwi — Mini-Pro 4-DOF (`B2 Stealth` v4 Clean-DFA)
 * =============================================================================
 * Sincronizado al 100% con el firmware `firmware/minipro_b2_stealth/`:
 *   - Cinemática trigonométrica real de pinza MeArm Mod 1.5 (adiós 3°/mm lineal)
 *   - Deshabilitación inmediata FULL_OFF (4096) al arrancar antes de habilitar PWM
 *   - Guarda cinemática anti-mesa (impide Z_j3/j4 < 22 mm o Z_tcp < 8 mm)
 *   - Resincronización limpia tras CENTER y rampa suave (>= 1200 ms) al salir de RELAX
 *
 * Pines I2C idénticos a Seeed Studio XIAO ESP32-S3:
 *   SDA = GPIO 5 (D4) · SCL = GPIO 6 (D5)
 */

#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <Adafruit_PWMServoDriver.h>

static const int      I2C_SDA_PIN  = 5;     // D4 en XIAO ESP32-S3
static const int      I2C_SCL_PIN  = 6;     // D5 en XIAO ESP32-S3
static const uint8_t  PCA9685_ADDR = 0x40;
static const float    SERVO_FREQ   = 50.0f;
static const uint32_t CTRL_DT_MS   = 10;    // 100 Hz

// Parámetros cinemáticos DH + Pinza MeArm Mod 1.5 (sincronizados con cad/params.py)
static const float DH_D1_MM              = 82.0f;
static const float DH_A2_MM              = 82.0f;
static const float DH_A3_MM              = 70.0f;
static const float DH_A4_MM              = 53.0f;
static const float TABLE_SAFE_Z_TCP_MM   = 8.0f;
static const float TABLE_SAFE_Z_JOINT_MM = 22.0f;
static const float GRIP_LINK_L_MM        = 16.5f;
static const float GRIP_NOMINAL_OPEN_MM  = 15.0f;
static const float GRIP_CLOSED_SERVO_DEG = 40.0f;
static const float MIN_WAKE_MOVE_MS      = 1200.0f;

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
  { 4,    0.0f,  30.0f,  15.0f,  15.0f,   40.0f, 600, 2400 }, // Pinza SG90 (trigonométrica)
};

Adafruit_PWMServoDriver pca(PCA9685_ADDR);

float curQ[5]    = { 0.0f, 68.0f, -96.0f, 28.0f, 15.0f };
float startQ[5]  = { 0.0f, 68.0f, -96.0f, 28.0f, 15.0f };
float targetQ[5] = { 0.0f, 68.0f, -96.0f, 28.0f, 15.0f };

bool     relaxed     = true;
bool     moving      = false;
uint32_t moveStartMs = 0;
float    moveDurMs   = 1100.0f;
uint32_t lastCtrlMs  = 0;

struct SweepStep { float q[5]; float durMs; const char *label; };
static const SweepStep SWEEP_SEQ[] = {
  { {   0,  68, -96,  28, 15 }, 1100, "Pose Héroe inicial (TCP=53mm)" },
  { {  65,  68, -96,  28, 15 }, 1000, "J1 Base -> +65 deg" },
  { { -65,  68, -96,  28, 15 }, 1300, "J1 Base -> -65 deg" },
  { {   0,  68, -96,  28, 15 }, 900,  "J1 Base -> 0 deg" },
  { {   0, 115, -96,  28, 15 }, 1000, "J2 Hombro -> +115 deg" },
  { {   0,  48, -96,  28, 15 }, 1200, "J2 Hombro -> +48 deg" },
  { {   0,  68, -96,  28, 15 }, 900,  "J2 Hombro -> +68 deg" },
  { {   0,  68, -30,  28, 15 }, 1000, "J3 Codo -> -30 deg" },
  { {   0,  68,-125,  28, 15 }, 1200, "J3 Codo -> -125 deg" },
  { {   0,  68, -96,  28, 15 }, 900,  "J3 Codo -> -96 deg" },
  { {   0,  68, -96,  70, 15 }, 900,  "J4 Muñeca -> +70 deg" },
  { {   0,  68, -96, -45, 15 }, 1100, "J4 Muñeca -> -45 deg" },
  { {   0,  68, -96,  28, 15 }, 900,  "J4 Muñeca -> +28 deg" },
  { {   0,  68, -96,  28, 28 }, 700,  "Pinza MeArm 1.5 -> 28 mm" },
  { {   0,  68, -96,  28,  2 }, 800,  "Pinza MeArm 1.5 -> 2 mm" },
  { {   0,  68, -96,  28, 15 }, 700,  "Pinza MeArm 1.5 -> 15 mm (TCP=53mm)" },
};
static const int SWEEP_LEN = sizeof(SWEEP_SEQ) / sizeof(SWEEP_SEQ[0]);
bool sweepActive = false;
int  sweepIdx    = 0;

static float clampF(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

static float gripMmToThetaRad(float g) {
  float gc = clampF(g, 0.0f, 30.0f);
  float s = clampF((gc * 0.5f) / GRIP_LINK_L_MM, 0.0f, 0.95f);
  return asinf(s);
}

static float gripMmToServoDeg(float g) {
  return GRIP_CLOSED_SERVO_DEG + gripMmToThetaRad(g) * (180.0f / 3.14159265f);
}

static float gripMmToTcpX(float g) {
  return DH_A4_MM + GRIP_LINK_L_MM * (cosf(gripMmToThetaRad(g)) - cosf(gripMmToThetaRad(GRIP_NOMINAL_OPEN_MM)));
}

static bool checkTableGuard(const float q[5], float &zTcpOut) {
  float a2 = q[1] * (3.14159265f / 180.0f);
  float a3 = (q[1] + q[2]) * (3.14159265f / 180.0f);
  float a4 = (q[1] + q[2] + q[3]) * (3.14159265f / 180.0f);
  float z_j3 = DH_D1_MM + DH_A2_MM * sinf(a2);
  float z_j4 = z_j3 + DH_A3_MM * sinf(a3);
  zTcpOut    = z_j4 + gripMmToTcpX(q[4]) * sinf(a4);
  return (z_j3 >= TABLE_SAFE_Z_JOINT_MM) && (z_j4 >= TABLE_SAFE_Z_JOINT_MM) && (zTcpOut >= TABLE_SAFE_Z_TCP_MM);
}

static uint16_t logicalToUs(int i, float q) {
  const ServoAxisConfig &a = AXES[i];
  float qc = clampF(q, a.q_min, a.q_max);
  float sdeg = (i == 4) ? gripMmToServoDeg(qc) : (a.zero_deg + qc);
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

static void disableAllOutputs() {
  for (int i = 0; i < 16; i++) pca.setPWM(i, 0, 4096); // FULL_OFF real
}

static void relaxAll() {
  relaxed = true;
  moving = false;
  sweepActive = false;
  disableAllOutputs();
  Serial.println("[OK] RELAX: PWM FULL_OFF (4096) en todos los canales");
}

static bool startMove(const float qIn[5], float durMs) {
  float qSafe[5];
  for (int i = 0; i < 5; i++) qSafe[i] = clampF(qIn[i], AXES[i].q_min, AXES[i].q_max);
  float zTcp = 0.0f;
  if (!checkTableGuard(qSafe, zTcp)) {
    Serial.printf("[GUARD] Pose bloqueada por guarda anti-mesa (Z_tcp=%.1f mm < %.0f mm)\n", zTcp, TABLE_SAFE_Z_TCP_MM);
    return false;
  }
  bool waking = relaxed;
  relaxed = false;
  for (int i = 0; i < 5; i++) {
    startQ[i]  = curQ[i];
    targetQ[i] = qSafe[i];
  }
  float d = durMs < 50.0f ? 50.0f : durMs;
  if (waking && d < MIN_WAKE_MOVE_MS) d = MIN_WAKE_MOVE_MS;
  moveDurMs   = d;
  moveStartMs = millis();
  moving      = true;
  return true;
}

static void printStatus() {
  Serial.printf("[STATUS] q=(%.1f, %.1f, %.1f, %.1f) deg | pinza=%.1f mm (TCP_x=%.2f mm) | %s\n",
                curQ[0], curQ[1], curQ[2], curQ[3], curQ[4], gripMmToTcpX(curQ[4]),
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
    float q[5] = { 0, 68, -96, 28, 15 };
    startMove(q, 1100);
    Serial.println("[OK] Moviendo a Pose Héroe v4");
  } else if (up == "HOME") {
    sweepActive = false;
    float q[5] = { 0, 90, -90, 0, 15 };
    startMove(q, 1100);
    Serial.println("[OK] Moviendo a HOME v4");
  } else if (up == "CENTER") {
    sweepActive = false;
    relaxed = false;
    moving = false;
    for (int i = 0; i < 4; i++) {
      writeUs(i, 1500);
      curQ[i] = targetQ[i] = startQ[i] = clampF(90.0f - AXES[i].zero_deg, AXES[i].q_min, AXES[i].q_max);
    }
    curQ[4] = targetQ[4] = startQ[4] = GRIP_NOMINAL_OPEN_MM;
    writeUs(4, logicalToUs(4, curQ[4]));
    Serial.println("[OK] CENTER: CH0..CH3 en 1500 us + estado interno resincronizado");
  } else if (up == "RELAX") {
    relaxAll();
  } else if (up == "STATUS") {
    printStatus();
  } else if (up.startsWith("M ") || up.startsWith("G ")) {
    sweepActive = false;
    float q[5] = { curQ[0], curQ[1], curQ[2], curQ[3], curQ[4] };
    float dur = up.startsWith("G ") ? 120.0f : 1100.0f;
    int n = sscanf(line.c_str() + 2, "%f %f %f %f %f %f", &q[0], &q[1], &q[2], &q[3], &q[4], &dur);
    if (n >= 5) {
      if (startMove(q, dur)) {
        Serial.printf("[OK] Target=(%.1f, %.1f, %.1f, %.1f, %.1fmm) en %.0f ms\n",
                      q[0], q[1], q[2], q[3], q[4], dur);
      }
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
  Serial.println("\n=== MINI-PRO 4-DOF (B2 STEALTH v4 Clean-DFA) — SIMULADOR WOKWI ===");

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.beginTransmission(PCA9685_ADDR);
  if (Wire.endTransmission() == 0) {
    Serial.println("[OK] PCA9685 detectado en I2C 0x40 (SDA=GPIO5, SCL=GPIO6)");
  } else {
    Serial.println("[ERR] PCA9685 NO detectado en 0x40 — revisa cables SDA/SCL");
  }

  pca.begin();
  disableAllOutputs(); // Evita pulsos residuales en reinicios calientes!
  pca.setOscillatorFrequency(25000000);
  pca.setPWMFreq(SERVO_FREQ);
  delay(20);

  Serial.println("[INFO] Iniciando barrido SWEEP automático v4 (escribe HERO, HOME, CENTER, RELAX o M ...)");
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
