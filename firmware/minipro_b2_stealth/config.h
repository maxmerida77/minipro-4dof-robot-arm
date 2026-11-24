#pragma once
#include <Arduino.h>
#include <math.h>

// ============================================================================
// CONFIGURACIÓN Y CALIBRACIÓN — MINI-PRO 4-DOF (`B2 STEALTH` v4 Clean-DFA)
// ============================================================================
// Sincronizado 100% con `cad/params.py`, `python/robot_minipro_rtb.py` y
// `python/gemelo_digital_esp32.py`.
//
// Incluye correcciones de auditoría (Codex):
//   - Conversión trigonométrica real de pinza MeArm Mod 1.5 (adiós 3°/mm lineal)
//   - Guarda cinemática anti-mesa (impide Z_tcp < 8 mm o Z_j3/j4 < 22 mm)
//   - Resincronización limpia tras RELAX / CENTER / RAW y FULL_OFF real (4096)

// --- Red Wi-Fi ---
static const char* WIFI_STA_SSID = "";
static const char* WIFI_STA_PASS = "";

static const char* WIFI_AP_SSID  = "MiniPro-B2-Stealth";
static const char* WIFI_AP_PASS  = "minipro1234";

static const uint16_t UDP_PORT = 4210;

// --- PCA9685 ---
static const uint8_t  PCA9685_ADDR  = 0x40;
static const float    SERVO_FREQ_HZ = 50.0f;  // Período 20,000 µs

// --- Parámetros Cinemáticos DH (mm) y Guarda Física 3D Real (idéntica a `cad/params.py`) ---
static const float DH_D1_MM                  = 82.0f;
static const float DH_A2_MM                  = 82.0f;
static const float DH_A3_MM                  = 70.0f;
static const float DH_A4_MM                  = 53.0f;
static const float TABLE_SAFE_Z_TCP_MM       = 8.0f;
static const float TABLE_SAFE_Z_JOINT_MM     = 22.0f;
static const float GUARD_FLOOR_Z_MIN_MM      = 4.0f;    // Z libre mínimo real (incluyendo panza SG90 y dedos)
static const float GUARD_BASE_DRUM_R_MM      = 56.0f;   // Carcasa base fija Ø106 mm (Z < 54 mm)
static const float GUARD_BASE_DRUM_Z_MM      = 54.0f;
static const float GUARD_BASE_NECK_R_MM      = 46.0f;   // Cuello torreta J1 (Z < 64 mm)
static const float GUARD_BASE_NECK_Z_MM      = 64.0f;
static const float GUARD_L4_SG90_Z_MM        = -21.8f;  // Fondo real de palma + SG90 bajo el eje J4
static const float GUARD_FINGER_TIP_EXTRA_MM = 7.1f;    // Saliente físico de las puntas de dedo tras TCP

// --- Geometría Exacta Pinza Paralela Abierta MeArm Módulo 1.5 (idéntica a `cad/params.py`) ---
static const float GRIP_LINK_L_MM         = 16.5f;  // Longitud centro-a-centro brazos/bielas
static const float GRIP_NOMINAL_OPEN_MM   = 15.0f;  // Apertura donde centro X almohadillas == A4 (53.0 mm)
static const float GRIP_PAD_CENTER_Z_MM   = 5.8f;   // Cota Z local del centro de almohadillas w04 respecto a J4
static const float GRIP_CLOSED_SERVO_DEG  = 40.0f;  // Ángulo SG90 cuando apertura g = 0 mm (θ = 0°)

// --- Interpolador Suave (Quíntico mínimo-jerk 100 Hz) ---
static const uint32_t CONTROL_PERIOD_MS   = 10;     // 100 Hz
static const float    DEFAULT_MOVE_MS     = 1100.0f; // Movimientos suaves para limitar picos de corriente < 2.2 A
static const float    MIN_WAKE_MOVE_MS    = 1200.0f; // Rampa suave obligatoria al salir de RELAX
static const float    STREAM_ALPHA        = 0.25f;

