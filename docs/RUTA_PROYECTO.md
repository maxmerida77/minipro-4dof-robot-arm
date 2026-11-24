# Ruta Iterativa del Proyecto — Brazo Robótico Mini-Pro 4-DOF (`B2 Stealth` · `v4 Clean-DFA`)

> **Meta:** Entregar un proyecto escolar sobresaliente con **Peter Corke (`roboticstoolbox-python 1.5.0`)** y un brazo minimalista de escritorio acabado como producto comercial, dentro de **\$1,500 MXN todo incluido** (logrado: **~\$1,120–\$1,320 MXN** comprando 100% local en México).

---

## Arquitectura Bloqueada (Single Source of Truth: `cad/params.py`)
* **4 DOF + Pinza:** `4× MG90S` 180° metálicos (`AR1240`, huella compatible `drop-in` con futuro `MG92B` en `J2`) + `1× SG90` (ya disponible).
* **Control y energía (1 solo cable USB-C negro):** `XIAO ESP32-S3` + `PCA9685` (`AR0389`, `VCC` estrictamente a `3V3`) + Cargador **UGREEN 50W** → Módulo USB-C PD **`AR5515` (DIP 5V)** + botón ON/OFF **`KCD11-2P`** (`AR0243`) + diodo Schottky **`1N5819`** (`AR0195`) + capacitor **`1000 µF 16V`** (`AR1127`).
* **Geometría DH (Innegociable):** `d₁ = 82 mm`, `a₂ = 82 mm`, `a₃ = 70 mm`, `a₄ = 53 mm` (alcance horizontal `205 mm`; base coaxial `Ø 106 mm` con 6 patas perimetrales `r = 45.5 mm`, 0 rodamientos `608ZZ`, 0 insertos con cautín).
* **Acabado:** **`B2 Stealth`** en **PLA+ / PLA Pro Negro** (~95%, Placas 1A y 1B) + **10 piezas PLA Blanco Mate separadas** (`0%` purga AMS, Placa 2).
* **Límites seguros + Guarda 3D sincronizados (`cad/params.py`):** `J1[-85,+85]`, `J2[+22,+145]`, `J3[-125,+20]`, `J4[-80,+80]` + guarda 3D real (mesa `Z ≥ 4 mm` con panza `SG90 -21.8 mm`, base `Ø 106 mm` y auto-colisión `L4 vs L2`), más control dual **FK + IK en vivo** y **`Ir a Posición Exacta [G]`**.

---

## Mapa de Iteraciones

### Iteración 0 — Envolvente 3D, Parámetros Maestros y Concepto Estético *(COMPLETADA)*
* `cad/params.py`, estética `B2 Stealth` monocromática seleccionada.

### Iteración 1 — Cinemática Oficial Peter Corke (Python) + BOM Verificado *(COMPLETADA)*
* `python/robot_minipro_rtb.py`, `python/demo_peter_corke.py`, gráficas en `docs/graficas_peter_corke/` (`error FK-IK = 1.27e-14°`, `error Z ctraj = 6.39e-14 mm`).

### Iteración 2 & 3 — `CAD v3.1` + KiCad 9.0 + Fritzing 4K + SPICE + Wokwi *(COMPLETADA)*
* Esquema nativo KiCad 9.0 (`0 Errores, 0 Avisos` ERC), diagrama pictórico Fritzing 4K, simulación SPICE real en `ngspice.dll`, simulador Wokwi (`ESP32-S3 + PCA9685 custom chip + 5 servos`).

