/*
 * ============================================================================
 * FIRMWARE MINI-PRO 4-DOF (`B2 STEALTH` v4 Clean-DFA) — XIAO ESP32-S3 / C3
 * ============================================================================
 * Correcciones integradas de la auditoría técnica (Codex):
 *   1. Deshabilitación inmediata de salidas PWM (`FULL_OFF = 4096`) al arrancar
 *      o reiniciar, antes de habilitar la frecuencia del PCA9685.
 *   2. Resincronización real de `qCurr[]` / `qTarget[]` tras `CENTER` y `RAW`,
 *      más rampa suave obligatoria al reactivar torque desde `RELAX`.
 *   3. Conversión trigonométrica exacta de la pinza paralela MeArm módulo 1.5
 *      (`gripMmToServoDeg`) compartida con `cad/params.py` y el Gemelo Digital.
 *   4. Guarda cinemática anti-mesa (`checkTableGuard`): bloquea poses donde
 *      J3/J4 < 22 mm o TCP < 8 mm (impide estrellar el brazo contra el escritorio).
 */

#include <math.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <Adafruit_PWMServoDriver.h>

#include "config.h"
#include "web_ui.h"

Adafruit_PWMServoDriver pwm(PCA9685_ADDR);
WebServer server(80);
WiFiUDP udp;

float qCurr[5]   = { 0.0f, 90.0f, -90.0f, 0.0f, 15.0f };
float qStart[5]  = { 0.0f, 90.0f, -90.0f, 0.0f, 15.0f };
float qTarget[5] = { 0.0f, 90.0f, -90.0f, 0.0f, 15.0f };

bool     isRelaxed     = true;
bool     streamMode    = false;
bool     trajActive    = false;
uint32_t trajStartMs   = 0;
uint32_t trajDurMs     = 1100;
uint32_t lastTickMs    = 0;

struct Waypoint { float q[5]; uint32_t ms; };
static const Waypoint DEMO_SEQ[] = {
    { {   0.0f,  90.0f,  -90.0f,   0.0f, 24.0f }, 1000 },
    { { -25.7f,  57.4f,  -98.6f,  41.2f, 24.0f }, 1100 },
    { { -25.7f,  36.5f, -100.3f,  63.8f, 24.0f },  900 },
    { { -25.7f,  36.5f, -100.3f,  63.8f,  6.0f },  550 },
    { { -25.7f,  57.4f,  -98.6f,  41.2f,  6.0f },  900 },
    { {   0.0f,  69.8f,  -94.3f,  24.4f,  6.0f }, 1100 },
    { {  25.7f,  57.4f,  -98.6f,  41.2f,  6.0f }, 1100 },
    { {  25.7f,  36.5f, -100.3f,  63.8f,  6.0f },  900 },
    { {  25.7f,  36.5f, -100.3f,  63.8f, 24.0f },  550 },
    { {  25.7f,  57.4f,  -98.6f,  41.2f, 24.0f },  850 },
    { {   0.0f,  68.0f,  -96.0f,  28.0f, 15.0f }, 1100 },
};
static const int DEMO_LEN = sizeof(DEMO_SEQ) / sizeof(DEMO_SEQ[0]);
bool demoRunning = false;
int  demoIdx     = 0;
String lastMsg   = "Listo (FK + IK activos)";
bool   lastOk    = true;

// ----------------------------------------------------------------------------
// Utilidades PWM, Conversión Inversa (Resincronización) y Guarda Anti-Mesa
// ----------------------------------------------------------------------------
static inline float clampf(float v, float lo, float hi) {
    return (v < lo) ? lo : ((v > hi) ? hi : v);
}

static inline uint32_t clampMoveMs(long ms) {
    return (ms < 150L) ? 150U : (uint32_t)ms;
}

static bool checkTableGuard(const float q[5], String* reasonOut = nullptr, float* zMinOut = nullptr) {
    return checkPhysicalGuard(q, reasonOut, zMinOut);
}