struct ServoAxisConfig {
    uint8_t  channel;
    float    q_min;          // Límite lógico inferior (° o mm en pinza)
    float    q_max;          // Límite lógico superior (° o mm en pinza)
    float    q_home;         // Postura de reposo segura
    float    q_hero;         // Pose Héroe CAD/Peter Corke
    float    servo_zero_deg; // Ángulo físico del servo (0..180°) cuando q lógico = 0
    float    offset_deg;     // Ajuste fino mecánico (±15°)
    bool     invert;         // true si el servo gira en sentido opuesto al DH
    uint16_t us_min;         // Pulso µs para 0° físico
    uint16_t us_max;         // Pulso µs para 180° físico
};

enum AxisIndex : uint8_t {
    AX_J1_BASE = 0,
    AX_J2_SHOULDER = 1,
    AX_J3_ELBOW = 2,
    AX_J4_WRIST = 3,
    AX_GRIPPER = 4
};

// Calibración segura para 4× MG90S (`AR1240`) + 1× SG90 (Pinza MeArm Mod 1.5):
// Límites sincronizados con `cad/params.py` (margen real contra topes internos MG90S y cables!)
static ServoAxisConfig AXES[5] = {
    // ch,  q_min,  q_max, q_home, q_hero, zero_deg, offset, invert, us_min, us_max
    {   0,  -85.0f,  85.0f,   0.0f,   0.0f,   90.0f,   0.0f,  false,   550,   2450 }, // J1 Base (170° útiles)
    {   1,   22.0f, 145.0f,  90.0f,  68.0f,    0.0f,   0.0f,  false,   550,   2450 }, // J2 Hombro (123° útiles)
    {   2, -125.0f,  20.0f, -90.0f, -96.0f,  135.0f,   0.0f,  false,   550,   2450 }, // J3 Codo (145° útiles)
    {   3,  -80.0f,  80.0f,   0.0f,  28.0f,   90.0f,   0.0f,  false,   550,   2450 }, // J4 Muñeca (160° útiles)
    {   4,    0.0f,  30.0f,  15.0f,  15.0f,   40.0f,   0.0f,  false,   600,   2400 }, // Pinza SG90 (trigonométrica)
};

// --- Cinemática Exacta Compartida de la Pinza Paralela (g_mm <-> θ_deg <-> Δx_tcp) ---
static inline float gripMmToThetaRad(float grip_mm) {
    float g = (grip_mm < 0.0f) ? 0.0f : ((grip_mm > 30.0f) ? 30.0f : grip_mm);
    float s = (g * 0.5f) / GRIP_LINK_L_MM;
    if (s > 0.95f) s = 0.95f;
    return asinf(s);
}

static inline float gripMmToServoDeg(float grip_mm) {
    float th_deg = gripMmToThetaRad(grip_mm) * (180.0f / 3.14159265f);
    return GRIP_CLOSED_SERVO_DEG + th_deg;
}

static inline float servoDegToGripMm(float servo_deg) {
    float th_deg = servo_deg - GRIP_CLOSED_SERVO_DEG;
    if (th_deg < 0.0f) th_deg = 0.0f;
    if (th_deg > 71.8f) th_deg = 71.8f;
    return 2.0f * GRIP_LINK_L_MM * sinf(th_deg * (3.14159265f / 180.0f));
}

static inline float gripMmToTcpX(float grip_mm) {
    float th_cur = gripMmToThetaRad(grip_mm);
    float th_nom = gripMmToThetaRad(GRIP_NOMINAL_OPEN_MM);
    return DH_A4_MM + GRIP_LINK_L_MM * (cosf(th_cur) - cosf(th_nom));
}

