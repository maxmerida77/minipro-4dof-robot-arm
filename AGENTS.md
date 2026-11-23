# AGENTS.md — Reglas Maestras y Contexto de Ingeniería (`Mini-Pro 4-DOF B2 Stealth`)

> **Propósito de este archivo:** Guía técnica oficial del repositorio para agentes de ingeniería (Codex, Antigravity, revisores externos). Define la arquitectura bloqueada, las restricciones físicas/presupuestarias innegociables, el estado actual del proyecto (`CAD v3.1` vs propuesta `v4 Clean-DFA`) y los criterios estrictos de verificación.

---

## 1. Resumen del Proyecto
* **Objetivo:** Brazo robótico de escritorio **4-DOF + Pinza Paralela** para entrega académica con cinemática oficial de **Peter Corke (`roboticstoolbox-python 1.5.0`)**, Gemelo Digital 3D en tiempo real (Wi-Fi UDP / USB Serial), electrónica de **1 solo cable USB-C** y acabado industrial minimalista **`B2 Stealth`**.
* **Estado Actual en el Repo:**
  * **Cinemática Peter Corke:** Completa y verificada (`error FK-IK = 1.27e-14°`, `error Z ctraj = 6.39e-14 mm`).
  * **CAD `v3.1`:** Completo (`cad/mini_pro_b2_stealth_v3.py`), **`0.00 mm³` colisiones B-Rep** (`cad/auditoria_ensamble_v3.py`), **`35/35` STLs estancos**, 3 placas `.3mf` en `Z = 0` para Bambu Lab A1.
  * **Electrónica:** Esquema nativo **KiCad 9.0** (`0 Errores, 0 Avisos` ERC), diagrama pictórico Fritzing 4K, simulación **SPICE real en `ngspice`** y proyecto **Wokwi (`ESP32-S3 + PCA9685 + 5 servos`)**.
  * **Firmware:** Completo (`firmware/minipro_b2_stealth/`, `100 Hz` quíntico mínimo-jerk + UDP `4210` + Serial `115200` + Web UI).
  * **Decisión en curso (motivo de esta revisión):** Antes de comprar/imprimir, estamos auditando la **facilidad real de ensamble (DFA) y la física estructural** para decidir qué cambios exactos pasar a **`CAD v4 Clean-DFA`** (sin romper ninguna restricción de la Sección 2).

---

## 2. Reglas Innegociables (Hard Constraints — NO ROMPER)

1. **Single Source of Truth (`cad/params.py`):**
   * Toda medida cinemática, envolvente, hardware y holgura debe provenir exclusivamente de `cad/params.py` y permanecer sincronizada con `python/robot_minipro_rtb.py`, `python/gemelo_digital_esp32.py` y `firmware/minipro_b2_stealth/config.h`.
2. **Cinemática Denavit-Hartenberg Estándar 4R Serial (NO cambiar a cadena cerrada en el brazo):**
   * `d1 = 82.0 mm`, `a2 = 82.0 mm`, `a3 = 70.0 mm`, `a4 = 53.0 mm` (alcance horizontal teórico `205.0 mm`).
   * Límites articulares: `J1 ∈ [-90°, +90°]`, `J2 ∈ [+15°, +165°]`, `J3 ∈ [-135°, +45°]`, `J4 ∈ [-90°, +90°]`, `Pinza ∈ [0, 30 mm]`.
   * **Motivo:** Requisito académico directo de modelado serial 4R con `DHRobot` de Peter Corke (por eso se descartó paralelogramo en el brazo principal tipo EEZYbotARM).
3. **Estética `B2 Stealth` Sagrada (NO comprometer el acabado exterior):**
   * Silueta monocromática limpia en **PLA Negro Mate (~95%)** con detalles separados en **PLA Blanco Mate (~5%, 0% purga AMS)**:
     * Aro blanco base (`w01`),
     * `6×` aros blancos laterales en las 3 articulaciones `J2, J3, J4` (`w_aro_j2/j3/j4`),
     * Collar blanco en la muñeca (`w02`),
     * `2×` almohadillas blancas en las mordazas de la pinza (`w04`).
   * Servos y cables deben quedar visualmente ocultos desde vistas frontal y lateral (tapas laterales cerradas o *snap-fit*, canal trasero de cables).
4. **Pinza Seleccionada por el Usuario para `v4`:**
   * **Pinza Paralela Abierta de 2 dedos simétricos (estilo MeArm con engranes gruesos módulo `1.5`)** accionada por `1× SG90`.
   * **Motivo:** El robot opera por coordenadas exactas `TCP` de Peter Corke **sin cámara**; se requiere cierre simétrico centrado en `TCP` (`0–30 mm`) sobre caras paralelas.
5. **Hardware y Presupuesto Bloqueados (≤ $1,500 MXN total en México):**
   * Actuadores: `4× MG90S` 180° metálicos (`22.8 × 12.2 mm`, huella compatible con futuro upgrade `1× MG92B` en `J2`) + `1× SG90` (ya disponible).
   * Control y potencia (**1 solo cable USB-C negro**): Cargador **UGREEN 50W** → Módulo PD **`AR5515` (DIP fijado en `5V`)** → Botón **`KCD11-2P`** (`AR0243`) → Bus `+5V_SERVO` con capacitor **`1000 µF 16V`** (`AR1127`) + Diodo Schottky antirretorno **`1N5819`** (`AR0195`, cátodo hacia `XIAO 5V`) → **`Seeed Studio XIAO ESP32-S3`** ↔ Bus I2C estrictamente a **`3.3V`** (`3V3`, `D4=GPIO5`, `D5=GPIO6`, `GND`) ↔ **`PCA9685` (`0x40`, `AR0389`)**.
   * **Regla eléctrica crítica:** `PCA9685 VCC` va SIEMPRE a `XIAO 3V3` (nunca `5V`).