static bool validateQuinticPath(const float q0[5], const float q1[5], String* reasonOut = nullptr, float* zMinOut = nullptr) {
    // Valida la trayectoria completa en 16 muestras quínticas (evita que curvas intermedias rocen mesa/base!)
    float qSample[5];
    for (int k = 1; k <= 16; k++) {
        float u = (float)k / 16.0f;
        float s = u * u * u * (10.0f - 15.0f * u + 6.0f * u * u);
        for (uint8_t i = 0; i < 5; i++) {
            qSample[i] = q0[i] + s * (q1[i] - q0[i]);
        }
        if (!checkTableGuard(qSample, reasonOut, zMinOut)) {
            return false;
        }
    }
    return true;
}

void writeMicros(uint8_t ch, uint16_t us) {
    us = (uint16_t)clampf((float)us, 450.0f, 2550.0f);
    uint16_t ticks = (uint16_t)roundf((us * 4096.0f) / 20000.0f);
    pwm.setPWM(ch, 0, ticks);
}

static float logicalToServoDeg(uint8_t idx, float qVal) {
    const ServoAxisConfig& cfg = AXES[idx];
    float qClamped = clampf(qVal, cfg.q_min, cfg.q_max);
    float servoDeg = (idx == AX_GRIPPER)
        ? gripMmToServoDeg(qClamped)
        : (cfg.servo_zero_deg + (cfg.invert ? -qClamped : qClamped));
    return clampf(servoDeg + cfg.offset_deg, 0.0f, 180.0f);
}

static float servoUsToLogical(uint8_t idx, uint16_t us) {
    const ServoAxisConfig& cfg = AXES[idx];
    float sdeg = ((float)us - (float)cfg.us_min) / (float)(cfg.us_max - cfg.us_min) * 180.0f;
    sdeg = clampf(sdeg - cfg.offset_deg, 0.0f, 180.0f);
    float q;
    if (idx == AX_GRIPPER) {
        q = servoDegToGripMm(sdeg);
    } else {
        float diff = sdeg - cfg.servo_zero_deg;
        q = cfg.invert ? -diff : diff;
    }
    return clampf(q, cfg.q_min, cfg.q_max);
}

void writeAxisLogical(uint8_t idx, float qVal) {
    const ServoAxisConfig& cfg = AXES[idx];
    float servoDeg = logicalToServoDeg(idx, qVal);
    uint16_t us = (uint16_t)roundf(cfg.us_min + (servoDeg / 180.0f) * (cfg.us_max - cfg.us_min));
    writeMicros(cfg.channel, us);
}

void applyCurrentPose() {
    for (uint8_t i = 0; i < 5; i++) {
        writeAxisLogical(i, qCurr[i]);
    }
}

void disableAllOutputsRaw() {
    // Bit FULL_OFF (4096 = 0x1000) real del PCA9685 en los 16 canales (cero pulsos!)
    for (uint8_t ch = 0; ch < 16; ch++) {
        pwm.setPWM(ch, 0, 4096);
    }
}

void relaxAll() {
    demoRunning = false;
    trajActive  = false;
    streamMode  = false;
    isRelaxed   = true;
    disableAllOutputsRaw();
    Serial.println(F("[OK] Servos relajados (FULL_OFF 4096, sin torque)."));
}

void centerBench90() {
    demoRunning = false;
    trajActive  = false;
    streamMode  = false;
    isRelaxed   = false;
    for (uint8_t i = 0; i < 4; i++) {
        writeMicros(AXES[i].channel, 1500);
        // Resincronización exacta para evitar latigazos en el siguiente comando!
        qCurr[i] = qTarget[i] = qStart[i] = servoUsToLogical(i, 1500);
    }
    qCurr[AX_GRIPPER] = qTarget[AX_GRIPPER] = qStart[AX_GRIPPER] = GRIP_NOMINAL_OPEN_MM;
    writeAxisLogical(AX_GRIPPER, GRIP_NOMINAL_OPEN_MM);
    Serial.printf("[OK] CENTER: CH0..CH3=1500us (resincronizado q=[%.1f, %.1f, %.1f, %.1f], grip=%.1f mm)\n",
                  qCurr[0], qCurr[1], qCurr[2], qCurr[3], qCurr[4]);
}