// --- Cinemática Directa (FK) 4R Estándar DH + Punto de Agarre Real Almohadillas ---
static inline void computeFK(const float qDeg[4], float& x_mm, float& y_mm, float& z_mm, float& phi_deg) {
    const float d2r = 3.14159265f / 180.0f;
    float t1   = qDeg[0] * d2r;
    float t2   = qDeg[1] * d2r;
    float t23  = (qDeg[1] + qDeg[2]) * d2r;
    float t234 = (qDeg[1] + qDeg[2] + qDeg[3]) * d2r;

    float r = DH_A2_MM * cosf(t2) + DH_A3_MM * cosf(t23) + DH_A4_MM * cosf(t234);
    x_mm    = r * cosf(t1);
    y_mm    = r * sinf(t1);
    z_mm    = DH_D1_MM + DH_A2_MM * sinf(t2) + DH_A3_MM * sinf(t23) + DH_A4_MM * sinf(t234);
    phi_deg = qDeg[1] + qDeg[2] + qDeg[3];
}

static inline void computeGripPointFK(const float qDeg[5], float& x_mm, float& y_mm, float& z_mm) {
    const float d2r = 3.14159265f / 180.0f;
    float t1   = qDeg[0] * d2r;
    float t2   = qDeg[1] * d2r;
    float t23  = (qDeg[1] + qDeg[2]) * d2r;
    float t234 = (qDeg[1] + qDeg[2] + qDeg[3]) * d2r;
    float gx   = gripMmToTcpX(qDeg[4]);
    float gz   = GRIP_PAD_CENTER_Z_MM;
    float r = DH_A2_MM * cosf(t2) + DH_A3_MM * cosf(t23) + gx * cosf(t234) - gz * sinf(t234);
    x_mm = r * cosf(t1);
    y_mm = r * sinf(t1);
    z_mm = DH_D1_MM + DH_A2_MM * sinf(t2) + DH_A3_MM * sinf(t23) + gx * sinf(t234) + gz * cosf(t234);
}

static inline bool solveIKPlanar(
    float q1Rad, float rSigned, float z_mm, float phi_deg,
    float qOutDeg[4], String* errMsg, bool elbowUp
) {
    const float d2r = 3.14159265f / 180.0f;
    const float r2d = 180.0f / 3.14159265f;
    float phi = phi_deg * d2r;
    float rw = rSigned - DH_A4_MM * cosf(phi);
    float zw = (z_mm - DH_D1_MM) - DH_A4_MM * sinf(phi);

    float dist2 = rw * rw + zw * zw;
    float D = (dist2 - DH_A2_MM * DH_A2_MM - DH_A3_MM * DH_A3_MM) / (2.0f * DH_A2_MM * DH_A3_MM);
    if (fabsf(D) > 1.0005f) {
        if (errMsg) *errMsg = "Fuera de alcance geometrico";
        return false;
    }
    if (D > 1.0f)  D = 1.0f;
    if (D < -1.0f) D = -1.0f;

    float s3 = sqrtf(fmaxf(0.0f, 1.0f - D * D));
    float q3 = elbowUp ? atan2f(-s3, D) : atan2f(s3, D);
    float q2 = atan2f(zw, rw) - atan2f(DH_A3_MM * sinf(q3), DH_A2_MM + DH_A3_MM * cosf(q3));
    float q4 = atan2f(sinf(phi - q2 - q3), cosf(phi - q2 - q3));

    float qd[4] = { q1Rad * r2d, q2 * r2d, q3 * r2d, q4 * r2d };
    static const char* NAMES[4] = { "J1", "J2", "J3", "J4" };
    for (int i = 0; i < 4; i++) {
        if (!isfinite(qd[i])) {
            if (errMsg) *errMsg = "Resultado IK no finito";
            return false;
        }
        if (qd[i] < AXES[i].q_min - 0.15f || qd[i] > AXES[i].q_max + 0.15f) {
            if (errMsg) *errMsg = String(NAMES[i]) + " fuera de limite (" + String(qd[i], 1) + " deg)";
            return false;
        }
        if (qd[i] < AXES[i].q_min) qd[i] = AXES[i].q_min;
        if (qd[i] > AXES[i].q_max) qd[i] = AXES[i].q_max;
        qOutDeg[i] = qd[i];
    }
    if (errMsg) *errMsg = "OK";
    return true;
}

