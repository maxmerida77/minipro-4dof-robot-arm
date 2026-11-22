/*
 * ============================================================================
 * FIRMWARE MINI-PRO 4-DOF (`B2 STEALTH`) — XIAO ESP32-S3 / XIAO ESP32-C3
 * ============================================================================
 * Hardware:
 *   - XIAO ESP32-S3 (ó C3) + PCA9685 (0x40, I2C D4/D5) + 4× MG90S + 1× SG90
 *   - Alimentación: 1 cable USB-C desde UGREEN 50W -> AR5515 (5V) -> KCD11-2P
 *
 * Modos de control simultáneos:
 *   1) USB Serial (115200 baud) — `python python/gemelo_digital_esp32.py --port COMx`
 *   2) Wi-Fi UDP  (puerto 4210) — `python python/gemelo_digital_esp32.py --wifi <IP>`
 *      (¡Permite usar Peter Corke Python con 1 SOLO cable USB-C de corriente en el brazo!)
 *   3) Web UI Minimalista B2 Stealth (puerto 80) — `http://<IP>/` o `http://192.168.4.1/`
 *
 * Comandos ASCII (USB Serial y UDP):
 *   G <q1> <q2> <q3> <q4> <grip>        -> Streaming en vivo (suavizado)
 *   M <q1> <q2> <q3> <q4> <grip> <ms>   -> Movimiento quíntico (jtraj) en <ms> ms
 *   HERO                                -> Pose Héroe (0, 68, -96, 28, 16 mm)
 *   HOME                                -> Postura vertical segura (0, 90, -90, 0, 18 mm)
 *   CENTER                              -> Centra los 4 MG90S a 90° físicos (1500 µs) para armado
 *   DEMO                                -> Ejecuta secuencia Pick-and-Place suave
 *   RAW <ch> <us>                       -> Pulso directo en µs para calibrar en banco
 *   RELAX                               -> Apaga PWM (libera torque de los servos)
 *   STATUS                              -> Reporta estado, ángulos actuales e IP Wi-Fi
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

// Estado cinemático actual y objetivos
float qCurr[5]   = { 0.0f, 90.0f, -90.0f, 0.0f, 18.0f };
float qStart[5]  = { 0.0f, 90.0f, -90.0f, 0.0f, 18.0f };
float qTarget[5] = { 0.0f, 90.0f, -90.0f, 0.0f, 18.0f };

bool     isRelaxed     = true;
bool     streamMode    = false;
bool     trajActive    = false;
uint32_t trajStartMs   = 0;
uint32_t trajDurMs     = 900;
uint32_t lastTickMs    = 0;

// Secuencia Demo Pick-and-Place no bloqueante (ángulos IK exactos de Peter Corke a escala 82/82/70/53 mm, φ=0°)
struct Waypoint { float q[5]; uint32_t ms; };
static const Waypoint DEMO_SEQ[] = {
    { {   0.0f,  90.0f,  -90.0f,   0.0f, 24.0f },  800 }, // Home seguro con pinza abierta
    { { -25.7f,  57.4f,  -98.6f,  41.2f, 24.0f },  900 }, // Aproximación superior izquierda (135, -65, 105 mm)
    { { -25.7f,  36.5f, -100.3f,  63.8f, 24.0f },  700 }, // Descenso vertical Pick (135, -65, 68 mm, φ=0°)
    { { -25.7f,  36.5f, -100.3f,  63.8f,  6.0f },  450 }, // Cerrar pinza
    { { -25.7f,  57.4f,  -98.6f,  41.2f,  6.0f },  700 }, // Elevación vertical
    { {   0.0f,  69.8f,  -94.3f,  24.4f,  6.0f },  900 }, // Cruce central elevado (145, 0, 130 mm)
    { {  25.7f,  57.4f,  -98.6f,  41.2f,  6.0f },  900 }, // Aproximación superior derecha (135, +65, 105 mm)
    { {  25.7f,  36.5f, -100.3f,  63.8f,  6.0f },  700 }, // Descenso vertical Place (135, +65, 68 mm, φ=0°)
    { {  25.7f,  36.5f, -100.3f,  63.8f, 24.0f },  450 }, // Soltar pieza
    { {  25.7f,  57.4f,  -98.6f,  41.2f, 24.0f },  650 }, // Retirada vertical
    { {   0.0f,  68.0f,  -96.0f,  28.0f, 16.0f },  950 }, // Pose Héroe (145.5, 0, 125.2 mm)
};
static const int DEMO_LEN = sizeof(DEMO_SEQ) / sizeof(DEMO_SEQ[0]);
bool demoRunning = false;
int  demoIdx     = 0;

// ----------------------------------------------------------------------------
// Utilidades PWM (PCA9685 12-bit)
// ----------------------------------------------------------------------------
static inline float clampf(float v, float lo, float hi) {
    return (v < lo) ? lo : ((v > hi) ? hi : v);
}

void writeMicros(uint8_t ch, uint16_t us) {
    us = (uint16_t)clampf((float)us, 450.0f, 2550.0f);
    // 50 Hz -> 20,000 µs por ciclo de 4096 cuentas
    uint16_t ticks = (uint16_t)roundf((us * 4096.0f) / 20000.0f);
    pwm.setPWM(ch, 0, ticks);
}

void writeAxisLogical(uint8_t idx, float qVal) {
    const ServoAxisConfig& cfg = AXES[idx];
    float qClamped = clampf(qVal, cfg.q_min, cfg.q_max);
    float servoDeg;
    if (idx == AX_GRIPPER) {
        servoDeg = cfg.servo_zero_deg + qClamped * GRIPPER_DEG_PER_MM;
    } else {
        servoDeg = cfg.servo_zero_deg + (cfg.invert ? -qClamped : qClamped);
    }
    servoDeg = clampf(servoDeg + cfg.offset_deg, 0.0f, 180.0f);
    uint16_t us = (uint16_t)roundf(cfg.us_min + (servoDeg / 180.0f) * (cfg.us_max - cfg.us_min));
    writeMicros(cfg.channel, us);
}

void applyCurrentPose() {
    for (uint8_t i = 0; i < 5; i++) {
        writeAxisLogical(i, qCurr[i]);
    }
}

void relaxAll() {
    demoRunning = false;
    trajActive  = false;
    streamMode  = false;
    isRelaxed   = true;
    for (uint8_t i = 0; i < 5; i++) {
        pwm.setPWM(AXES[i].channel, 0, 0);
    }
    Serial.println(F("[OK] Servos relajados (sin torque)."));
}

void centerBench90() {
    demoRunning = false;
    trajActive  = false;
    streamMode  = false;
    isRelaxed   = false;
    for (uint8_t i = 0; i < 4; i++) {
        writeMicros(AXES[i].channel, 1500);
    }
    writeAxisLogical(AX_GRIPPER, 16.0f);
    Serial.println(F("[OK] CENTER: CH0..CH3 en 1500 us (90 deg mecanico). Ya puedes atornillar horns."));
}

void startQuinticMove(const float tgt[5], uint32_t durationMs) {
    isRelaxed   = false;
    streamMode  = false;
    trajActive  = true;
    trajStartMs = millis();
    trajDurMs   = (durationMs < 80) ? 80 : durationMs;
    for (uint8_t i = 0; i < 5; i++) {
        qStart[i]  = qCurr[i];
        qTarget[i] = clampf(tgt[i], AXES[i].q_min, AXES[i].q_max);
    }
}

void setStreamTarget(const float tgt[5]) {
    demoRunning = false;
    trajActive  = false;
    isRelaxed   = false;
    streamMode  = true;
    for (uint8_t i = 0; i < 5; i++) {
        qTarget[i] = clampf(tgt[i], AXES[i].q_min, AXES[i].q_max);
    }
}

void startDemo() {
    demoRunning = true;
    demoIdx     = 0;
    startQuinticMove(DEMO_SEQ[0].q, DEMO_SEQ[0].ms);
    Serial.println(F("[OK] Iniciando Demo Pick-and-Place."));
}

String getCurrentIP() {
    return (WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString() : WiFi.softAPIP().toString();
}

void printStatus() {
    Serial.printf("[STATUS] q=[%.1f, %.1f, %.1f, %.1f] deg | grip=%.1f mm | relaxed=%d | IP=%s\n",
                  qCurr[0], qCurr[1], qCurr[2], qCurr[3], qCurr[4],
                  isRelaxed ? 1 : 0, getCurrentIP().c_str());
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
        startQuinticMove(tgt, (uint32_t)DEFAULT_MOVE_MS);
        Serial.println(F("[OK] Moviendo a Pose Heroe."));
    } else if (up == "HOME") {
        demoRunning = false;
        float tgt[5] = { AXES[0].q_home, AXES[1].q_home, AXES[2].q_home, AXES[3].q_home, AXES[4].q_home };
        startQuinticMove(tgt, (uint32_t)DEFAULT_MOVE_MS);
        Serial.println(F("[OK] Moviendo a Home."));
    } else if (up == "CENTER") {
        centerBench90();
    } else if (up == "DEMO") {
        startDemo();
    } else if (up == "RELAX") {
        relaxAll();
    } else if (up == "STATUS") {
        printStatus();
    } else if (up.startsWith("G ")) {
        float t[5];
        if (sscanf(line.c_str() + 2, "%f %f %f %f %f", &t[0], &t[1], &t[2], &t[3], &t[4]) == 5) {
            setStreamTarget(t);
        }
    } else if (up.startsWith("M ")) {
        float t[5];
        int ms = 900;
        if (sscanf(line.c_str() + 2, "%f %f %f %f %f %d", &t[0], &t[1], &t[2], &t[3], &t[4], &ms) >= 5) {
            demoRunning = false;
            startQuinticMove(t, (uint32_t)max(100, ms));
        }
    } else if (up.startsWith("RAW ")) {
        int ch = 0, us = 1500;
        if (sscanf(line.c_str() + 4, "%d %d", &ch, &us) == 2 && ch >= 0 && ch < 16) {
            demoRunning = false; trajActive = false; streamMode = false; isRelaxed = false;
            writeMicros((uint8_t)ch, (uint16_t)us);
            Serial.printf("[OK] RAW CH%d -> %d us\n", ch, us);
        }
    } else {
        Serial.printf("[ERR] Comando desconocido: %s\n", line.c_str());
    }
}

// ----------------------------------------------------------------------------
// Endpoints HTTP Web UI
// ----------------------------------------------------------------------------
String buildStatusJson() {
    String j = "{\"q\":[";
    for (int i = 0; i < 5; i++) {
        j += String(qCurr[i], 1);
        if (i < 4) j += ",";
    }
    j += "],\"relaxed\":";
    j += (isRelaxed ? "true" : "false");
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
        setStreamTarget(t);
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
    delay(600);
    Serial.println(F("\n=== MINI-PRO 4-DOF B2 STEALTH (XIAO ESP32 + PCA9685) ==="));

    // I2C nativo de la XIAO ESP32-S3 (D4=SDA, D5=SCL) y XIAO ESP32-C3 (D4=SDA, D5=SCL)
    Wire.begin();
    Wire.setClock(400000);

    // Verificar presencia del PCA9685 en 0x40
    Wire.beginTransmission(PCA9685_ADDR);
    if (Wire.endTransmission() == 0) {
        Serial.println(F("[OK] PCA9685 detectado en 0x40."));
    } else {
        Serial.println(F("[ERR] No se detecta PCA9685 en 0x40! Revisa 3V3->VCC, SDA->D4, SCL->D5 y GND."));
    }

    pwm.begin();
    pwm.setOscillatorFrequency(27000000);
    pwm.setPWMFreq(SERVO_FREQ_HZ);
    delay(20);

    // Arranque seguro relajado: evita cualquier golpe brusco al encender antes de calibrar.
    // Envía HERO, HOME o mueve un slider para activar torque suavemente.
    relaxAll();

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

    // 2. Leer comandos por Wi-Fi UDP (Peter Corke Python con 1 solo cable!)
    int pktSize = udp.parsePacket();
    if (pktSize > 0) {
        char buf[96];
        int len = udp.read(buf, min(pktSize, (int)sizeof(buf) - 1));
        if (len > 0) {
            buf[len] = '\0';
            String cmdStr(buf);
            processCommand(cmdStr);
            cmdStr.trim();
            if (cmdStr.equalsIgnoreCase("STATUS")) {
                String js = buildStatusJson();
                udp.beginPacket(udp.remoteIP(), udp.remotePort());
                udp.print(js);
                udp.endPacket();
            }
        }
    }

    // 3. Lazo de control suave a 100 Hz
    uint32_t now = millis();
    if (now - lastTickMs < CONTROL_PERIOD_MS) return;
    lastTickMs = now;

    if (isRelaxed) return;

    if (trajActive) {
        float u = (float)(now - trajStartMs) / (float)trajDurMs;
        if (u >= 1.0f) {
            u = 1.0f;
            trajActive = false;
        }
        // Polinomio quíntico mínimo-jerk (idéntico a `rtb.jtraj` de Peter Corke)
        float s = u * u * u * (10.0f + u * (-15.0f + 6.0f * u));
        for (uint8_t i = 0; i < 5; i++) {
            qCurr[i] = qStart[i] + s * (qTarget[i] - qStart[i]);
        }
        applyCurrentPose();

        // Avanzar siguiente paso si la demo Pick-and-Place está activa
        if (!trajActive && demoRunning) {
            demoIdx++;
            if (demoIdx < DEMO_LEN) {
                startQuinticMove(DEMO_SEQ[demoIdx].q, DEMO_SEQ[demoIdx].ms);
            } else {
                demoRunning = false;
                Serial.println(F("[OK] Demo finalizada."));
            }
        }
    } else if (streamMode) {
        bool moved = false;
        for (uint8_t i = 0; i < 5; i++) {
            float diff = qTarget[i] - qCurr[i];
            if (fabsf(diff) > 0.05f) {
                qCurr[i] += diff * STREAM_ALPHA;
                moved = true;
            } else {
                qCurr[i] = qTarget[i];
            }
        }
        if (moved) applyCurrentPose();
    }
}