bool startQuinticMove(const float tgt[5], uint32_t durationMs) {
    for (uint8_t i = 0; i < 5; i++) {
        if (!isfinite(tgt[i])) {
            lastOk = false;
            lastMsg = "Entrada no finita (NaN/Inf)";
            return false;
        }
    }
    float clamped[5];
    for (uint8_t i = 0; i < 5; i++) {
        clamped[i] = clampf(tgt[i], AXES[i].q_min, AXES[i].q_max);
    }
    String gReason;
    float zMin = 0.0f;
    if (!checkTableGuard(clamped, &gReason, &zMin)) {
        lastOk = false;
        lastMsg = gReason;
        Serial.printf("[GUARD] Destino bloqueado: %s (Z_min=%.1f mm)\n", gReason.c_str(), zMin);
        return false;
    }
    if (!validateQuinticPath(qCurr, clamped, &gReason, &zMin)) {
        lastOk = false;
        lastMsg = "Trayectoria bloqueada: " + gReason;
        Serial.printf("[GUARD] Trayectoria bloqueada: %s (Z_min=%.1f mm)\n", gReason.c_str(), zMin);
        return false;
    }

    bool wasRelaxed = isRelaxed;
    isRelaxed   = false;
    streamMode  = false;
    trajActive  = true;
    trajStartMs = millis();
    uint32_t minDur = wasRelaxed ? (uint32_t)MIN_WAKE_MOVE_MS : 120U;
    trajDurMs   = (durationMs < minDur) ? minDur : durationMs;

    for (uint8_t i = 0; i < 5; i++) {
        qStart[i]  = qCurr[i];
        qTarget[i] = clamped[i];
    }
    if (wasRelaxed) {
        Serial.printf("[INFO] Reactivando desde RELAX con rampa quintica obligatoria (%lu ms).\n", (unsigned long)trajDurMs);
    }
    return true;
}

bool setStreamTarget(const float tgt[5]) {
    for (uint8_t i = 0; i < 5; i++) {
        if (!isfinite(tgt[i])) {
            lastOk = false;
            lastMsg = "Entrada no finita (NaN/Inf)";
            return false;
        }
    }
    // Ronda 2 P0-5: JAMÁS evadir la rampa obligatoria de 1200 ms al reactivar desde RELAX!
    if (isRelaxed) {
        return startQuinticMove(tgt, (uint32_t)MIN_WAKE_MOVE_MS);
    }
    float clamped[5];
    for (uint8_t i = 0; i < 5; i++) {
        clamped[i] = clampf(tgt[i], AXES[i].q_min, AXES[i].q_max);
    }
    String gReason;
    float zMin = 0.0f;
    if (!checkTableGuard(clamped, &gReason, &zMin)) {
        lastOk = false;
        lastMsg = gReason;
        Serial.printf("[GUARD] Streaming bloqueado: %s (Z_min=%.1f mm)\n", gReason.c_str(), zMin);
        return false;
    }
    demoRunning = false;
    trajActive  = false;
    streamMode  = true;
    for (uint8_t i = 0; i < 5; i++) {
        qTarget[i] = clamped[i];
    }
    return true;
}

void startDemo() {
    demoRunning = true;
    demoIdx     = 0;
    if (!startQuinticMove(DEMO_SEQ[0].q, DEMO_SEQ[0].ms)) {
        demoRunning = false;
        return;
    }
    Serial.println(F("[OK] Iniciando Demo Pick-and-Place suave."));
}