6. **Impresión 3D — Bambu Lab A1 Combo (`256 × 256 mm`, boquilla `0.4 mm`, PLA Mate):**
   * Impresora abierta (sin cámara cerrada → usar **PLA Mate / PLA+**, NO ABS/ASA).
   * **0% purga AMS:** Todas las piezas blancas deben ser piezas separadas impresas en su propia placa.
   * Toda pieza exportada para impresión debe ser **100% estanca (*watertight*)**, orientada óptimamente en `Z = 0.000 mm`, con tolerancias realistas para boquilla `0.4 mm` (`CLEARANCE_FIT ≥ 0.20 mm`; engranes módulo `≥ 1.5` en FDM).
7. **Estándar de Verificación Obligatorio antes de aprobar cualquier cambio CAD:**
   * **Cero colisiones B-Rep 3D (`0.00 mm³`)** verificadas matemáticamente con OpenCASCADE (`.intersect()`) en pose héroe y extremos de recorrido (pinza abierta/cerrada y extremos de `J2/J3/J4`).
   * **Verificación de acceso real de herramienta (DFA):** Ningún tornillo de *horn*, servo o pivote puede quedar inaccesible para un desarmador o llave al momento de ensamblar.
   * **Análisis físico real:** Validar torque estático y dinámico en `J2` (cuello de botella principal con `MG90S = 1.85 kg·cm` stall / `1.25 kg·cm` continuo), momento de vuelco en `J1`, deflexión de horquillas en PLA y esfuerzo en pestañas *snap-fit* (cuidado con fatiga/fractura de PLA rígido en clips cortos!).

---

## 3. Mapa Rápido del Repositorio

```text
├── AGENTS.md                                  # Este archivo (reglas maestras para agentes)
├── docs/
│   ├── BRIEF_REVISION_ARQUITECTURA_V4.md      # Brief completo de auditoría física/DFA para segunda opinión
│   ├── RUTA_PROYECTO.md                       # Estado de iteraciones
│   ├── BOM_UNIT_ELECTRONICS.md                # Lista de materiales y costos en México
│   └── GUIA_IMPRESION_BAMBU_A1.md             # Perfiles Bambu Studio y protocolo de tolerancias
├── cad/
│   ├── params.py                              # Single Source of Truth (DH + hardware + holguras)
│   ├── mini_pro_b2_stealth_v3.py              # CAD v3.1 actual (35 STLs + STEP)
│   ├── auditoria_ensamble_v3.py               # Auditoría B-Rep exacta de colisiones (0.00 mm³)
│   ├── generar_placas_bambu_a1.py             # Generador 3 placas .3mf/.stl en Z=0
│   ├── visor_cad_interactivo.py               # Visor 3D VTK interactivo
│   └── exports/                               # STEP v3.1, 35 STLs, 3 placas .3mf y tolerance_test_kit
├── python/
│   ├── robot_minipro_rtb.py                   # Modelo Peter Corke DHRobot + IK analítica
│   ├── demo_peter_corke.py                    # Validación cinemática y gráficas
│   └── gemelo_digital_esp32.py                # Gemelo Digital 3D real (DRY_RUN / Wi-Fi UDP / Serial)
├── electronics/
│   ├── kicad/                                 # Proyecto nativo KiCad 9.0 (0 Errores ERC + PDF/SVG)
│   ├── simulacion_spice/                      # Netlist + script ngspice.dll (KiCad 9) + gráfica
│   ├── simulacion_wokwi/                      # Simulador ESP32-S3 + PCA9685 custom chip + 5 servos
│   ├── diagrama_fritzing_b2_stealth.png/.svg  # Diagrama pictórico 4K
│   └── DIAGRAMA_CABLEADO.md                   # Tabla pin-a-pin + checklist de seguridad
└── firmware/
    └── minipro_b2_stealth/                    # Sketch XIAO ESP32-S3 (100 Hz quíntico + UDP + Web UI)
```

---

## 4. Qué Debe Hacer un Agente Revisor en Esta Fase
* **No reescribir el CAD todavía sin aprobación explícita del usuario.**
* Leer `docs/BRIEF_REVISION_ARQUITECTURA_V4.md`, `cad/params.py` y `cad/mini_pro_b2_stealth_v3.py`.
* Auditar con rigor físico-mecánico cada propuesta de `v4 Clean-DFA` y emitir un dictamen concreto:
  * Qué aprobar tal cual,
  * Qué riesgos físicos ocultos detecta (ej. fricción en pista anular `Ø 78 mm` de PLA, fractura de clips *snap-fit* en PLA Mate, rigidez lateral de horquilla en U sin rodamiento vs con micro-balero, torque de `SG90` en pinza módulo `1.5`, centro de masa y estabilidad anti-vuelco de la base `Ø 94 mm` sin lastre),
  * Qué medidas/tolerancias exactas recomienda ajustar antes de programar `cad/mini_pro_b2_stealth_v4.py`.
