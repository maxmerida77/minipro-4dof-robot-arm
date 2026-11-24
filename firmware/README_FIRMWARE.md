# Firmware `XIAO ESP32-S3 / C3` — Mini-Pro 4-DOF (`B2 Stealth` v4 · FK + IK a Bordo)

## 1. Cómo cargarlo (Arduino IDE — 3 pasos)
1. En **Arduino IDE** instala el paquete de placas **esp32** (Espressif), selecciona **`XIAO_ESP32S3`** *(o `XIAO_ESP32C3`)* y verifica en `Herramientas` que **`USB CDC On Boot: Enabled`** esté activo.
2. En el *Library Manager*, instala **`Adafruit PWM Servo Driver Library`** (por Adafruit).
3. Abre `firmware/minipro_b2_stealth/minipro_b2_stealth.ino`, conecta tu `XIAO` por USB-C y presiona **Subir**. *(Opcional: edita `WIFI_STA_SSID` y `WIFI_STA_PASS` en `config.h`; si los dejas vacíos, crea su propia red `MiniPro-B2-Stealth` en `http://192.168.4.1/`).*

---

## 2. Calibración de Servos en Banco (ANTES de ensamblar el brazo)
1. Verifica primero **5.0 V** en el `AR5515` con multímetro (`PCA9685 VCC` siempre a `XIAO 3V3`).
2. Enchufa los `4× MG90S` sueltos en `CH0..CH3` del `PCA9685` y tu `SG90` en `CH4`.
3. Abre el Monitor Serial (`115200 baud`) y envía `CENTER` → `CH0..CH3` se colocan en `1500 µs` (`90°` exactos) y se resincroniza el estado interno; atornilla los *horns* alineados y ensambla.
4. Verifica el sentido de giro enviando movimientos pequeños (`M 10 90 -90 0 15 800`, etc.); si un eje se mueve al revés cambia `invert = true`, o si queda desviado `±3°–5°` ajusta `offset_deg` en `config.h` y vuelve a subir.

### Límites Seguros y Guarda Física 3D Activa (Sincronizados con `cad/params.py`)
* **Límites articulares:** `J1 ∈ [-85°, +85°]`, `J2 ∈ [+22°, +145°]`, `J3 ∈ [-125°, +20°]`, `J4 ∈ [-80°, +80°]`, `Pinza ∈ [0, 30 mm]` (conservan `5°–25°` de margen contra los topes internos de los `MG90S` y protegen los bucles de cableado).
* **Guarda 3D real en cada movimiento (FK e IK):** Bloquea cualquier pose donde la panza del `SG90` (`-21.8 mm` bajo `J4`), las puntas de los dedos (`+7.1 mm` tras el TCP) o el antebrazo bajen de `Z < 4 mm`, choquen contra la base cilíndrica (`Ø 106 mm`) o produzcan auto-colisión `L4 vs L2`.

---

## 3. Comandos Unificados (USB Serial `115200` y Wi-Fi UDP `4210`)

| Comando | Tipo | Descripción | Ejemplo |
| :--- | :---: | :--- | :--- |
| `IK x y z phi [grip] [ms]` | **Inversa (IK)** | Calcula `(q1..q4)` a bordo y mueve suave al punto cartesiano `(X, Y, Z, φ)` con guarda anti-mesa | `IK 135 50 90 -20 15 1100` |
| `IKG x y z phi [grip]` | **Inversa (IK)** | Streaming continuo cartesiano (para sliders en vivo) | `IKG 145 0 125 0 15` |
| `M q1 q2 q3 q4 grip [ms]` | **Directa (FK)** | Movimiento quíntico mínimo-jerk en espacio articular | `M 0 68 -96 28 15 1100` |
| `G q1 q2 q3 q4 grip` | **Directa (FK)** | Streaming articular continuo desde Peter Corke / Gemelo Digital | `G 25 80 -90 10 15` |
| `FK` / `STATUS` | **Telemetría** | Imprime ángulos `(q1..q4)`, pinza y TCP calculado `(X, Y, Z, φ)` | `FK` |
| `HERO` / `HOME` / `DEMO` | **Presets** | Pose Héroe (`145.5, 0, 125.2 mm`), Home Vertical o Pick & Place | `HERO` |
| `CENTER` / `RELAX` | **Banco / Seguridad** | Centrado `1500 µs` resincronizado o apagado `FULL_OFF` (`4096`) | `RELAX` |

---

## 4. Control Dual en Vivo (`Directa FK` ↔ `Inversa IK`)
* **Web UI desde tu celular (`http://192.168.4.1/`):** Incluye pestañas **`Directa · FK (J1..J4)`** e **`Inversa · IK (X, Y, Z, φ)`** con sliders + cajas numéricas exactas + telemetría bidireccional en vivo y aviso instantáneo si un punto sale de alcance o activa la guarda anti-mesa.
* **Gemelo Digital 3D (Peter Corke Python):**
  ```powershell
  python python/gemelo_digital_esp32.py                     # Simulación 3D ([F] FK / [I] IK / [G] Ir a Posición Exacta)
  python python/gemelo_digital_esp32.py --goto 125 65 95 -20  # Arranca yendo suavemente a (X,Y,Z,Phi)
  python python/gemelo_digital_esp32.py --wifi 192.168.4.1  # Vivo por Wi-Fi UDP (1 solo cable)
  python python/gemelo_digital_esp32.py --port COM5         # Vivo por USB Serial
  ```