String getCurrentIP() {
    return (WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString() : WiFi.softAPIP().toString();
}

void printStatus() {
    float fx = 0, fy = 0, fz = 0, fphi = 0;
    computeFK(qCurr, fx, fy, fz, fphi);
    Serial.printf("[STATUS] q=[%.1f, %.1f, %.1f, %.1f] deg | grip=%.1f mm | TCP=(%.1f, %.1f, %.1f) mm phi=%.1f deg | relaxed=%d | IP=%s\n",
                  qCurr[0], qCurr[1], qCurr[2], qCurr[3], qCurr[4],
                  fx, fy, fz, fphi, isRelaxed ? 1 : 0, getCurrentIP().c_str());
}

bool moveByIK(float x_mm, float y_mm, float z_mm, float phi_deg, float grip_mm, uint32_t durationMs, bool streaming) {
    float qSol[4];
    String ikErr;
    if (!computeIK(x_mm, y_mm, z_mm, phi_deg, qSol, &ikErr, true, qCurr[0])) {
        lastOk  = false;
        lastMsg = "IK: " + ikErr;
        Serial.printf("[IK ERR] (%.1f, %.1f, %.1f, phi=%.1f): %s\n", x_mm, y_mm, z_mm, phi_deg, ikErr.c_str());
        return false;
    }
    if (!isfinite(grip_mm)) {
        lastOk  = false;
        lastMsg = "Pinza no finita (NaN/Inf)";
        return false;
    }
    float tgt[5] = { qSol[0], qSol[1], qSol[2], qSol[3], clampf(grip_mm, AXES[4].q_min, AXES[4].q_max) };
    bool ok = streaming ? setStreamTarget(tgt) : startQuinticMove(tgt, durationMs);
    if (!ok) {
        return false;
    }
    demoRunning = false;
    lastOk  = true;
    lastMsg = "IK OK -> q=[" + String(qSol[0], 1) + ", " + String(qSol[1], 1) + ", " + String(qSol[2], 1) + ", " + String(qSol[3], 1) + "]";
    if (!streaming) {
        Serial.printf("[IK OK] (%.1f, %.1f, %.1f, phi=%.1f) -> q=[%.1f, %.1f, %.1f, %.1f] en %lu ms\n",
                      x_mm, y_mm, z_mm, phi_deg, qSol[0], qSol[1], qSol[2], qSol[3], (unsigned long)durationMs);
    }
    return true;
}

// ----------------------------------------------------------------------------
// Parser unificado de comandos (USB Serial + Wi-Fi UDP)
// ----------------------------------------------------------------------------
void processCommand(String line) {
    line.trim();
    if (line.length() == 0) return;

    String up = line;
    up.toUpperCase();

    if (up == "HERO") {
        demoRunning = false;
        float tgt[5] = { AXES[0].q_hero, AXES[1].q_hero, AXES[2].q_hero, AXES[3].q_hero, AXES[4].q_hero };
        if (startQuinticMove(tgt, (uint32_t)DEFAULT_MOVE_MS)) {
            lastOk = true; lastMsg = "Pose Heroe";
            Serial.println(F("[OK] Moviendo a Pose Heroe."));
        }
    } else if (up == "HOME") {
        demoRunning = false;
        float tgt[5] = { AXES[0].q_home, AXES[1].q_home, AXES[2].q_home, AXES[3].q_home, AXES[4].q_home };
        if (startQuinticMove(tgt, (uint32_t)DEFAULT_MOVE_MS)) {
            lastOk = true; lastMsg = "Home Vertical";
            Serial.println(F("[OK] Moviendo a Home."));
        }
    } else if (up == "CENTER") {
        centerBench90();
        lastOk = true; lastMsg = "CENTER 1500us";
    } else if (up == "DEMO") {
        startDemo();
        lastOk = true; lastMsg = "Demo Pick & Place";
    } else if (up == "RELAX") {
        relaxAll();
        lastOk = true; lastMsg = "Servos relajados";
    } else if (up == "STATUS" || up == "FK") {
        printStatus();
    } else if (up.startsWith("IKG ")) {
        float x, y, z, phi, g = qCurr[4];
        int n = sscanf(line.c_str() + 4, "%f %f %f %f %f", &x, &y, &z, &phi, &g);
        if (n >= 4) moveByIK(x, y, z, phi, g, 0, true);
    } else if (up.startsWith("IK ")) {
        float x, y, z, phi, g = qCurr[4];
        long ms = (long)DEFAULT_MOVE_MS;
        int n = sscanf(line.c_str() + 3, "%f %f %f %f %f %ld", &x, &y, &z, &phi, &g, &ms);
        if (n >= 4) {
            moveByIK(x, y, z, phi, g, clampMoveMs(ms), false);
        } else {
            Serial.println(F("[ERR] Uso: IK x y z phi [grip_mm] [ms]"));
        }
    } else if (up.startsWith("G ")) {
        float t[5];
        if (sscanf(line.c_str() + 2, "%f %f %f %f %f", &t[0], &t[1], &t[2], &t[3], &t[4]) == 5) {
            lastOk = setStreamTarget(t);
            if (lastOk) lastMsg = "FK activo";
        }
    } else if (up.startsWith("M ")) {
        float t[5];
        long ms = (long)DEFAULT_MOVE_MS;
        if (sscanf(line.c_str() + 2, "%f %f %f %f %f %ld", &t[0], &t[1], &t[2], &t[3], &t[4], &ms) >= 5) {
            demoRunning = false;
            lastOk = startQuinticMove(t, clampMoveMs(ms));
            if (lastOk) lastMsg = "Movimiento FK quintico";
        }
    } else if (up.startsWith("RAW ")) {
        int ch = 0, us = 1500;
        if (sscanf(line.c_str() + 4, "%d %d", &ch, &us) == 2 && ch >= 0 && ch < 16) {
            demoRunning = false; trajActive = false; streamMode = false; isRelaxed = false;
            writeMicros((uint8_t)ch, (uint16_t)us);
            for (uint8_t i = 0; i < 5; i++) {
                if (AXES[i].channel == (uint8_t)ch) {
                    qCurr[i] = qTarget[i] = qStart[i] = servoUsToLogical(i, (uint16_t)us);
                }
            }
            lastOk = true; lastMsg = "RAW OK";
            Serial.printf("[OK] RAW CH%d -> %d us (resincronizado)\n", ch, us);
        }
    } else {
        Serial.printf("[ERR] Comando desconocido: %s (usa HERO|HOME|CENTER|DEMO|RELAX|FK|G|M|IK|IKG|RAW)\n", line.c_str());
    }
}

// ----------------------------------------------------------------------------
// Endpoints HTTP Web UI (FK + IK en vivo!)
// ----------------------------------------------------------------------------
String buildStatusJson() {
    float fx = 0, fy = 0, fz = 0, fphi = 0;
    float gx = 0, gy = 0, gz = 0;
    computeFK(qCurr, fx, fy, fz, fphi);
    computeGripPointFK(qCurr, gx, gy, gz);
    String j = "{\"q\":[";
    for (int i = 0; i < 5; i++) {
        j += String(qCurr[i], 1);
        if (i < 4) j += ",";
    }
    j += "],\"xyz\":[" + String(fx, 1) + "," + String(fy, 1) + "," + String(fz, 1) + "," + String(fphi, 1) + "]";
    j += ",\"grip_xyz\":[" + String(gx, 1) + "," + String(gy, 1) + "," + String(gz, 1) + "]";
    j += ",\"relaxed\":" + String(isRelaxed ? "true" : "false");
    j += ",\"ok\":" + String(lastOk ? "true" : "false");
    j += ",\"msg\":\"" + lastMsg + "\"";
    j += ",\"ip\":\"" + getCurrentIP() + "\"}";
    return j;
}

void setupWebServer() {
    server.on("/", HTTP_GET, []() { server.send_P(200, "text/html", WEB_UI_HTML); });
    server.on("/api/status", HTTP_GET, []() { server.send(200, "application/json", buildStatusJson()); });
    server.on("/api/move", HTTP_GET, []() {
        float t[5] = {
            server.hasArg("q0") ? server.arg("q0").toFloat() : qTarget[0],
            server.hasArg("q1") ? server.arg("q1").toFloat() : qTarget[1],
            server.hasArg("q2") ? server.arg("q2").toFloat() : qTarget[2],
            server.hasArg("q3") ? server.arg("q3").toFloat() : qTarget[3],
            server.hasArg("g")  ? server.arg("g").toFloat()  : qTarget[4]
        };
        lastOk = setStreamTarget(t);
        if (lastOk) lastMsg = "FK OK";
        server.send(200, "application/json", buildStatusJson());
    });
    server.on("/api/ik", HTTP_GET, []() {
        float fx = 0, fy = 0, fz = 0, fphi = 0;
        computeFK(qCurr, fx, fy, fz, fphi);
        float x   = server.hasArg("x")   ? server.arg("x").toFloat()   : fx;
        float y   = server.hasArg("y")   ? server.arg("y").toFloat()   : fy;
        float z   = server.hasArg("z")   ? server.arg("z").toFloat()   : fz;
        float phi = server.hasArg("phi") ? server.arg("phi").toFloat() : fphi;
        float g   = server.hasArg("g")   ? server.arg("g").toFloat()   : qCurr[4];
        uint32_t ms = server.hasArg("ms") ? clampMoveMs(server.arg("ms").toInt()) : (uint32_t)DEFAULT_MOVE_MS;
        bool stream = server.hasArg("stream") && (server.arg("stream") == "1");
        moveByIK(x, y, z, phi, g, ms, stream);
        server.send(200, "application/json", buildStatusJson());
    });
    server.on("/api/cmd", HTTP_GET, []() {
        if (server.hasArg("c")) processCommand(server.arg("c"));
        server.send(200, "application/json", buildStatusJson());
    });
    server.begin();
}

void setupWiFi() {
    if (strlen(WIFI_STA_SSID) > 0) {
        WiFi.mode(WIFI_STA);
        WiFi.begin(WIFI_STA_SSID, WIFI_STA_PASS);
        Serial.printf("[WiFi] Conectando a %s", WIFI_STA_SSID);
        uint32_t t0 = millis();
        while (WiFi.status() != WL_CONNECTED && millis() - t0 < 8000) {
            delay(250);
            Serial.print('.');
        }
        Serial.println();
        if (WiFi.status() == WL_CONNECTED) {
            Serial.printf("[OK] Wi-Fi conectado! IP: http://%s/\n", WiFi.localIP().toString().c_str());
            return;
        }
        Serial.println(F("[WARN] No conecto a STA, iniciando modo AP local..."));
    }
    WiFi.mode(WIFI_AP);
    WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASS);
    Serial.printf("[OK] Red AP activa: %s (pass: %s) -> http://%s/\n",
                  WIFI_AP_SSID, WIFI_AP_PASS, WiFi.softAPIP().toString().c_str());
}

