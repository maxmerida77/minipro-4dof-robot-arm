# AGENTS.md — Reglas Maestras y Contexto de Ingeniería (`Mini-Pro 4-DOF B2 Stealth`)

> **Propósito de este archivo:** Guía técnica oficial del repositorio para agentes de ingeniería (Codex, Antigravity, revisores externos). Define la arquitectura bloqueada, las restricciones físicas/presupuestarias innegociables, el estado actual verificado (`CAD v4 Clean-DFA`) y los criterios estrictos de verificación.

---

## 1. Resumen del Proyecto
* **Objetivo:** Brazo robótico de escritorio **4-DOF + Pinza Paralela Abierta MeArm Módulo `1.5`** para entrega académica con cinemática oficial de **Peter Corke (`roboticstoolbox-python 1.5.0`)**, Gemelo Digital 3D en tiempo real (Wi-Fi UDP / USB Serial), electrónica de **1 solo cable USB-C** y acabado industrial minimalista **`B2 Stealth`**.
* **Estado Actual Verificado en el Repo (`CAD v4 Clean-DFA` · Auditorías Ronda 1 + Ronda 2 + Ronda 3 cerradas al 100%):**
  * **Cinemática Peter Corke:** Completa y verificada (`error FK-IK = 1.27e-14°`, `error Z ctraj = 6.39e-14 mm`) + IK con radio firmado (`r < 0`), fallback de codo y preservación de `q1` en `r ≈ 0` (paridad total Python / Firmware / Wokwi) + rechazo `NaN/Inf` + guarda física 3D completa + punto real de agarre `w04` (`(tcp_x(g), 0, +5.800) mm`) comandable en Python, Web UI (`mode=grip`), Serial/UDP (`IKGRIP`) y Wokwi.
  * **CAD `v4 Clean-DFA`:** Completo (`cad/mini_pro_b2_stealth_v4.py`), **`42/42` STLs estancos y de 1 solo sólido conectado (`len(split()) == 1`)**, **`0.0000 mm³` colisiones B-Rep (`tol = 0.01 mm³`, 0 errores booleanos)** (`cad/auditoria_ensamble_v4.py`) en las **11 auditorías estrictas** (sin omisión genérica `hw_steel`, excluyendo únicamente el contacto roscado `hw_screw_X <-> hw_nut_X`), con TODOS los herrajes reales modelados (`3× M3×8` avellanados en `04b_reten_axial_j1` a `+0.65 mm` sobre Duponts `23 mm` en `J1 = 0°/-30°/+45°/+85°`, `4× M3×4` ciegos en `PCA9685` con `+1.25 mm` piso macizo PLA+ sobre lastre, `M3×12/16/10` + `M3 Nyloc` tras mamparo `1.2 mm` en `J2/J3/J4`, `+0.500 mm` libre en biela pinza sobre `SG90` y bóveda de lastre de **`217.7 g`** B-Rep exactos [`SF = 1.62×` vacío] bajo `03b_bandeja_electronica_v4`), punto de agarre `w04` en **`(53.000, +5.800) mm` @ `g=15 mm` (`err = 0.0000 mm`)**, masa móvil `~122.4 g` (`72.6 g` PLA+).
  * **Fabricación Bambu Lab A1:** Kit progresivo de **3 cupones `.3mf`** (`cad/cupones_prototipo_v4.py`) + **3 placas `.3mf` en `Z = 0`** (`cad/generar_placas_bambu_a1_v4.py`, `37/42` [88%] sin soportes, `0%` purga AMS, `04b`, `09` y `11c` volteados con 0 overhang).
  * **Electrónica:** Esquema nativo **KiCad 9.0** (`0 Errores, 0 Avisos` ERC), diagrama pictórico Fritzing 4K, simulación **SPICE real en `ngspice`** (script Python y `.cir` standalone 100% sincronizados con OCP `3.0 A`: `V_SERVO min = 4.434 V`, `V_XIAO min = 4.171 V`, `I_PD máx = 2.534 A < 3.0 A`, fuga inversa `26 µA`) y proyecto **Wokwi (`ESP32-S3 + PCA9685 + 5 servos`)** compilado sin errores en `esp32:esp32 3.1.3`.
  * **Firmware:** Completo y compilado con `0 errores` para `esp32:esp32:XIAO_ESP32S3` (`esp32:esp32 3.1.3`, `firmware/minipro_b2_stealth/`, `100 Hz` quíntico mínimo-jerk, `FULL_OFF = 4096` desde `setup()`, **bloqueo `wakeRampActive` que impide que paquetes de streaming cancelen la rampa de `1200 ms` al salir de `RELAX`**, validación quíntica en 16 muestras + guarda en cada tick `100 Hz`, rechazo `NaN/Inf`, IK dual `TCP DH` / `Agarre w04` en Web UI y Serial/UDP).

---

## 2. Reglas Innegociables (Hard Constraints — NO ROMPER)

1. **Single Source of Truth (`cad/params.py`):**
   * Toda medida cinemática, envolvente, pinza `GRIP_V4`, guarda de mesa y holgura debe provenir exclusivamente de `cad/params.py` y permanecer sincronizada con `python/robot_minipro_rtb.py`, `python/gemelo_digital_esp32.py`, `firmware/minipro_b2_stealth/config.h` y `electronics/simulacion_wokwi/sketch.ino`.
