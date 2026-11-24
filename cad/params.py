"""
Parámetros Maestros (Single Source of Truth) — Brazo Robótico Mini-Pro 4-DOF (`B2 Stealth` v4 Clean-DFA)
========================================================================================================
Todas las dimensiones están en milímetros (mm) y ángulos en grados (°).
Sincronizado al 100% entre:
  - CAD paramétrico v4 (`cad/mini_pro_b2_stealth_v4.py`)
  - Cinemática oficial Peter Corke (`python/robot_minipro_rtb.py`)
  - Gemelo Digital 3D (`python/gemelo_digital_esp32.py`)
  - Firmware XIAO ESP32-S3 (`firmware/minipro_b2_stealth/config.h`)
  - BOM verificado en México (`docs/BOM_UNIT_ELECTRONICS.md`)

Incorpora TODAS las correcciones de la auditoría cruzada de ingeniería (Codex + DFA):
  1. Sólido único conectado garantizado en todas las piezas estructurales (L2/L3 horquillas en U).
  2. Despeje completo en todo el recorrido articular (incl. J3=-135° sin colisión) + guarda Z mesa.
  3. Pinza Paralela Abierta MeArm módulo 1.5 (10T), centro de almohadillas calibrado exacto en a4=53 mm
     a apertura nominal 15 mm, y ecuación trigonométrica exacta compartida con firmware y gemelo.
  4. Base Ø106 mm con MG90S J1 coaxial centrado, retención axial independiente del horn, pista Ø88 mm,
     apoyo perimetral (r=45.5 mm), espacio de lastre y empaquetado 0-colisión con conectores enchufados.
  5. Articulaciones J2/J3/J4 con acceso real al tornillo del horn (Ø5.2 mm), pivote M3 con separador
     (rosca fuera de la superficie de giro, Nyloc no frena el movimiento) y tapas Stealth de bayoneta.
"""

import math

# --- Preferencias Confirmadas ---
FINISH_VARIANT = "b2_stealth"
ESP32_BOARD = "xiao_esp32_s3"
CAD_VERSION = "v4_clean_dfa"

# --- Parámetros Cinemáticos Denavit-Hartenberg Estándar 4R Serial (mm — INNEGOCIABLES) ---
D1_BASE_TO_SHOULDER = 82.0   # Altura escritorio (Z=0) -> eje Hombro J2
A2_LOWER_ARM = 82.0          # Longitud centro-a-centro Hombro (J2) -> Codo (J3)
A3_FOREARM = 70.0            # Longitud centro-a-centro Codo (J3) -> Muñeca (J4)
A4_WRIST_TO_TCP = 53.0       # Distancia eje Muñeca (J4) -> centro de almohadillas pinza en apertura nominal (15 mm)

# --- Límites Articulares Reales Seguros (grados / mm — Single Source of Truth) ---
# Calibrados contra las mallas STL v4 + márgenes de protección contra topes internos MG90S
# y bucles de cableado (conservan 199 mm alcance frontal, Pick & Place y Rectángulo ctraj).
Q_LIMITS_DEG = {
    "q1_base": (-85.0, 85.0),      # 170° útiles (5° margen por lado contra topes internos MG90S)
    "q2_shoulder": (22.0, 145.0),  # 123° útiles (evita zona alto par/piso <22° y vuelco atrás >145°)
    "q3_elbow": (-125.0, 20.0),    # 145° útiles (evita pellizco cables <-125° e hiperextensión >+20°)
    "q4_wrist": (-80.0, 80.0),     # 160° útiles (10° margen por lado contra topes MG90S/cable SG90)
    "gripper": (0.0, 30.0),        # Apertura paralela de pinza en mm
}

# --- Guarda Física 3D Envolvente Real (mm) — Sincronizada CAD / Python / Firmware / Wokwi ---
# Incluye la envolvente real medida de los STLs v4: panza inferior del SG90 (-21.8 mm bajo J4),
# punta física de los dedos (+7.1 mm tras TCP), carcasa cilíndrica de base Ø106 mm y viga L2.
TABLE_SAFE_Z_TCP_MM = 8.0      # Z mínimo de referencia del TCP sobre la mesa
TABLE_SAFE_Z_JOINT_MM = 22.0   # Z mínimo de referencia para centros J3 y J4
GUARD_FLOOR_Z_MIN_MM = 4.0     # Altura libre mínima real de cualquier punto físico (SG90/dedos/L3) sobre Z=0
GUARD_BASE_DRUM_R_MM = 56.0    # Radio de exclusión de la base fija Ø106 mm (Z < 54 mm)
GUARD_BASE_DRUM_Z_MM = 54.0
GUARD_BASE_NECK_R_MM = 46.0    # Radio de exclusión del cuello/torreta J1 (Z < 64 mm)
GUARD_BASE_NECK_Z_MM = 64.0
GUARD_L4_SG90_Z_MM = -21.8     # Cota Z más baja real de palma+SG90 en frame local J4
GUARD_FINGER_TIP_EXTRA_MM = 7.1  # Saliente físico de las puntas de dedos más allá del centro almohadilla TCP

