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

// --- Parámetros Cinemáticos DH (mm) y Guarda Anti-Mesa ---
static const float DH_D1_MM              = 82.0f;
static const float DH_A2_MM              = 82.0f;
static const float DH_A3_MM              = 70.0f;
static const float DH_A4_MM              = 53.0f;
static const float TABLE_SAFE_Z_TCP_MM   = 8.0f;
static const float TABLE_SAFE_Z_JOINT_MM = 22.0f;

// --- Geometría Exacta Pinza Paralela Abierta MeArm Módulo 1.5 (idéntica a `cad/params.py`) ---
static const float GRIP_LINK_L_MM         = 16.5f;  // Longitud centro-a-centro brazos/bielas
static const float GRIP_NOMINAL_OPEN_MM   = 15.0f;  // Apertura donde centro almohadillas == A4 (53.0 mm)
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
static ServoAxisConfig AXES[5] = {
    // ch,  q_min,  q_max, q_home, q_hero, zero_deg, offset, invert, us_min, us_max
    {   0,  -90.0f,  90.0f,   0.0f,   0.0f,   90.0f,   0.0f,  false,   550,   2450 }, // J1 Base
    {   1,   15.0f, 165.0f,  90.0f,  68.0f,    0.0f,   0.0f,  false,   550,   2450 }, // J2 Hombro
    {   2, -135.0f,  45.0f, -90.0f, -96.0f,  135.0f,   0.0f,  false,   550,   2450 }, // J3 Codo
    {   3,  -90.0f,  90.0f,   0.0f,  28.0f,   90.0f,   0.0f,  false,   550,   2450 }, // J4 Muñeca
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