### Iteración 4 — Auditoría Cruzada (Codex + DFA) → `CAD v4 Clean-DFA` *(COMPLETADA Y VERIFICADA 8/8)*
Resuelve íntegramente los 8 hallazgos técnicos detectados en la auditoría independiente antes de fabricar:
1. **Sólido único conectado (`34/34` STLs `len(split()) == 1`):** Horquillas en U monolíticas `L2/L3` (`05_eslabon_l2_v4`, `06_antebrazo_l3_v4`) y base `01_base_fija_v4` con jefes fusionados.
2. **Despeje multipose (`0.00 mm³` en 6 escenarios) + Guarda Anti-Mesa:** Eliminada la colisión `198.44 mm³` en `J3=-135°` y el contacto con la mesa (`Z_tcp ≥ 8 mm`, `Z_j3/j4 ≥ 22 mm` bloqueados en firmware, Wokwi, Peter Corke y Gemelo Digital).
3. **Pinza Paralela Abierta MeArm Módulo `1.5` (`12T`):** 1 solo sólido rígido engrane+brazo+horn, centro de almohadillas calibrado exacto en **`53.000 mm`** (`err = 0.0000 mm`), ecuación trigonométrica exacta compartida (`asin/cos`) eliminando la aproximación lineal `3°/mm`.
4. **Base Coaxial `Ø 106 mm` sin colisiones (`0.00 mm³`):** `MG90S J1` centrado + `PCA9685` desplazado a `+X` con volumen real de conectores Dupont (`23 mm`), `KCD11` con terminales faston (`19 mm`), `XIAO`, `AR5515`, `1000 µF` y aro de lastre.
5. **Balance de masa y carga útil realista:** Masa móvil reducida a **`~95.1 g`** (`49.3 g` PLA); arranque protocolizado **sin carga externa** con rampas suaves de `1100 ms` hasta medir corriente y temperatura real.
6. **Estabilidad y retención axial `J1`:** 6 patas perimetrales (`r = 45.5 mm`, radio efectivo `39.4 mm`) + retén axial independiente **`04b_reten_axial_j1`** (`3× M3`) liberando al *horn* de cargas axiales.
7. **Pivotes con separador M3 + Bayonetas `32°` + Cupones progresivos:** Casquillos `11_separador_m3_*` (rosca fuera del giro, `Nyloc` no frena la horquilla), tapas Stealth de bayoneta (`0` flexión PLA), tapas de cables `dovetail` y **3 cupones `.3mf`** (`cupon_1`, `cupon_2` articulación piloto, `cupon_3` pinza independiente).
8. **Potencia y seguridad de firmware:** `FULL_OFF` real (`4096`) desde `setup()`, resincronización tras `CENTER`/`RAW`, rampa de despertar (`≥ 1200 ms`), simulación SPICE con modelo OCP `3.0 A` (`I_PD máx = 2.53 A < 3.0 A`), y `2×` tiras Dupont `20 cm` en el BOM para bucles articulados holgados.

### Iteración 4B — Cierre Integral Auditoría Pre-Fabricación Ronda 2 (`CAD v4 Clean-DFA` · **GO**) *(COMPLETADA Y VERIFICADA)*
Resuelve todos los bloqueos `P0`, `P1`, control y potencia de [`AUDITORIA_RONDA_2_PRE_FABRICACION_V4.md`](AUDITORIA_RONDA_2_PRE_FABRICACION_V4.md):
* **P0-1 Pivote pasivo `J2/J3/J4`:** `HUB_HALF_W = 19.0 mm` + mamparo sólido `1.20 mm` separando el cuerpo del `MG90S` del bolsillo `M3 Nyloc` y la punta del `M3×12` (`2.30 mm` libre del servo; **`0.0000 mm³`** colisión B-Rep con tornillos y tuercas reales).
* **P0-2 Cupón 1:** Corte de cola de milano corregido a `extrude(+42.0)` (`Y = -21..+21 mm`) con `assert vol_removed > 1200 mm³`.
* **P0-3 Tornillería y casquillos de la pinza:** `SG90` rotado 180° a `+Y` (`12.4 mm` libre del engrane pasivo derecho), `7×` casquillos lisos `M3` (`11b..11e`), pilares traseros con `Nyloc` cautivas sobre el `SG90`, avellanado `Ø 6.0×1.70 mm` en engranes para `2× M3×16` (cero `M3×18`), `≥ 0.70 mm` de rosca tras nylon en las 10 tuercas `Nyloc`, postes `PCA9685` estandarizados a `4× M3×6` y tabla exacta por unión en `BOM_UNIT_ELECTRONICS.md`.
* **P0-4 Base y bóveda de lastre:** Bóveda inferior en herradura (`Z = 1.6..10.0 mm`) con 6 pilas guiadas modeladas (`~247 g` acero sólido / `~222 g` monedas MX / hasta `~298 g` rellenado) sellada bajo la bandeja electrónica aislante plana **`03b_bandeja_electronica_v4`** (`0 soportes`, `0.0000 mm³` vs `PCA9685`, Duponts `23 mm` y retén `04b`).
* **P0-5 Compilación, reactivación y control:** Ambos sketches (`minipro_b2_stealth.ino` para `XIAO_ESP32S3` y `simulacion_wokwi/sketch.ino` para `esp32s3`) compilados con **`0 errores`** en `esp32:esp32 3.1.3`; reactivación segura unificada `≥ 1200 ms` incluso desde streaming; validación de trayectoria quíntica en 16 muestras + tick `100 Hz`; rechazo `NaN/Inf`; IK con radio firmado (`r < 0`), fallback de codo y preservación de `q1` en `r ≈ 0`.
* **P1-1 y P1-2 Punto de agarre + Auditoría B-Rep estricta + SPICE `.cir`:** Transformación explícita `(tcp_x(g), 0, +5.800) mm` en Python, Gemelo 3D y firmware (`grip_xyz`); auditoría estricta `tol = 0.01 mm³` sin ocultar errores booleanos (**`42/42` STLs estancos 1-sólido, `0.0000 mm³` en los 8 escenarios**); `.cir` sincronizado con OCP `3.0 A` (`4.434 V`, `4.171 V`, `2.534 A`).

