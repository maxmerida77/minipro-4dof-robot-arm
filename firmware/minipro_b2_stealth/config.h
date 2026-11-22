#pragma once
#include <Arduino.h>

// ============================================================================
// CONFIGURACIÓN Y CALIBRACIÓN — MINI-PRO 4-DOF (`B2 STEALTH` · XIAO ESP32-S3/C3)
// ============================================================================
// Sincronizado con `cad/params.py` y `python/robot_minipro_rtb.py`.
// Ajusta aquí únicamente `us_min`, `us_max`, `offset_deg` o `invert` durante
// la calibración en banco sin tocar el código principal.

// --- Red Wi-Fi ---
// Modo 1 (Station — recomendado para Peter Corke por Wi-Fi con 1 solo cable USB-C):
//   Escribe el SSID y contraseña de tu Wi-Fi local. Si queda vacío o falla en 8 s,
//   la XIAO levanta automáticamente su propia red AP "MiniPro-B2-Stealth" (192.168.4.1).
static const char* WIFI_STA_SSID = "";
static const char* WIFI_STA_PASS = "";

static const char* WIFI_AP_SSID  = "MiniPro-B2-Stealth";
static const char* WIFI_AP_PASS  = "minipro1234";

// Puerto UDP para control en vivo desde `python/gemelo_digital_esp32.py --wifi <IP>`
static const uint16_t UDP_PORT = 4210;

// --- PCA9685 ---
static const uint8_t  PCA9685_ADDR = 0x40;
static const float    SERVO_FREQ_HZ = 50.0f;  // Período 20,000 µs

// --- Interpolador Suave (S-Curve / Quíntico tipo Peter Corke jtraj) ---
static const uint32_t CONTROL_PERIOD_MS = 10;     // 100 Hz
static const float    DEFAULT_MOVE_MS   = 900.0f; // Duración por defecto de movimientos suaves
static const float    STREAM_ALPHA      = 0.28f;  // Suavizado ligero para streaming vivo (25-50 Hz)

// --- Tabla de Calibración por Eje (CH0..CH4) ---
// Mapeo lineal: ángulo físico del servo = clamp(logical_to_servo(q_deg) + offset_deg, 0, 180)
struct ServoAxisConfig {
    uint8_t channel;
    float   q_min;          // Límite lógico inferior (° o mm en pinza)
    float   q_max;          // Límite lógico superior (° o mm en pinza)
    float   q_home;         // Postura de reposo segura
    float   q_hero;         // Pose Héroe CAD/Peter Corke
    float   servo_zero_deg; // Ángulo físico del servo (0..180°) cuando q lógico = 0
    float   offset_deg;     // Ajuste fino mecánico al atornillar el horn (±15°)
    bool    invert;         // true si el servo gira en sentido opuesto al DH
    uint16_t us_min;        // Pulso µs para 0° físico (típico MG90S: 500..600 µs)
    uint16_t us_max;        // Pulso µs para 180° físico (típico MG90S: 2400..2500 µs)
};

// Índices del arreglo AXES[5]
enum AxisIndex : uint8_t {
    AX_J1_BASE = 0,
    AX_J2_SHOULDER = 1,
    AX_J3_ELBOW = 2,
    AX_J4_WRIST = 3,
    AX_GRIPPER = 4
};

// Calibración inicial segura para 4× MG90S (UNIT AR1240) + 1× SG90 en Pinza:
//   J1 Base   : q1 in [-90, +90]   -> servo = 90 + q1   (0° lógico = 90° servo)
//   J2 Hombro : q2 in [ 15, 165]   -> servo = q2        (90° vertical = 90° servo)
//   J3 Codo   : q3 in [-135, +45]  -> servo = 135 + q3  (-45° medio = 90° servo)
//   J4 Muñeca : q4 in [-90, +90]   -> servo = 90 + q4   (0° alineado = 90° servo)
//   Pinza SG90: grip in [0, 30 mm] -> 0 mm cerrado (~40° servo) a 30 mm abierto (~130° servo)
static ServoAxisConfig AXES[5] = {
    // ch,  q_min,  q_max, q_home, q_hero, zero_deg, offset, invert, us_min, us_max
    {   0,  -90.0f,  90.0f,   0.0f,   0.0f,   90.0f,   0.0f,  false,   550,   2450 }, // J1 Base
    {   1,   15.0f, 165.0f,  90.0f,  68.0f,    0.0f,   0.0f,  false,   550,   2450 }, // J2 Hombro
    {   2, -135.0f,  45.0f, -90.0f, -96.0f,  135.0f,   0.0f,  false,   550,   2450 }, // J3 Codo
    {   3,  -90.0f,  90.0f,   0.0f,  28.0f,   90.0f,   0.0f,  false,   550,   2450 }, // J4 Muñeca
    {   4,    0.0f,  30.0f,  18.0f,  16.0f,   40.0f,   0.0f,  false,   600,   2400 }, // Pinza SG90 (3°/mm)
};

// Factor de conversión mm -> grados del SG90 de la pinza (30 mm -> 90° de giro de engrane 14T)
static const float GRIPPER_DEG_PER_MM = 3.0f;