// --- Cinemática Inversa (IK) Analítica Cerrada 4R con radio firmado + rechazo NaN ---
static inline bool computeIK(
    float x_mm, float y_mm, float z_mm, float phi_deg,
    float qOutDeg[4], String* errMsg = nullptr, bool elbowUp = true, float q1RefDeg = 0.0f
) {
    if (!isfinite(x_mm) || !isfinite(y_mm) || !isfinite(z_mm) || !isfinite(phi_deg) || !isfinite(q1RefDeg)) {
        if (errMsg) *errMsg = "Entrada no finita (NaN/Inf)";
        return false;
    }
    const float d2r = 3.14159265f / 180.0f;
    float r = hypotf(x_mm, y_mm);
    String firstErr;
    bool branches[2] = { elbowUp, !elbowUp };
    if (r < 1e-3f) {
        float q1c = q1RefDeg;
        if (q1c < AXES[0].q_min) q1c = AXES[0].q_min;
        if (q1c > AXES[0].q_max) q1c = AXES[0].q_max;
        for (int b = 0; b < 2; b++) {
            String err;
            if (solveIKPlanar(q1c * d2r, 0.0f, z_mm, phi_deg, qOutDeg, &err, branches[b])) {
                if (errMsg) *errMsg = "OK";
                return true;
            }
            if (b == 0) firstErr = err;
        }
        if (errMsg) *errMsg = firstErr;
        return false;
    }
    float q1Fwd = atan2f(y_mm, x_mm);
    float q1Rev = atan2f(sinf(q1Fwd + 3.14159265f), cosf(q1Fwd + 3.14159265f));
    for (int b = 0; b < 2; b++) {
        String errF, errR;
        if (solveIKPlanar(q1Fwd, +r, z_mm, phi_deg, qOutDeg, &errF, branches[b])) {
            if (errMsg) *errMsg = "OK";
            return true;
        }
        if (b == 0) firstErr = errF;
        // Rama sobre el hombro (radio firmado negativo -> soporta poses traseras legales X < 0!)
        if (solveIKPlanar(q1Rev, -r, z_mm, phi_deg, qOutDeg, &errR, branches[b])) {
            if (errMsg) *errMsg = "OK";
            return true;
        }
    }
    if (errMsg) *errMsg = firstErr;
    return false;
}