### Iteración 4C — Cierre Definitivo Auditoría Ronda 3 (`CAD v4 Clean-DFA` · **GO TOTAL**) *(COMPLETADA Y VERIFICADA)*
Cierra los 6 hallazgos finales de [`AUDITORIA_RONDA_3_CIERRE_GO_V4.md`](AUDITORIA_RONDA_3_CIERRE_GO_V4.md):
1. **Retén axial `J1` (`3× M3×8` avellanados):** `04b_reten_axial_j1` (`Z = 37.3..40.5`, 3 avellanados `Ø 6.2×1.75 mm`, volteado en Placa 1B con 0 overhang) aloja las cabezas `M3×8` a `+0.65 mm` sobre los Duponts de `23 mm` en todo el giro `J1` (`0.0000 mm³` en `J1 = 0°, -30°, +45°, +85°`).
2. **Postes ciegos `PCA9685` (`4× M3×4`):** `03b_bandeja_electronica_v4` (`2.0 mm`) + postes ciegos `1.6 mm` con piloto terminado en `Z = 11.15 mm` → **`1.05 mm` de PLA+ macizo** + `0.20 mm` cámara piloto (`1.25 mm` bajo punta `M3×4`, `+1.60 mm` hasta discos), `0.0000 mm³` colisión con tornillos modelados.
3. **Bloqueo `wakeRampActive` en despachador de firmware y Wokwi:** Durante la rampa obligatoria de `1200 ms` desde `RELAX`, NINGÚN comando (incluidos `CENTER`, `RAW`, `DEMO`, `SWEEP`, `HERO`, `HOME`, `M`, `G`, `IK`, `IKG`, `IKGRIP`) puede cancelar `trajActive`, alterar secuencias ni escribir PWM directo (solo `RELAX` y `STATUS/FK` están permitidos).
4. **Lastre exacto B-Rep y presupuesto:** Documentados exactamente **`217.7 g`** (`27.73 cm³` acero en 6 discos, `SF = 1.62×` sin carga) y sumados `\$50 MXN` de rondanas al total (**`~\$1,405 MXN ≤ \$1,500 MXN`**).
5. **Pinza `M3×10` sobre `SG90`:** Brida de `11c` elevada a `1.30 mm` + tope ciego `Z = +1.70 mm` → **`+0.500 mm`** de despeje B-Rep sobre `SG90` (`10×` mayor margen) y `+0.55 mm` de rosca tras `Nyloc`.
6. **Paridad IK y `Agarre w04`:** Wokwi pasa `curQ[0]` a `computeIK` (preserva yaw en `r ≈ 0`); Web UI, firmware y Wokwi ofrecen modalidad explícita `TCP DH (a₄=53)` vs `Agarre w04 (+5.8 mm)` (`mode=grip` / `IKGRIP`).

### Iteración 5 — Prototipado Progresivo, Pruebas en Banco y Entrega Escolar *(SIGUIENTE PASO FÍSICO)*
1. Imprimir **Cupón 1 → Cupón 2 (1 articulación con servo real) → Cupón 3 (pinza independiente con 7 casquillos y SG90)**.
2. Imprimir las **3 placas `v4` (`239.5 g` PLA, `37/42` [88%] sin soportes, `0%` purga AMS)** en Bambu Lab A1 Combo.
3. Verificar `5.0 V` del `AR5515` y caída real bajo carga con multímetro; ejecutar `CENTER` antes de fijar *horns*.
4. Ejecutar demostración final sincronizada **Peter Corke Python ↔ Gemelo Digital 3D ↔ XIAO ESP32-S3 (Wi-Fi UDP)**.