// ----------------------------------------------------------------------------
// SETUP & LOOP (100 Hz)
// ----------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    delay(250);
    Serial.println(F("\n=== MINI-PRO 4-DOF B2 STEALTH v4 (XIAO ESP32 + PCA9685) ==="));

    Wire.begin();
    Wire.setClock(400000);

    Wire.beginTransmission(PCA9685_ADDR);
    if (Wire.endTransmission() == 0) {
        Serial.println(F("[OK] PCA9685 detectado en 0x40."));
    } else {
        Serial.println(F("[ERR] No se detecta PCA9685 en 0x40! Revisa 3V3->VCC, SDA->D4, SCL->D5 y GND."));
    }

    // Secuencia de arranque segura ante reinicios en caliente:
    // Apagar salidas (FULL_OFF=4096) INMEDIATAMENTE al inicializar antes de habilitar 50 Hz!
    pwm.begin();
    disableAllOutputsRaw();
    pwm.setOscillatorFrequency(27000000);
    pwm.setPWMFreq(SERVO_FREQ_HZ);
    disableAllOutputsRaw();
    isRelaxed = true;
    Serial.println(F("[OK] Arranque seguro: salidas PWM deshabilitadas (FULL_OFF) en reinicio."));

    setupWiFi();
    udp.begin(UDP_PORT);
    setupWebServer();
    Serial.printf("[OK] Escuchando USB Serial (115200) y UDP puerto %u.\n", UDP_PORT);
}