2. **Cinemática Denavit-Hartenberg Estándar 4R Serial (NO cambiar a cadena cerrada en el brazo):**
   * `d1 = 82.0 mm`, `a2 = 82.0 mm`, `a3 = 70.0 mm`, `a4 = 53.0 mm` (alcance horizontal teórico `205.0 mm`, útil seguro `199.0 mm`).
   * Límites articulares seguros (`cad/params.py`): `J1 ∈ [-85°, +85°]`, `J2 ∈ [+22°, +145°]`, `J3 ∈ [-125°, +20°]`, `J4 ∈ [-80°, +80°]`, `Pinza ∈ [0, 30 mm]` + **Guarda Física 3D** (`Z_min ≥ 4 mm` con panza `SG90 -21.8 mm` y puntas `+7.1 mm`, exclusión de base `Ø 106 mm` y auto-colisión `L4 vs L2`).
3. **Estética `B2 Stealth` Sagrada (NO comprometer el acabado exterior):**
   * Silueta monocromática limpia en **PLA Negro Mate (~95%)** con **10 piezas separadas en PLA Blanco Mate (~5%, 0% purga AMS)**: `w01` aro base, `6×` aros laterales `J2/J3/J4`, `w02` collar muñeca y `2×` almohadillas `w04`.
4. **Pinza Seleccionada:**
   * **Pinza Paralela Abierta MeArm módulo `1.5` (`12T`)** accionada por `1× SG90` (cierre simétrico centrado en `TCP = 53.000 mm` @ `g = 15 mm`).
5. **Hardware y Presupuesto Bloqueados (`≤ $1,500 MXN` total en México):**
   * `4× MG90S` 180° metálicos (`AR1240`, huella compatible con `MG92B` en `J2`) + `1× SG90` + `XIAO ESP32-S3` + `PCA9685` (`0x40`, `VCC` SIEMPRE a `3V3`) + 1 solo cable USB-C (`UGREEN 50W` → `AR5515` DIP `5V` → `KCD11-2P` → `1000 µF 16V` + `1N5819` cátodo a `XIAO 5V`).
   * **Protocolo de pruebas:** Arrancar **sin carga externa** y medir tensión/corriente/temperatura en banco antes de declarar capacidad de carga.
6. **Estándar de Verificación Obligatorio antes de aprobar cualquier cambio CAD:**
   * `100%` STLs estancos (`is_watertight == True`) **Y de 1 solo sólido conectado (`len(split()) == 1`)**.
   * **`0.00 mm³` colisiones B-Rep 3D** verificadas en `cad/auditoria_ensamble_v4.py` en las 6 poses/extremos.
   * Acceso real de desarmador/llave y validación física progresiva mediante `cad/exports/v4_clean_dfa/cupones_prueba/`.

---

## 3. Mapa Rápido del Repositorio

```text
├── AGENTS.md                                  # Este archivo (reglas maestras para agentes)
├── docs/
│   ├── BRIEF_REVISION_ARQUITECTURA_V4.md      # Brief original de auditoría física/DFA
│   ├── RUTA_PROYECTO.md                       # Estado de iteraciones (v4 Clean-DFA)
│   ├── BOM_UNIT_ELECTRONICS.md                # Lista de materiales y costos en México (v4)
│   └── GUIA_IMPRESION_BAMBU_A1.md             # Protocolo progresivo de cupones + 3 placas v4
├── cad/
│   ├── params.py                              # Single Source of Truth (DH + GRIP_V4 + holguras)
│   ├── mini_pro_b2_stealth_v4.py              # CAD v4 Clean-DFA oficial (34 STLs 1-sólido + STEP)
│   ├── auditoria_ensamble_v4.py               # Auditoría B-Rep multipose (6 escenarios, 0.00 mm³)
│   ├── cupones_prototipo_v4.py                # Kit progresivo 3 cupones .3mf (Z=0)
│   ├── generar_placas_bambu_a1_v4.py          # Generador 3 placas .3mf/.stl v4 en Z=0
│   ├── render_v4_clean_dfa.py                 # Tablero 4 vistas estudio v4 Clean-DFA
│   ├── visor_cad_interactivo.py               # Visor 3D VTK interactivo (v4)
│   └── exports/v4_clean_dfa/                  # STEP v4, 34 STLs, cupones_prueba/ y placas_bambu_a1/
├── python/
│   ├── robot_minipro_rtb.py                   # Modelo Peter Corke DHRobot + IK + guarda mesa
│   ├── demo_peter_corke.py                    # Validación cinemática y gráficas
│   └── gemelo_digital_esp32.py                # Gemelo Digital 3D real v4 (DRY_RUN / Wi-Fi UDP / Serial)
├── electronics/
│   ├── kicad/                                 # Proyecto nativo KiCad 9.0 (0 Errores ERC + PDF/SVG)
│   ├── simulacion_spice/                      # ngspice.dll (KiCad 9) + modelo OCP 3.0 A + gráfica
│   ├── simulacion_wokwi/                      # Simulador ESP32-S3 + PCA9685 custom chip (v4)
│   ├── diagrama_fritzing_b2_stealth.png/.svg  # Diagrama pictórico 4K
│   └── DIAGRAMA_CABLEADO.md                   # Tabla pin-a-pin + checklist de seguridad
└── firmware/
    └── minipro_b2_stealth/                    # Sketch XIAO ESP32-S3 v4 (100 Hz + FULL_OFF + guarda mesa)
```