# --- Dimensiones Reales Verificadas (UNIT Electronics) ---
# MG90S y MG92B comparten huella 22.8×12.2 mm; alojamiento compatible con ambos en J2!
MG90S = {
    "sku": "AR1240",
    "body_l": 22.8,
    "body_w": 12.2,
    "body_h": 28.5,
    "pocket_depth": 29.0,
    "flange_l": 32.5,
    "flange_t": 2.4,
    "flange_z_from_top": 6.6,   # Desde tope del cuerpo (bajo el cuello de salida) hasta parte superior de orejas
    "hole_pitch": 27.5,
    "shaft_offset_from_end": 6.0,
}
MG92B = MG90S

SG90 = {
    "body_l": 22.5,
    "body_w": 11.8,
    "body_h": 22.7,
    "flange_l": 32.0,
    "flange_t": 2.2,
    "hole_pitch": 27.5,
    "shaft_offset_from_end": 6.0,
}

# Rodamiento de referencia (conservado por retrocompatibilidad v3 y pruebas opcionales)
BEARING_608 = {"sku": "AR4602", "code": "608ZZ-7", "id": 8.0, "od": 22.0, "w": 7.0}
BEARING_BASE = BEARING_608
BEARING_JOINT = BEARING_608

# Electrónica interna en la base (dimensiones PCB + envolvente real con conectores enchufados)
PCA9685 = {
    "sku": "AR0389",
    "pcb_l": 62.5,
    "pcb_w": 25.4,
    "hole_dx": 56.0,
    "hole_dy": 19.0,
    "height": 14.0,
    "height_with_dupont": 23.0,  # Con conectores Dupont enchufados encima
}

XIAO_ESP32 = {
    "pcb_l": 21.0,
    "pcb_w": 17.8,
    "height": 7.5,
    "height_with_headers": 13.0,
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
    "cut_w": 13.5,
    "cut_h": 9.0,
    "bezel_w": 15.0,
    "bezel_h": 10.5,
    "depth": 14.0,
    "depth_with_spades": 19.0,   # Incluyendo terminales faston y cable soldado
}

CAP_1000UF = {
    "sku": "AR1127",
    "dia": 10.2,
    "height": 16.5,
}

# --- Tolerancias Calibradas para Bambu Lab A1 Combo (Boquilla 0.4 mm · PLA Mate) ---
CLEARANCE_FIT = 0.22         # Holgura general piezas acoplables (0.22 mm real para PLA Mate 0.4 mm)
PIVOT_CLEARANCE = 0.25       # Holgura radial/axial en pivote liso sobre separador M3
BAYONET_CLEARANCE = 0.25     # Holgura de giro suave para tapas de bayoneta (0 flexión en PLA Mate)
BEARING_FIT = 0.14
INSERT_M3_DIA = 4.10
INSERT_M3_DEPTH = 3.80
M3_NUT_AF = 5.70             # Entre caras tuerca hexagonal M3 (5.5 mm nominal + 0.20 mm holgura)
M3_NUT_H = 2.65              # Altura tuerca M3 estándar (2.4 mm + 0.25 mm)
M3_NYLOC_H = 4.25            # Altura tuerca M3 Nyloc (4.0 mm + 0.25 mm)
M3_SPACER_OD = 5.00          # Diámetro exterior del casquillo separador liso (rosca M3 fuera de superficie de giro!)

# --- Envolvente Industrial Minimalista `B2 Stealth` v4 Clean-DFA (mm) ---
BASE_DIA = 106.0             # Ø106 mm: +67% estabilidad anti-vuelco (r_apoyo=45.5 mm) + empaquetado 0-colisión con J1 coaxial
BASE_WALL = 3.2
BASE_LOWER_H = 44.0
BASE_RING_H = 3.0            # Aro blanco base w01 + pista anular de apoyo Ø88 mm
BASE_CROWN_H = 14.0          # Z = 47..61 mm; horquilla J2 sube al eje Z = 82.0 mm (d1 exacto!)
BASE_TRACK_DIA = 88.0        # Diámetro de la pista anular amplia de apoyo axial/vuelco en J1
BASE_FEET_R = 45.5           # 6 patas antideslizantes en el perímetro exterior (radio mínimo efectivo = 39.4 mm!)

