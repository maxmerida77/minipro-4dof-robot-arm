# Simulador Interactivo de Electrónica y Firmware en Wokwi (`ESP32-S3 + PCA9685 + 5 Servos`)

Esta carpeta te permite probar **gratis en el navegador (`wokwi.com`)** tu bus I2C (`SDA = GPIO5`, `SCL = GPIO6`), la librería real `Adafruit_PWMServoDriver(0x40)`, el interpolador quíntico a `100 Hz` y ver moverse los **5 servos (`J1..J4` + `Pinza SG90`)** antes de comprar un solo componente.

## Cómo correrlo en 2 minutos en `wokwi.com` (sin instalar nada)

1. Entra a **[wokwi.com/projects/new/esp32-s3](https://wokwi.com/projects/new/esp32-s3)** *(inicia sesión gratis para habilitar Custom Chips)*.
2. **Copia/reemplaza los 3 archivos principales** en las pestañas del proyecto:
   * `sketch.ino` ← contenido de [`sketch.ino`](sketch.ino)
   * `diagram.json` ← contenido de [`diagram.json`](diagram.json)
   * En la pestaña **Library Manager (`+`)** agrega **`Adafruit PWM Servo Driver Library`** *(o pega [`libraries.txt`](libraries.txt))*.
3. **Agrega el chip custom `PCA9685`:**
   * Haz clic en la flecha junto a las pestañas (`▼` → **"Add a new file..."**) y crea estos 2 archivos con su nombre exacto:
     * `pca9685.chip.json` ← contenido de [`pca9685.chip.json`](pca9685.chip.json)
     * `pca9685.chip.c` ← contenido de [`pca9685.chip.c`](pca9685.chip.c)
4. Pulsa el botón verde **Play ▶**:
   * Verás en el Monitor Serial: `[OK] PCA9685 detectado en I2C 0x40 (SDA=GPIO5, SCL=GPIO6)`.
   * Automáticamente correrá **`SWEEP`**, moviendo suavemente **uno por uno** `j1_base`, `j2_hombro`, `j3_codo`, `j4_muneca` y `pinza_sg90`.
   * Luego puedes escribir comandos interactivos en el Monitor Serial:
     * `CENTER` → pone `CH0..CH3` a `1500 µs` (`90°` exactos)
     * `HERO` / `HOME` / `SWEEP` / `RELAX` / `STATUS`
     * `M 45 80 -70 10 28` → mueve suavemente a esos ángulos y abre la pinza a `28 mm`.