void loop() {
    server.handleClient();

    // 1. Leer comandos por USB Serial
    static String serBuf;
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (serBuf.length() > 0) {
                processCommand(serBuf);
                serBuf = "";
            }
        } else if (serBuf.length() < 96) {
            serBuf += c;
        }
    }

    // 2. Leer paquetes UDP (Wi-Fi puerto 4210)
    int pktSize = udp.parsePacket();
    if (pktSize > 0) {
        char buf[128];
        int n = udp.read(buf, sizeof(buf) - 1);
        if (n > 0) {
            buf[n] = '\0';
            String cmd(buf);
            cmd.trim();
            processCommand(cmd);
            if (cmd.equalsIgnoreCase("STATUS")) {
                String resp = buildStatusJson();
                udp.beginPacket(udp.remoteIP(), udp.remotePort());
                udp.print(resp);
                udp.endPacket();
            }
        }
    }

    // 3. Lazo de control determinista a 100 Hz
    uint32_t now = millis();
    if (now - lastTickMs < CONTROL_PERIOD_MS) return;
    lastTickMs = now;

    if (isRelaxed) return;

    if (trajActive) {
        float u = clampf((float)(now - trajStartMs) / (float)trajDurMs, 0.0f, 1.0f);
        float s = u * u * u * (10.0f - 15.0f * u + 6.0f * u * u);
        float qNext[5];
        for (uint8_t i = 0; i < 5; i++) {
            qNext[i] = qStart[i] + s * (qTarget[i] - qStart[i]);
        }
        String gReason;
        if (!checkTableGuard(qNext, &gReason)) {
            trajActive = false;
            demoRunning = false;
            lastOk = false;
            lastMsg = "Detenido en paso interpolado: " + gReason;
            Serial.printf("[GUARD] Detenido en interpolacion: %s\n", gReason.c_str());
            return;
        }
        for (uint8_t i = 0; i < 5; i++) qCurr[i] = qNext[i];
        applyCurrentPose();
        if (u >= 1.0f) {
            trajActive = false;
            if (demoRunning) {
                demoIdx++;
                if (demoIdx < DEMO_LEN) {
                    startQuinticMove(DEMO_SEQ[demoIdx].q, DEMO_SEQ[demoIdx].ms);
                } else {
                    demoRunning = false;
                    Serial.println(F("[OK] Demo completada."));
                }
            }
        }
    } else if (streamMode) {
        float qNext[5];
        for (uint8_t i = 0; i < 5; i++) {
            qNext[i] = qCurr[i] + STREAM_ALPHA * (qTarget[i] - qCurr[i]);
        }
        String gReason;
        if (checkTableGuard(qNext, &gReason)) {
            for (uint8_t i = 0; i < 5; i++) qCurr[i] = qNext[i];
            applyCurrentPose();
        } else {
            streamMode = false;
            lastOk = false;
            lastMsg = "Stream detenido: " + gReason;
            Serial.printf("[GUARD] Stream detenido en paso intermedio: %s\n", gReason.c_str());
        }
    }
}
