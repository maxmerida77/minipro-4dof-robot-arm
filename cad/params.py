"""
Parámetros Maestros (Single Source of Truth) — Brazo Robótico Mini-Pro 4-DOF (`B2 Stealth`)
===========================================================================================
Todas las dimensiones están en milímetros (mm) y ángulos en grados (°).
Sincronizado al 100% con el carrito verificado de UNIT Electronics México (`docs/BOM_UNIT_ELECTRONICS.md`)
y alimenta simultáneamente el CAD paramétrico (CadQuery) y Peter Corke (`roboticstoolbox-python`).

Hardware definitivo verificado:
- 4 DOF: 4× MG90S 180° metálicos (`AR1240`, compatible 1:1 en huella con MG92B)
- Pinza: 1× SG90 (ya disponible)
- Controlador: XIAO ESP32-S3 (o C3, 21.0×17.8 mm) + PCA9685 (`AR0389`, 62.5×25.4 mm)
- Alimentación (1 cable USB-C desde cargador UGREEN 50W): Módulo USB-C PD `AR5515` (28×10×12 mm, fijado en 5V)
  + Interruptor ON/OFF `KCD11-2P` negro (`AR0243`) + Diodo `1N5819` + Capacitor `1000 µF 16V`
- Rodamientos: 4× `608ZZ-7` (`AR4602`, 8×22×7 mm) · Insertos: `AR2811` (`M3 × 4.5 mm OD × 3 mm`)
- Acabado: `B2 Stealth` (95% PLA Negro Mate + aros blancos ultra-finos en piezas separadas, 0% purga AMS)
"""

# --- Preferencias Confirmadas ---
FINISH_VARIANT = "b2_stealth"
ESP32_BOARD = "xiao_esp32_s3"

# --- Parámetros Cinemáticos Denavit-Hartenberg (mm) — Optimizados para MG90S (~2× margen seguridad) ---
D1_BASE_TO_SHOULDER = 82.0   # Altura escritorio (Z=0) -> eje Hombro J2
A2_LOWER_ARM = 82.0          # Longitud centro-a-centro Hombro (J2) -> Codo (J3)
A3_FOREARM = 70.0            # Longitud centro-a-centro Codo (J3) -> Muñeca (J4)
A4_WRIST_TO_TCP = 53.0       # Distancia eje Muñeca (J4) -> centro de agarre de pinza (TCP)
# Alcance horizontal total = 82 + 70 + 53 = 205 mm · Altura vertical máx = 287 mm (~22-23 cm postura escritorio)

# --- Límites Articulares Reales (grados) ---
Q_LIMITS_DEG = {
    "q1_base": (-90.0, 90.0),      # 180° útiles centrados en +X
    "q2_shoulder": (15.0, 165.0),  # 90° vertical hacia arriba
    "q3_elbow": (-135.0, 45.0),    # 0° alineado con L2; negativo dobla hacia adelante/abajo
    "q4_wrist": (-90.0, 90.0),     # 0° alineado con L3; mantiene pinza horizontal (φ=0°) o vertical (φ=-90°)
    "gripper": (0.0, 30.0),        # Apertura paralela de pinza en mm
}

# --- Dimensiones Reales Verificadas (UNIT Electronics) ---
# Nota: MG90S y MG92B comparten la misma huella 22.8×12.2 mm; dejamos 31.2 mm de fondo interno para compatibilidad dual!
MG90S = {
    "sku": "AR1240",
    "body_l": 22.8,
    "body_w": 12.2,
    "body_h": 28.5,          # Profundidad cuerpo (MG92B = 28.5..31.0 con cuello -> bolsillo 31.2 mm sirve para ambos)
    "pocket_depth": 29.0,    # Profundidad neta del bolsillo para el cuerpo principal
    "flange_l": 32.5,
    "hole_pitch": 27.5,
    "shaft_offset_from_end": 6.0,
}
# Alias de retrocompatibilidad para scripts v0/v1
MG92B = MG90S

SG90 = {
    "body_l": 22.5,
    "body_w": 11.8,
    "body_h": 22.7,
    "flange_l": 32.0,
}

# Rodamientos reales de UNIT Electronics (`AR4602`: 608ZZ-7, $8 MXN c/u)
BEARING_608 = {"sku": "AR4602", "code": "608ZZ-7", "id": 8.0, "od": 22.0, "w": 7.0}
BEARING_BASE = BEARING_608
BEARING_JOINT = BEARING_608

# Electrónica interna en la base (mm)
PCA9685 = {
    "sku": "AR0389",
    "pcb_l": 62.5,
    "pcb_w": 25.4,
    "hole_dx": 56.0,
    "hole_dy": 19.0,
    "height": 14.0,
}

XIAO_ESP32 = {
    "pcb_l": 21.0,
    "pcb_w": 17.8,
    "height": 7.5,
    "usbc_w": 9.4,
    "usbc_h": 3.8,
}

USBC_PD_AR5515 = {
    "sku": "AR5515",
    "pcb_l": 28.0,
    "pcb_w": 10.0,
    "height": 12.0,
    "usbc_w": 9.4,
    "usbc_h": 3.8,
}

SWITCH_KCD11 = {
    "sku": "AR0243",
    "cut_w": 13.5,           # Recorte rectangular de panel (snap-fit)
    "cut_h": 9.0,
    "bezel_w": 15.0,
    "bezel_h": 10.5,
    "depth": 14.0,
}

CAP_1000UF = {
    "sku": "AR1127",
    "dia": 10.2,
    "height": 16.5,
}

# --- Tolerancias Calibradas para Bambu Lab A1 Combo (PLA Mate) ---
CLEARANCE_FIT = 0.20         # Holgura general piezas acoplables
BEARING_FIT = 0.14           # Ajuste semi-apretado para 608ZZ (asiento Ø 22.14 mm, eje Ø 7.86 mm)
# Insertos reales UNIT `AR2811` (M3 × 4.5 mm OD × 3.0 mm largo -> barreno Ø 4.1 mm × 3.8 mm)
INSERT_M3_DIA = 4.10
INSERT_M3_DEPTH = 3.80

# --- Envolvente Industrial Minimalista `B2 Stealth` (mm) ---
BASE_DIA = 94.0
BASE_LOWER_H = 44.0
BASE_RING_H = 3.0
BASE_CROWN_H = 14.0          # Z = 47..61 mm; horquilla sube al eje J2 en Z = 82 mm

J2_DRUM_DIA = 42.0           # Aloja MG90S (22.8×12.2) + 608ZZ (Ø 22×7) 100% encapsulados
J2_DRUM_W = 48.0             # Ancho DFM v3: deja holgura limpia tras MG90S (+Y) y buje 608ZZ (-Y) bajo tapas
J2_CAP_DIA = 32.0

J3_DRUM_DIA = 38.0
J3_DRUM_W = 48.0
J3_CAP_DIA = 29.0

J4_DRUM_DIA = 32.0           # Aloja MG90S + 608ZZ (Ø 22×7) con pared de 5 mm
J4_DRUM_W = 48.0
J4_CAP_DIA = 24.0

# --- Pose Héroe por Defecto (Pinza perfectamente horizontal φ = 0°) ---
HERO_POSE_DEG = {
    "q1": 0.0,
    "q2": 68.0,
    "q3": -96.0,
    "q4": 28.0,
    "gripper_open_mm": 16.0,
}