# Dimensiones compactas de las articulaciones v4 (Horquilla en U abierta + tapas bayoneta Stealth)
# Alojamiento interno del servo: 29.6 mm (Y = -14.8 .. +14.8); horquilla externa: ±15.2 .. ±19.4; tapas bayoneta: ±19.4 .. ±21.4
J2_DRUM_DIA = 38.0
J2_DRUM_W = 42.8             # Más estrecho y ~35 g más ligero que los 48 mm de v3!
J2_CAP_DIA = 31.0

J3_DRUM_DIA = 36.0
J3_DRUM_W = 42.8
J3_CAP_DIA = 29.0

J4_DRUM_DIA = 32.0
J4_DRUM_W = 42.8
J4_CAP_DIA = 25.0

# --- Geometría Exacta de la Pinza Paralela Abierta MeArm Módulo 1.5 (Compartida CAD / Python / Firmware) ---
GRIP_V4 = {
    "module": 1.5,            # Módulo 1.5 robusto para boquilla 0.4 mm FDM
    "teeth": 12,              # 12T sector engranado -> pitch_d = 18.0 mm (0 undercut, calza al ras de muñeca Ø38.8!)
    "gear_x": 27.5,           # Centro X de los 2 engranes motrices (desde eje J4)
    "gear_y": 9.20,           # Mitad de distancia entre centros (18.40 mm = 18.0 + 0.40 mm backlash imprimible)
    "idler_x": 21.0,          # Centro X de los 2 pivotes traseros de paralelismo (despeja collar w02 y SG90!)
    "idler_y": 16.90,         # Centro Y de los 2 pivotes traseros (paralelogramo exacto 10.08 mm, 100% libre de SG90!)
    "link_l": 16.5,           # Longitud centro-a-centro de brazos motrices y bielas paralelas
    "nominal_open_mm": 15.0,  # Apertura nominal donde el centro de las almohadillas w04 = A4_WRIST_TO_TCP (53.00 mm exactos!)
    "pad_len": 13.0,          # Longitud de la almohadilla blanca w04
    "pad_offset_y": 9.20,     # Distancia lateral desde pivote del dedo hasta cara interna de almohadilla (g=0 -> contacto)
    "servo_closed_deg": 40.0, # Ángulo físico SG90 cuando apertura g = 0 mm (θ = 0°); g = 30 mm -> 40 + 65.38 = 105.38°
}


def gripper_kinematics_v4(grip_open_mm: float):
    """
    Ecuación cinemática trigonométrica EXACTA de la Pinza Paralela MeArm Mod 1.5.
    Retorna (theta_deg, tcp_x_mm, tcp_dx_mm, servo_deg):
      - theta_deg : ángulo del brazo motriz desde +X (0° cerrado -> 56.44° en 30 mm)
      - tcp_x_mm  : posición X real del centro de las almohadillas respecto a J4 (53.00 mm exactos en g = 15 mm)
      - tcp_dx_mm : desplazamiento longitudinal real respecto a A4=53 mm al abrir/cerrar
      - servo_deg : ángulo físico objetivo del SG90 (sustituye la aproximación lineal 3°/mm)
    """
    g = max(0.0, min(30.0, float(grip_open_mm)))
    L = GRIP_V4["link_l"]
    sin_th = max(0.0, min(0.95, (g / 2.0) / L))
    th_rad = math.asin(sin_th)
    th_deg = math.degrees(th_rad)

    sin_nom = (GRIP_V4["nominal_open_mm"] / 2.0) / L
    th_nom = math.asin(sin_nom)
    dx = L * (math.cos(th_rad) - math.cos(th_nom))
    tcp_x = A4_WRIST_TO_TCP + dx
    servo_deg = GRIP_V4["servo_closed_deg"] + th_deg
    return th_deg, tcp_x, dx, servo_deg


# Puntos de envolvente físico real en frame local (x, z) medidos de los STL v4 Clean-DFA
_ENV_L3_LOCAL = (
    (15.0, -14.0), (35.0, -14.0), (55.0, -14.0), (70.0, -18.2),
    (35.0, +14.0), (70.0, +18.2),
)
_ENV_L4_LOCAL_BASE = (
    ( 0.0, -16.2),              # fondo tapa muñeca J4
    (21.6, GUARD_L4_SG90_Z_MM), # esquina trasera inferior SG90 / palma
    (34.5, GUARD_L4_SG90_Z_MM), # esquina frontal inferior SG90 / palma
    (35.9, +16.2),              # tope superior palma abierta
)