// --- Guarda Física 3D Envolvente Real (idéntica a `check_physical_guard_v4` en `cad/params.py`) ---
static inline bool checkPhysicalGuard(const float q[5], String* reasonOut = nullptr, float* zMinOut = nullptr) {
    for (int i = 0; i < 5; i++) {
        if (!isfinite(q[i])) {
            if (reasonOut) *reasonOut = "Entrada no finita (NaN/Inf)";
            return false;
        }
    }
    if (q[4] < -0.05f || q[4] > 30.05f) {
        if (reasonOut) *reasonOut = "Pinza fuera de rango [0, 30 mm]";
        return false;
    }
    static const char* NAMES[4] = { "J1", "J2", "J3", "J4" };
    for (int i = 0; i < 4; i++) {
        if (q[i] < AXES[i].q_min - 0.05f || q[i] > AXES[i].q_max + 0.05f) {
            if (reasonOut) *reasonOut = String(NAMES[i]) + " fuera de limite seguro";
            return false;
        }
    }

    const float d2r = 3.14159265f / 180.0f;
    float t2   = q[AX_J2_SHOULDER] * d2r;
    float t23  = (q[AX_J2_SHOULDER] + q[AX_J3_ELBOW]) * d2r;
    float t234 = (q[AX_J2_SHOULDER] + q[AX_J3_ELBOW] + q[AX_J4_WRIST]) * d2r;
    float c2 = cosf(t2), s2 = sinf(t2);
    float c23 = cosf(t23), s23 = sinf(t23);
    float c234 = cosf(t234), s234 = sinf(t234);

    float r3 = DH_A2_MM * c2;
    float z3 = DH_D1_MM + DH_A2_MM * s2;
    float r4 = r3 + DH_A3_MM * c23;
    float z4 = z3 + DH_A3_MM * s23;

    static const float L3_PTS[6][2] = {
        {15.0f, -14.0f}, {35.0f, -14.0f}, {55.0f, -14.0f}, {70.0f, -18.2f},
        {35.0f, +14.0f}, {70.0f, +18.2f}
    };
    float zMin = 9999.0f;
    for (int i = 0; i < 6; i++) {
        float rr = r3 + L3_PTS[i][0] * c23 - L3_PTS[i][1] * s23;
        float zz = z3 + L3_PTS[i][0] * s23 + L3_PTS[i][1] * c23;
        if (zz < zMin) zMin = zz;
        if ((zz < GUARD_BASE_DRUM_Z_MM && fabsf(rr) < GUARD_BASE_DRUM_R_MM) ||
            (zz < GUARD_BASE_NECK_Z_MM && fabsf(rr) < GUARD_BASE_NECK_R_MM)) {
            if (zMinOut) *zMinOut = zMin;
            if (reasonOut) *reasonOut = "Antebrazo L3 chocaria con la base";
            return false;
        }
    }
    if (zMin < GUARD_FLOOR_Z_MIN_MM) {
        if (zMinOut) *zMinOut = zMin;
        if (reasonOut) *reasonOut = "Antebrazo/Muneca chocaria con mesa";
        return false;
    }

    float tcpX = gripMmToTcpX(q[AX_GRIPPER]);
    float tipX = tcpX + GUARD_FINGER_TIP_EXTRA_MM;
    const float L4_PTS[7][2] = {
        { 0.0f, -16.2f },
        { 21.6f, GUARD_L4_SG90_Z_MM },
        { 34.5f, GUARD_L4_SG90_Z_MM },
        { 35.9f, +16.2f },
        { tcpX,  -1.5f },
        { tipX,  -1.5f },
        { tipX, +13.8f }
    };
    float zMin4 = 9999.0f;
    for (int i = 0; i < 7; i++) {
        float rr = r4 + L4_PTS[i][0] * c234 - L4_PTS[i][1] * s234;
        float zz = z4 + L4_PTS[i][0] * s234 + L4_PTS[i][1] * c234;
        if (zz < zMin4) zMin4 = zz;
        if (zz < zMin)  zMin  = zz;
        if ((zz < GUARD_BASE_DRUM_Z_MM && fabsf(rr) < GUARD_BASE_DRUM_R_MM) ||
            (zz < GUARD_BASE_NECK_Z_MM && fabsf(rr) < GUARD_BASE_NECK_R_MM)) {
            if (zMinOut) *zMinOut = zMin;
            if (reasonOut) *reasonOut = "Pinza/SG90 chocaria con la base";
            return false;
        }
        float dz = zz - DH_D1_MM;
        float xL2 = rr * c2 + dz * s2;
        float zL2 = -rr * s2 + dz * c2;
        if (xL2 > 8.0f && xL2 < 72.0f && fabsf(zL2) < 14.0f) {
            if (zMinOut) *zMinOut = zMin;
            if (reasonOut) *reasonOut = "Pinza/SG90 chocaria con brazo L2";
            return false;
        }
    }
    if (zMinOut) *zMinOut = zMin;
    if (zMin4 < GUARD_FLOOR_Z_MIN_MM) {
        if (reasonOut) *reasonOut = "Pinza/SG90 chocaria con mesa";
        return false;
    }
    if (reasonOut) *reasonOut = "OK";
    return true;
}
