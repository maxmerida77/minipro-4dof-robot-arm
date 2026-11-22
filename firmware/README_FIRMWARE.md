# Firmware `XIAO ESP32-S3 / C3` — Mini-Pro 4-DOF (`B2 Stealth`)

## 1. Cómo cargarlo (Arduino IDE — 3 pasos)
1. En **Arduino IDE** instala el paquete de placas **esp32** (Espressif), selecciona **`XIAO_ESP32S3`** *(o `XIAO_ESP32C3`)* y verifica en `Herramientas` que **`USB CDC On Boot: Enabled`** esté activo para ver los mensajes en el Monitor Serial.
2. En el *Library Manager*, instala **`Adafruit PWM Servo Driver Library`** (por Adafruit).
3. Abre `firmware/minipro_b2_stealth/minipro_b2_stealth.ino`, conecta tu `XIAO` por USB-C y presiona **Subir**. *(Opcional: edita `WIFI_STA_SSID` y `WIFI_STA_PASS` en `config.h` si quieres que se conecte al Wi-Fi de tu casa; si los dejas vacíos, crea su propia red `MiniPro-B2-Stealth` en `http://192.168.4.1/`).*

---

## 2. Calibración de Servos en Banco (ANTES de ensamblar el brazo)
1. Conecta el circuito siguiendo `electronics/DIAGRAMA_CABLEADO.md` (verificando primero **5.0V** en el `AR5515` con multímetro).
2. Enchufa los `4× MG90S` sueltos en `CH0..CH3` del `PCA9685` y tu `SG90` en `CH4`.
3. Abre el Monitor Serial a `115200 baud` y envía:
   ```text
   CENTER
   ```
   Los 4 `MG90S` irán a `1500 µs` (`90°` exactos). Con el brazo en esa posición neutra, atornilla los *horns* alineados y ensambla.
4. Si algún eje queda desviado ±3°–5° tras armar, ajusta su `offset_deg` en `config.h` y vuelve a subir.

---

## 3. Cómo conectarlo con Peter Corke Python (¡con 1 solo cable USB-C!)
* **Modo Wi-Fi (1 solo cable de corriente al UGREEN 50W, cero cable a la laptop):**
  ```powershell
  python python/gemelo_digital_esp32.py --wifi 192.168.4.1
  ```
  *(Cambia `192.168.4.1` por la IP que imprima el Monitor Serial si configuraste tu Wi-Fi de casa).*
* **Modo Cableado USB Serial:**
  ```powershell
  python python/gemelo_digital_esp32.py --port COM5
  ```
* **Modo Escritorio Independiente (sin Python ni PC):**
  Abre `http://192.168.4.1/` (o la IP local) en tu celular o navegador para controlar el brazo con la interfaz minimalista **`B2 Stealth`**.