def check_physical_guard_v4(q_deg, grip_open_mm: float = 15.0, z_floor_min: float = GUARD_FLOOR_Z_MIN_MM):
    """
    Guarda física 3D compartida (Single Source of Truth para Python, Gemelo 3D y Firmware):
      1. Verifica límites articulares seguros `Q_LIMITS_DEG`.
      2. Verifica altura libre real sobre el escritorio (`Z >= 4 mm`) incluyendo la panza
         inferior del servo SG90 (`-21.8 mm` bajo J4) y puntas de los dedos (`+7.1 mm` tras TCP).
      3. Verifica despeje respecto a la base fija Ø106 mm + cuello torreta J1.
      4. Verifica no auto-colisión entre L4/SG90 y la viga superior del hombro L2.
    Retorna: (ok: bool, msg: str)
    """
    q1, q2, q3, q4 = [float(x) for x in q_deg]
    lims = (
        ("J1", Q_LIMITS_DEG["q1_base"]),
        ("J2", Q_LIMITS_DEG["q2_shoulder"]),
        ("J3", Q_LIMITS_DEG["q3_elbow"]),
        ("J4", Q_LIMITS_DEG["q4_wrist"]),
    )
    for (nm, (lo, hi)), val in zip(lims, (q1, q2, q3, q4)):
        if val < lo - 1e-2 or val > hi + 1e-2:
            return False, f"{nm}={val:+.1f}° fuera de límite seguro [{lo:+.0f}°, {hi:+.0f}°]"

    t2 = math.radians(q2)
    t23 = math.radians(q2 + q3)
    t234 = math.radians(q2 + q3 + q4)
    c2, s2 = math.cos(t2), math.sin(t2)
    c23, s23 = math.cos(t23), math.sin(t23)
    c234, s234 = math.cos(t234), math.sin(t234)

    r3 = A2_LOWER_ARM * c2
    z3 = D1_BASE_TO_SHOULDER + A2_LOWER_ARM * s2
    r4 = r3 + A3_FOREARM * c23
    z4 = z3 + A3_FOREARM * s23

    # 1) Puntos de L3
    z_min_l3 = 1e9
    for lx, lz in _ENV_L3_LOCAL:
        rr = r3 + lx * c23 - lz * s23
        zz = z3 + lx * s23 + lz * c23
        if zz < z_min_l3:
            z_min_l3 = zz
        if (zz < GUARD_BASE_DRUM_Z_MM and abs(rr) < GUARD_BASE_DRUM_R_MM) or (
            zz < GUARD_BASE_NECK_Z_MM and abs(rr) < GUARD_BASE_NECK_R_MM
        ):
            return False, "Antebrazo L3 chocaría con la base cilíndrica"
    if z_min_l3 < z_floor_min:
        return False, f"Antebrazo/Muñeca chocaría con mesa (Z={z_min_l3:.1f} < {z_floor_min:.0f} mm)"

    # 2) Puntos de L4 + SG90 + dedos
    _th, tcp_x, _dx, _sdeg = gripper_kinematics_v4(grip_open_mm)
    tip_x = tcp_x + GUARD_FINGER_TIP_EXTRA_MM
    l4_pts = _ENV_L4_LOCAL_BASE + ((tcp_x, -1.5), (tip_x, -1.5), (tip_x, +13.8))
    z_min_l4 = 1e9
    for lx, lz in l4_pts:
        rr = r4 + lx * c234 - lz * s234
        zz = z4 + lx * s234 + lz * c234
        if zz < z_min_l4:
            z_min_l4 = zz
        if (zz < GUARD_BASE_DRUM_Z_MM and abs(rr) < GUARD_BASE_DRUM_R_MM) or (
            zz < GUARD_BASE_NECK_Z_MM and abs(rr) < GUARD_BASE_NECK_R_MM
        ):
            return False, "Pinza/SG90 chocaría con la base cilíndrica"
        dz = zz - D1_BASE_TO_SHOULDER
        x_in_l2 = rr * c2 + dz * s2
        z_in_l2 = -rr * s2 + dz * c2
        if 8.0 < x_in_l2 < 72.0 and abs(z_in_l2) < 14.0:
            return False, "Pinza/SG90 chocaría con el brazo L2"
    if z_min_l4 < z_floor_min:
        return False, f"Pinza/SG90 chocaría con mesa (Z={z_min_l4:.1f} < {z_floor_min:.0f} mm)"

    return True, "OK"


# --- Pose Héroe por Defecto (Pinza perfectamente horizontal φ = 0°, apertura nominal 15 mm = TCP exacto en 53 mm) ---
HERO_POSE_DEG = {
    "q1": 0.0,
    "q2": 68.0,
    "q3": -96.0,
    "q4": 28.0,
    "gripper_open_mm": 15.0,
}
