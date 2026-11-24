"""
CAD Paramétrico v4 (`Clean-DFA` + 100% Estética `B2 Stealth`) — Mini-Pro 4-DOF
===============================================================================
Resuelve íntegramente los 8 hallazgos técnicos de la auditoría cruzada (Codex + DFA)
conservando intactas TODAS las restricciones de `AGENTS.md`:
  - Cinemática DH estándar 4R serial de Peter Corke: d1=82, a2=82, a3=70, a4=53 mm.
  - Límites articulares exactos: J1[-90,90], J2[15,165], J3[-135,45], J4[-90,90], Pinza[0,30 mm].
  - Estética `B2 Stealth` intacta: PLA Negro Mate + 10 piezas Blanco Mate separadas (0% purga AMS).

Correcciones estructurales y de ensamble implementadas en v4:
  [1] Sólido único conectado garantizado (`len(split()) == 1` en 100% de las piezas; L2/L3 horquillas en U).
  [2] Despeje mecánico real en todo el recorrido articular (incl. J3=-135° y Plegado Compacto, 0.00 mm³).
  [3] Pinza Paralela Abierta MeArm módulo 1.5 (sector 12T): dientes gruesos FDM con 0.35 mm backlash,
      abierta arriba, centro de almohadillas calibrado exacto en X = a4 = 53.00 mm a g=15 mm,
      engrane+brazo+horn 1 solo sólido rígido, paralelogramo exacto sin interferencia con SG90.
  [4] Base Ø106 mm con MG90S J1 coaxial centrado, retención axial independiente del horn
      (`04b_reten_axial_j1`), pista anular Ø88 mm, 6 patas perimetrales (r=45.5 mm), espacio para
      lastre y empaquetado 0-colisión incluyendo conectores Dupont enchufados y terminales KCD11.
  [5] Articulaciones J2/J3/J4 en horquilla abierta reforzada (pared 4.6 mm): acceso directo con
      desarmador (Ø5.2 mm) al tornillo del horn + acceso libre a los 2× M2 del servo + pivote pasivo
      sobre casquillo separador liso M3 (`11_separador_m3_*`, rosca M3 fuera del giro, Nyloc nunca
      frena la horquilla) + tapas laterales `B2 Stealth` con cierre de BAYONETA real (32°, 0 fatiga PLA).
  [6] Canales traseros de cables en L2/L3 con tapas deslizables en cola de milano (`dovetail`).

Exporta en `cad/exports/v4_clean_dfa/`:
  - `mini_pro_b2_stealth_v4.step` (ensamble completo nombrado para SolidWorks)
  - `stl_negro_mate/` (24 STLs estancos, 100% 1 solo sólido)
  - `stl_blanco_mate/` (10 STLs estancos, 0% purga AMS)
  - `hardware_ref/` (mallas internas incl. conectores Dupont, servos, PCBs y tornillos M3)
"""

import glob
import math
import os
import cadquery as cq

from params import (
    D1_BASE_TO_SHOULDER,
    A2_LOWER_ARM,
    A3_FOREARM,
    A4_WRIST_TO_TCP,
    BASE_DIA,
    BASE_WALL,
    BASE_LOWER_H,
    BASE_RING_H,
    BASE_CROWN_H,
    BASE_TRACK_DIA,
    BASE_FEET_R,
    BASE_FEET_DIA,
    BASE_BALLAST,
    J2_DRUM_DIA,
    J2_CAP_DIA,
    J3_DRUM_DIA,
    J3_CAP_DIA,
    J4_DRUM_DIA,
    J4_CAP_DIA,
    MG90S,
    SG90,
    PCA9685,
    XIAO_ESP32,
    USBC_PD_AR5515,
    SWITCH_KCD11,
    CAP_1000UF,
    CLEARANCE_FIT,
    PIVOT_CLEARANCE,
    BAYONET_CLEARANCE,
    M3_NUT_AF,
    M3_NUT_H,
    M3_NYLOC_H,
    M3_SPACER_OD,
    GRIP_V4,
    HERO_POSE_DEG,
    gripper_kinematics_v4,
)

# Constantes geométricas de horquillas v4 (100% paramétricas · Ronda 2 P0-1 resuelto!)
# Stackup -Y -> +Y en cada hub J2/J3/J4:
#   MG90S cuerpo: Y = -9.50 .. +19.00 (bolsillo -10.00 .. +20.5)
#   Mamparo sólido separador servo/Nyloc: Y = -11.20 .. -10.00 (1.20 mm PLA+)
#   Espacio salida punta tornillo M3×12: Y = -12.80 .. -11.20 (punta real en -11.80 -> 2.3 mm libre del MG90S!)
#   Bolsillo cautivo M3 Nyloc: Y = -17.05 .. -12.80 (Nyloc 4.0 mm en -17.00..-13.00 -> +1.20 mm salida rosca!)
#   Pared retenedora exterior hub -Y: Y = -19.00 .. -17.05 (1.95 mm sólido!)
HUB_HALF_W = 19.0     # Semiancho del bloque fijo del servo (38.0 mm total -> aloja MG90S + mamparo + Nyloc sin colisión!)
FORK_IN_Y = HUB_HALF_W + 0.40      # 19.40 mm (0.40 mm holgura axial cada lado)
FORK_THK = 4.6                     # Espesor reforzado de cada brazo de horquilla en U
FORK_OUT_Y = FORK_IN_Y + FORK_THK  # 24.00 mm -> ancho exterior sin tapas = 48.0 mm
CAP_OUT_Y = FORK_OUT_Y + 3.2       # 27.20 mm -> cavidad interior a ±26.00 (0.55 mm libre sobre cabeza M3 botón ±25.45!)


def _place_xz(shape: cq.Workplane, origin_xz, angle_deg: float) -> cq.Workplane:
    ox, oz = origin_xz
    return shape.rotate((0, 0, 0), (0, 1, 0), -angle_deg).translate((ox, 0.0, oz))


def _cyl_y(cx: float, cz: float, r: float, y0: float, y1: float) -> cq.Workplane:
    """Cilindro sobre eje Y en el intervalo exacto [min(y0,y1), max(y0,y1)] (inmune a signos XZ!)."""
    ya, yb = min(y0, y1), max(y0, y1)
    return cq.Workplane("XZ").workplane(offset=-ya).center(cx, cz).circle(r).extrude(-(yb - ya))


def _tube_y(cx: float, cz: float, r_out: float, r_in: float, y0: float, y1: float) -> cq.Workplane:
    """Tubo anular sobre eje Y en el intervalo exacto [min(y0,y1), max(y0,y1)]."""
    ya, yb = min(y0, y1), max(y0, y1)
    return cq.Workplane("XZ").workplane(offset=-ya).center(cx, cz).circle(r_out).circle(r_in).extrude(-(yb - ya))


def _sector_y(cx: float, cz: float, r_in: float, r_out: float, a0_deg: float, a1_deg: float, y0: float, y1: float, nseg: int = 8) -> cq.Workplane:
    """Sector anular en plano XZ extruido sobre eje Y en [min(y0,y1), max(y0,y1)]."""
    ya, yb = min(y0, y1), max(y0, y1)
    pts = []
    for k in range(nseg + 1):
        a = math.radians(a0_deg + (a1_deg - a0_deg) * k / nseg)
        pts.append((cx + r_out * math.cos(a), cz + r_out * math.sin(a)))
    for k in range(nseg, -1, -1):
        a = math.radians(a0_deg + (a1_deg - a0_deg) * k / nseg)
        pts.append((cx + r_in * math.cos(a), cz + r_in * math.sin(a)))
    return cq.Workplane("XZ").workplane(offset=-ya).polyline(pts).close().extrude(-(yb - ya))


def _spur_gear_sector_xy(
    teeth: int,
    module: float,
    thickness: float,
    bore_r: float,
    phase_deg: float,
    active_min_deg: float,
    active_max_deg: float,
    hub_r: float = 6.2,
) -> cq.Workplane:
    """
    Sector de engrane recto módulo 1.5 optimizado para boquilla 0.4 mm FDM:
      - Dientes conjugados perfilados con holgura lateral (0.35 mm backlash imprimible -> 0.00 mm³ solape).
      - Dientes SOLO en el arco activo de engrane (155°); el dorso mantiene un cubo liso Ø12.4 mm
        para dar >2.9 mm de luz libre al pivote trasero de paralelismo en todo el recorrido!
    """
    pitch_r = (teeth * module) / 2.0
    r_out = pitch_r + 0.78 * module
    r_root = max(bore_r + 1.0, pitch_r - 1.15 * module)
    step = 360.0 / teeth

    # Empezar con cubo base liso + añadir el arco engranado en los dientes activos
    pts = []
    n_tot = teeth
    for i in range(n_tot):
        ang_c = i * step + phase_deg
        # Normalizar a [-180, 180]
        ang_n = ((ang_c + 180.0) % 360.0) - 180.0
        in_active = (active_min_deg <= ang_n <= active_max_deg) or (active_min_deg <= ang_n + 360.0 <= active_max_deg) or (active_min_deg <= ang_n - 360.0 <= active_max_deg)
        if in_active:
            for frac, rad in [
                (-0.22, r_root),
                (-0.10, r_out),
                (+0.10, r_out),
                (+0.22, r_root),
            ]:
                ar = math.radians(ang_c + frac * step)
                pts.append((rad * math.cos(ar), rad * math.sin(ar)))
        else:
            for frac in (-0.22, 0.0, +0.22):
                ar = math.radians(ang_c + frac * step)
                pts.append((hub_r * math.cos(ar), hub_r * math.sin(ar)))

    g = cq.Workplane("XY").polyline(pts).close().extrude(thickness)
    if bore_r > 0.1:
        g = g.cut(cq.Workplane("XY").workplane(offset=-0.5).circle(bore_r).extrude(thickness + 1.0))
    return g


def _horn_recess_xz(y_inner: float, depth: float = 1.8, arm_len: float = 13.5) -> cq.Workplane:
    """
    Bolsillo empotrado del horn plástico MG90S en la cara INTERIOR del brazo +Y de la horquilla
    (Y = y_inner .. y_inner + depth) + barreno pasante Ø5.2 mm para acceso directo del desarmador
    al tornillo central del eje + 2 barrenos M2 pasantes para fijar el brazo del horn!
    """
    hub = _cyl_y(0.0, 0.0, 3.9, y_inner - 0.1, y_inner + depth)
    tip = _cyl_y(arm_len, 0.0, 2.4, y_inner - 0.1, y_inner + depth)
    arm = (
        cq.Workplane("XZ")
        .workplane(offset=-(y_inner - 0.1))
        .center(arm_len / 2.0, 0.0)
        .rect(arm_len, 5.0)
        .extrude(-(depth + 0.1))
    )
    center_driver = _cyl_y(0.0, 0.0, 2.60, y_inner - 1.0, y_inner + FORK_THK + 1.5)
    h1 = _cyl_y(8.0, 0.0, 0.95, y_inner - 1.0, y_inner + FORK_THK + 1.5)
    h2 = _cyl_y(12.5, 0.0, 0.95, y_inner - 1.0, y_inner + FORK_THK + 1.5)
    return hub.union(tip).union(arm).union(center_driver).union(h1).union(h2)


def _horn_recess_xy(z_bottom: float, depth: float = 2.0, arm_len: float = 11.5, total_thk: float = 5.0) -> cq.Workplane:
    """Bolsillo empotrado del horn SG90/MG90S en plano XY con barreno pasante Ø5.0 mm arriba para desarmador."""
    hub = cq.Workplane("XY").workplane(offset=z_bottom - 0.1).circle(3.9).extrude(depth + 0.1)
    tip = cq.Workplane("XY").workplane(offset=z_bottom - 0.1).center(arm_len, 0.0).circle(2.3).extrude(depth + 0.1)
    arm = cq.Workplane("XY").workplane(offset=z_bottom - 0.1).center(arm_len / 2.0, 0.0).rect(arm_len, 4.8).extrude(depth + 0.1)
    center_driver = cq.Workplane("XY").workplane(offset=z_bottom - 1.0).circle(2.50).extrude(total_thk + 2.5)
    h1 = cq.Workplane("XY").workplane(offset=z_bottom - 1.0).center(8.5, 0.0).circle(0.95).extrude(total_thk + 2.5)
    return hub.union(tip).union(arm).union(center_driver).union(h1)


def _bayonet_socket_cut_xz(center_xz, cap_d: float, side: int) -> cq.Workplane:
    """
    Alojamiento real de BAYONETA (giro 32°, 0 flexión PLA Mate) en la cara exterior |Y| = FORK_OUT_Y:
      - Rebaje exterior para aro blanco w_aro_* (`|Y| = 18.6 .. 19.8`)
      - Labio retenedor sólido (`|Y| = 18.6 .. 19.8`) con 3 muescas axiales de entrada (`0°, 120°, 240°`, 28°)
      - Ranura anular interna de trabado (`|Y| = 17.4 .. 18.6`) detrás del labio retenedor!
    """
    cx, cz = center_xz
    y_ext = side * FORK_OUT_Y
    y_lip = side * (FORK_OUT_Y - 1.20)   # ±18.60 mm
    y_grv = side * (FORK_OUT_Y - 2.40)   # ±17.40 mm

    r_ring_out = cap_d / 2.0 + BAYONET_CLEARANCE
    r_ring_in = cap_d / 2.0 - 1.70
    r_groove = cap_d / 2.0 - 2.15
    r_lip = cap_d / 2.0 - 3.90

    # 1. Rebaje exterior para el aro blanco
    cut = _tube_y(cx, cz, r_ring_out, r_ring_in, y_lip, y_ext + side * 0.2)
    # 2. Abertura central dentro del labio retenedor
    cut = cut.union(_cyl_y(cx, cz, r_lip, y_grv, y_ext + side * 0.2))
    # 3. Ranura interna 360° detrás del labio retenedor (|Y| = 17.40 .. 18.60)
    cut = cut.union(_tube_y(cx, cz, r_groove, r_lip - 0.5, y_grv, y_lip))
    # 4. 3 entradas axiales (span 28°) para meter las lengüetas rectas y luego girar 32°
    for k in range(3):
        a0 = k * 120.0 - 14.0
        a1 = k * 120.0 + 14.0
        cut = cut.union(_sector_y(cx, cz, r_lip - 0.5, r_groove, a0, a1, y_grv, y_ext + side * 0.2))
    return cut


def _bayonet_cap_and_ring_xz(center_xz, cap_d: float, side: int, exp_y: float = 0.0):
    """
    Construye la tapa Stealth de bayoneta (`tapa_*`) y su aro blanco separado (`w_aro_*`, 0% purga AMS).
    Incluye cavidad interior Ø12.4 mm para ocultar la cabeza del tornillo M3 y la brida del separador
    con >0.6 mm de holgura real!
    """
    cx, cz = center_xz
    y_shift = side * exp_y
    y_ring_in = side * (FORK_OUT_Y - 1.00) + y_shift  # ±18.80 (0.20 mm libre del fondo 18.60!)
    y_out = side * CAP_OUT_Y + y_shift                # ±22.40

    r_ring_out = cap_d / 2.0
    r_ring_in = cap_d / 2.0 - 1.50
    r_cap = r_ring_in - BAYONET_CLEARANCE
    r_lip = cap_d / 2.0 - 3.90
    r_collar_out = r_lip - (BAYONET_CLEARANCE + 0.05)
    r_tab_out = cap_d / 2.0 - (2.15 + BAYONET_CLEARANCE + 0.05)
    r_hollow = 5.4

    # Aro blanco B2 Stealth separado (0% purga AMS)
    white_ring = _tube_y(cx, cz, r_ring_out, r_ring_in, y_ring_in, y_out)

    # Tapa negra circular lisa exterior (`|Y| = 20.00 .. 22.40` -> 0.20 mm libre de la horquilla 19.80!)
    y_face_in = side * (FORK_OUT_Y + 0.20) + y_shift
    y_wall_in = side * (CAP_OUT_Y - 1.20) + y_shift   # Pared exterior maciza 1.20 mm
    y_collar_end = side * (FORK_OUT_Y - 2.20) + y_shift  # ±17.60 (0.20 mm libre del fondo 17.40!)
    y_tab_out = side * (FORK_OUT_Y - 1.40) + y_shift     # ±18.40 (0.20 mm libre del labio 18.60!)

    cap_disc = _cyl_y(cx, cz, r_cap, y_face_in, y_out)
    cap_collar = _tube_y(cx, cz, r_collar_out, r_hollow, y_collar_end, y_face_in + side * 0.1)
    cap_solid = cap_disc.union(cap_collar)

    # 3 lengüetas radiales de bayoneta en posición bloqueada (+34° detrás del labio retenedor!)
    for k in range(3):
        a0 = k * 120.0 + 25.0
        a1 = k * 120.0 + 43.0
        cap_solid = cap_solid.union(_sector_y(cx, cz, r_collar_out - 0.4, r_tab_out, a0, a1, y_collar_end, y_tab_out))

    # Cavidad interior Ø10.8 mm en la tapa para alojar libremente la cabeza del tornillo M3 / acceso horn
    cap_solid = cap_solid.cut(_cyl_y(cx, cz, r_hollow, y_collar_end - side * 0.2, y_wall_in))
    return cap_solid, white_ring


def _m3_pivot_spacer_xz(center_xz, exp_y: float = 0.0) -> cq.Workplane:
    """
    Casquillo separador escalonado liso (Ø5.0 exterior × Ø3.3 interior):
      - Brida Ø8.4 mm empotrada en el avellanado de la horquilla (`Y = -19.6 .. -18.4`, libre de la tapa!)
      - Camisa lisa Ø5.0 mm de longitud `3.55 mm` (`Y = -18.4 .. -14.85`) frente a espesor de pared `3.20 mm`
        -> garantiza `0.35 mm` de luz axial para que la tuerca Nyloc NUNCA frene la horquilla
        y mantiene la rosca del tornillo M3 fuera de la superficie de giro (Hallazgo #7 Codex!).
    """
    cx, cz = center_xz
    y_flange_out = -(FORK_OUT_Y - 0.20) - exp_y   # -19.60 mm (0.20 mm empotrado dentro de -19.80!)
    y_flange_in = -(FORK_OUT_Y - 1.40) - exp_y    # -18.40 mm
    y_sleeve_end = -(HUB_HALF_W + 0.05) - exp_y   # -14.85 mm (apoya firme contra el cubo fijo -14.80!)

    flange = _cyl_y(cx, cz, 4.15, y_flange_out, y_flange_in)
    sleeve = _cyl_y(cx, cz, M3_SPACER_OD / 2.0, y_flange_in, y_sleeve_end)
    bore = _cyl_y(cx, cz, 1.65, y_flange_out - 0.5, y_sleeve_end + 0.5)
    return flange.union(sleeve).cut(bore)


def _servo_hub_drum_xz(center_xz, radius: float) -> cq.Workplane:
    """Tambor sólido del alojamiento del MG90S (`Y = -14.8 .. +14.8 mm`). Se corta DESPUÉS de unir la viga!"""
    cx, cz = center_xz
    return (
        cq.Workplane("XZ")
        .center(cx, cz)
        .circle(radius)
        .extrude(HUB_HALF_W, both=True)
        .edges()
        .chamfer(0.8)
    )


def _m3_button_screw_y(cx: float, cz: float, y_seat: float, length: float, dir_y: int = +1) -> cq.Workplane:
    """Tornillo real M3 cabeza botón (Ø5.7×1.65 mm + vástago Ø2.95 mm) sobre eje Y para auditoría B-Rep."""
    y_head0 = y_seat - dir_y * 1.65
    y_tip = y_seat + dir_y * length
    head = _cyl_y(cx, cz, 2.85, y_head0, y_seat)
    shank = _cyl_y(cx, cz, 1.47, y_seat, y_tip)
    return head.union(shank)


def _m3_nyloc_y(cx: float, cz: float, y0: float, y1: float, rot_deg: float = 0.0) -> cq.Workplane:
    """Tuerca real M3 Nyloc (5.5 mm entre caras × 4.0 mm altura con barreno Ø3.0) sobre eje Y."""
    ya, yb = min(y0, y1), max(y0, y1)
    nut = cq.Workplane("XZ").workplane(offset=-ya).polygon(6, 5.5 / math.cos(math.pi / 6.0)).extrude(-(yb - ya))
    bore = _cyl_y(0.0, 0.0, 1.50, ya - 0.2, yb + 0.2)
    return nut.cut(bore).rotate((0, 0, 0), (0, 1, 0), -rot_deg).translate((cx, 0.0, cz))


def _m3_button_screw_z(cx: float, cy: float, z_seat: float, length: float, dir_z: int = +1) -> cq.Workplane:
    """Tornillo real M3 cabeza botón (Ø5.7×1.65 mm + vástago Ø2.95 mm) sobre eje Z para auditoría B-Rep."""
    z_head0 = z_seat - dir_z * 1.65
    z_tip = z_seat + dir_z * length
    za, zb = min(z_head0, z_seat), max(z_head0, z_seat)
    sa, sb = min(z_seat, z_tip), max(z_seat, z_tip)
    head = cq.Workplane("XY").workplane(offset=za).center(cx, cy).circle(2.85).extrude(zb - za)
    shank = cq.Workplane("XY").workplane(offset=sa).center(cx, cy).circle(1.47).extrude(sb - sa)
    return head.union(shank)


def _m3_selftap_screw_z(
    cx: float, cy: float, z_seat: float, length: float, dir_z: int, pilot_start_z: float
) -> cq.Workplane:
    """
    Tornillo real M3 cabeza botón autorroscante en piloto Ø2.60 mm de PLA+:
      - Cabeza completa Ø5.70 × 1.65 mm + tramo libre Ø2.95 mm hasta `pilot_start_z`
      - Tramo roscado Ø2.46 mm (diámetro menor ISO M3) dentro del piloto Ø2.60 mm hasta `z_tip`
        -> detecta al instante cualquier perforación de piso ciego o choque con lastre/Dupont!
    """
    z_head0 = z_seat - dir_z * 1.65
    z_tip = z_seat + dir_z * length
    za, zb = min(z_head0, z_seat), max(z_head0, z_seat)
    head = cq.Workplane("XY").workplane(offset=za).center(cx, cy).circle(2.85).extrude(zb - za)
    ca, cb = min(z_seat, pilot_start_z), max(z_seat, pilot_start_z)
    clr = cq.Workplane("XY").workplane(offset=ca).center(cx, cy).circle(1.47).extrude(cb - ca)
    ta, tb = min(pilot_start_z, z_tip), max(pilot_start_z, z_tip)
    tap = cq.Workplane("XY").workplane(offset=ta).center(cx, cy).circle(1.23).extrude(tb - ta)
    return head.union(clr).union(tap)


def _m3_nyloc_z(cx: float, cy: float, z0: float, z1: float, af: float = 5.5, rot_deg: float = 0.0) -> cq.Workplane:
    """Tuerca real M3 Nyloc / Hex (5.5 mm entre caras × altura z1-z0 con barreno Ø3.0) sobre eje Z."""
    za, zb = min(z0, z1), max(z0, z1)
    nut = (
        cq.Workplane("XY").workplane(offset=za).center(cx, cy)
        .transformed(rotate=(0, 0, rot_deg))
        .polygon(6, af / math.cos(math.pi / 6.0)).extrude(zb - za)
    )
    bore = cq.Workplane("XY").workplane(offset=za - 0.2).center(cx, cy).circle(1.50).extrude((zb - za) + 0.4)
    return nut.cut(bore)


def _servo_hub_cuts_xz(center_xz, tail_dir_xz) -> cq.Workplane:
    """
    Cortes completos del alojamiento MG90S (+Y) + mamparo sólido (1.20 mm) + bolsillo cautivo M3 Nyloc (-Y).
    Ronda 2 P0-1 RESUELTO: la Nyloc vive en Y = [-17.05, -12.80] mm, 100% separada del cuerpo MG90S
    (Y = [-9.50, +19.00] mm) por un mamparo macizo de 1.20 mm -> 0.00 mm³ colisión real con tuerca y tornillo!
    """
    cx, cz = center_xz
    ang_deg = math.degrees(math.atan2(tail_dir_xz[1], tail_dir_xz[0]))
    off_t = MG90S["body_l"] / 2.0 - MG90S["shaft_offset_from_end"]  # +5.4 mm hacia la cola

    # 1) Cuerpo MG90S: Y = [y_body_back .. +HUB_HALF_W + 1.5] = [-10.00 .. +20.50 mm] (0.50 mm detrás del servo!)
    y_body_back = HUB_HALF_W - MG90S["pocket_depth"]  # -10.00 mm
    body_cut = (
        cq.Workplane("XZ")
        .workplane(offset=-y_body_back)  # normal -Y -> offset=+10.0 => Y=-10.00 mm
        .center(off_t, 0.0)
        .rect(MG90S["body_l"] + CLEARANCE_FIT * 2, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-(MG90S["pocket_depth"] + 1.5))
    )
    # 2) Escalón de orejas (32.5 mm) en Y = [y_flange_back .. +HUB_HALF_W + 1.5] = [+9.80 .. +20.50 mm]
    y_flange_back = HUB_HALF_W - MG90S["flange_z_from_top"] - MG90S["flange_t"] - 0.2  # +9.80 mm
    flange_cut = (
        cq.Workplane("XZ")
        .workplane(offset=-y_flange_back)
        .center(off_t, 0.0)
        .rect(MG90S["flange_l"] + 0.8, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-(HUB_HALF_W - y_flange_back + 1.5))
    )
    # 3) 2 barrenos piloto M2 accesibles desde +Y (directo en plástico sólido detrás de orejas!)
    ear_h1 = _cyl_y(off_t + MG90S["hole_pitch"] / 2.0, 0.0, 0.90, y_flange_back - 6.0, y_flange_back + 0.5)
    ear_h2 = _cyl_y(off_t - MG90S["hole_pitch"] / 2.0, 0.0, 0.90, y_flange_back - 6.0, y_flange_back + 0.5)

    # 4) Lado pasivo -Y (100% detrás del mamparo sólido Y = -11.20..-10.00 mm):
    #    - Barreno pasante M3 + hueco de salida punta tornillo M3×12: Y = -19.50 .. -11.20 mm (punta real en -11.80!)
    #    - Bolsillo hexagonal cautivo M3 Nyloc + ranura lateral de inserción hacia -X: Y = -17.05 .. -12.80 mm
    y_nyloc_out = -(HUB_HALF_W - 1.95)  # -17.05 mm (pared retenedora exterior 1.95 mm!)
    m3_hole = _cyl_y(0.0, 0.0, 1.75, -HUB_HALF_W - 0.8, y_body_back - 1.20)
    nyloc_hex = (
        cq.Workplane("XZ")
        .workplane(offset=-y_nyloc_out)
        .polygon(6, M3_NUT_AF / math.cos(math.pi / 6.0))
        .extrude(-M3_NYLOC_H)
    )
    nyloc_slot = (
        cq.Workplane("XZ")
        .workplane(offset=-y_nyloc_out)
        .center(-9.5, 0.0)
        .rect(19.0, M3_NUT_AF)
        .extrude(-M3_NYLOC_H)
    )
    cuts = body_cut.union(flange_cut).union(ear_h1).union(ear_h2).union(m3_hole).union(nyloc_hex).union(nyloc_slot)
    return cuts.rotate((0, 0, 0), (0, 1, 0), -ang_deg).translate((cx, 0.0, cz))


def _u_fork_beam_v4(
    length: float,
    prox_hub_r: float,
    prox_cap_d: float,
    beam_w: float,
    beam_h: float,
    dist_hub_r: float,
    dist_tail_dir=(-1.0, 0.0),
):
    """
    Construye un eslabón v4 100% MONOLÍTICO (`len(split()) == 1` garantizado):
      - Horquilla en U abierta en (0, 0) abrazando el tambor previo en Y = ±[15.2, 19.8] mm
      - Puente sólido de transición en X = prox_hub_r + 3.4 .. +11.2 mm (0.00 mm³ colisión hasta J3=-135°!)
      - Viga octagonal ligera con canal trasero de cables en cola de milano (`dovetail`)
      - Alojamiento distal del siguiente MG90S en (length, 0) cortado AL FINAL (0 colisión servo!)
    Retorna: (eslabon_solido, tapa_canal_dovetail)
    """
    bridge_x0 = prox_hub_r + 3.4
    bridge_x1 = bridge_x0 + 7.6
    r_fork_ear = prox_hub_r + 1.0

    def _fork_arm(y_start: float):
        ear = _cyl_y(0.0, 0.0, r_fork_ear, y_start, y_start + FORK_THK)
        strap = (
            cq.Workplane("XZ")
            .workplane(offset=-y_start)
            .center(bridge_x1 / 2.0, 0.0)
            .rect(bridge_x1, min(beam_h + 1.4, r_fork_ear * 1.35))
            .extrude(-FORK_THK)
        )
        return ear.union(strap)

    arm_pos = _fork_arm(FORK_IN_Y)       # Y = +15.2 .. +19.8
    arm_neg = _fork_arm(-FORK_OUT_Y)     # Y = -19.8 .. -15.2

    u_bridge = (
        cq.Workplane("XY")
        .workplane(offset=-beam_h / 2.0)
        .center(0.5 * (bridge_x0 + bridge_x1), 0.0)
        .rect(bridge_x1 - bridge_x0, FORK_OUT_Y * 2.0)
        .extrude(beam_h)
        .edges("|X")
        .chamfer(2.4)
    )
    u_clear = cq.Workplane("XZ").circle(prox_hub_r + 2.5).extrude(FORK_IN_Y, both=True)
    u_fork = arm_pos.union(arm_neg).union(u_bridge).cut(u_clear)

    # Bolsillo horn + barreno Ø5.2 mm en brazo +Y
    u_fork = u_fork.cut(_horn_recess_xz(FORK_IN_Y, depth=1.8, arm_len=13.5))
    # Barreno liso Ø5.40 mm (M3_SPACER_OD + 2*PIVOT_CLEARANCE) + avellanado Ø9.2 mm en brazo -Y para el separador M3!
    u_fork = u_fork.cut(_cyl_y(0.0, 0.0, M3_SPACER_OD / 2.0 + PIVOT_CLEARANCE, -FORK_OUT_Y - 1.0, -FORK_IN_Y + 1.0))
    u_fork = u_fork.cut(_cyl_y(0.0, 0.0, 4.60, -FORK_OUT_Y - 0.5, -(FORK_OUT_Y - 1.45)))
    # Alojamiento de bayoneta real en ambas caras exteriores (±19.8 mm)
    u_fork = u_fork.cut(_bayonet_socket_cut_xz((0.0, 0.0), prox_cap_d, +1))
    u_fork = u_fork.cut(_bayonet_socket_cut_xz((0.0, 0.0), prox_cap_d, -1))

    # Viga octagonal ligera conectando puente U -> tambor distal
    beam_x0 = bridge_x0 + 2.0
    beam_x1 = length - dist_hub_r + 3.5
    ch = 2.6
    pts_oct = [
        (-beam_w / 2.0 + ch, -beam_h / 2.0),
        (beam_w / 2.0 - ch, -beam_h / 2.0),
        (beam_w / 2.0, -beam_h / 2.0 + ch),
        (beam_w / 2.0, beam_h / 2.0 - ch),
        (beam_w / 2.0 - ch, beam_h / 2.0),
        (-beam_w / 2.0 + ch, beam_h / 2.0),
        (-beam_w / 2.0, beam_h / 2.0 - ch),
        (-beam_w / 2.0, -beam_h / 2.0 + ch),
    ]
    beam = cq.Workplane("YZ").workplane(offset=beam_x0).polyline(pts_oct).close().extrude(beam_x1 - beam_x0)

    # Canal trasero de cables en cola de milano (`dovetail`, cara +Z = espalda del brazo!)
    ch_w_bot = 8.0
    ch_w_top = 6.6
    ch_d = 4.8
    z_top = beam_h / 2.0
    dove_pts = [
        (-ch_w_top / 2.0, z_top + 0.2),
        (ch_w_top / 2.0, z_top + 0.2),
        (ch_w_bot / 2.0, z_top - 1.6),
        (ch_w_bot / 2.0, z_top - ch_d),
        (-ch_w_bot / 2.0, z_top - ch_d),
        (-ch_w_bot / 2.0, z_top - 1.6),
    ]
    chan_len = max(12.0, (length - 22.5) - (beam_x0 + 2.5))
    cable_chan = cq.Workplane("YZ").workplane(offset=beam_x0 + 2.5).polyline(dove_pts).close().extrude(chan_len)

    tol = 0.25
    lid_pts = [
        (-(ch_w_top / 2.0 - tol), z_top),
        (+(ch_w_top / 2.0 - tol), z_top),
        (+(ch_w_bot / 2.0 - tol), z_top - 1.45),
        (-(ch_w_bot / 2.0 - tol), z_top - 1.45),
    ]
    cable_lid = cq.Workplane("YZ").workplane(offset=beam_x0 + 3.5).polyline(lid_pts).close().extrude(max(8.0, chan_len - 2.0))

    # Tambor distal sólido -> UNIR TODO -> CORTAR bolsillo servo AL FINAL (garantiza 0.00 mm³ colisión servo!)
    dist_drum = _servo_hub_drum_xz((length, 0.0), dist_hub_r)
    dist_cuts = _servo_hub_cuts_xz((length, 0.0), tail_dir_xz=dist_tail_dir)

    link_solid = u_fork.union(beam).union(dist_drum).cut(cable_chan).cut(dist_cuts)
    return link_solid, cable_lid


# --- Dummies visuales de hardware (incluyendo conectores enchufados para auditoría B-Rep real!) ---
def _mg90s_dummy_v4(y_shaft_face=HUB_HALF_W, tail_dir_xz=(-1.0, 0.0)) -> cq.Workplane:
    bl, bw, bh = MG90S["body_l"], MG90S["body_w"], MG90S["body_h"]
    off_t = bl / 2.0 - MG90S["shaft_offset_from_end"]
    ang_deg = math.degrees(math.atan2(tail_dir_xz[1], tail_dir_xz[0]))
    body = cq.Workplane("XZ").workplane(offset=-y_shaft_face).center(off_t, 0.0).rect(bl, bw).extrude(bh)
    flange = cq.Workplane("XZ").workplane(offset=-(y_shaft_face - 6.6)).center(off_t, 0.0).rect(MG90S["flange_l"], bw).extrude(2.4)
    shaft = _cyl_y(0.0, 0.0, 2.3, y_shaft_face, y_shaft_face + 2.0)
    return body.union(flange).union(shaft).rotate((0, 0, 0), (0, 1, 0), -ang_deg)


def _mg90s_dummy_vertical_y() -> cq.Workplane:
    """MG90S vertical con eje en (0, 0) apuntando a +Z y cuerpo extendido hacia +Y (base coaxial J1!)."""
    bl, bw, bh = MG90S["body_l"], MG90S["body_w"], MG90S["body_h"]
    off_y = bl / 2.0 - MG90S["shaft_offset_from_end"]  # +5.4 mm
    body = cq.Workplane("XY").center(0.0, off_y).rect(bw, bl).extrude(bh)
    flange = cq.Workplane("XY").workplane(offset=bh - 9.0).center(0.0, off_y).rect(bw, MG90S["flange_l"]).extrude(2.4)
    shaft = cq.Workplane("XY").workplane(offset=bh).circle(2.3).extrude(2.5)
    return body.union(flange).union(shaft)


def _sg90_dummy_coaxial_v4() -> cq.Workplane:
    bl, bw, bh = SG90["body_l"], SG90["body_w"], SG90["body_h"]
    gx, gy = GRIP_V4["gear_x"], GRIP_V4["gear_y"]
    # SG90 girado hacia +Y sobre su eje (gx, +gy) -> cuerpo Y=[+3.20..+25.70], 12.4 mm LIBRE del pivote engrane der (gx, -gy)!
    cy = gy + (bl / 2.0 - 6.0)  # +14.45 mm
    z0 = -21.3                  # Tope cuerpo Z = +1.40; orejas Z = -5.4 .. -3.2; eje Z = +1.4 .. +3.8!
    body = cq.Workplane("XY").workplane(offset=z0).center(gx, cy).rect(bw, bl).extrude(bh)
    flange = cq.Workplane("XY").workplane(offset=z0 + bh - 6.8).center(gx, cy).rect(bw, SG90["flange_l"]).extrude(2.2)
    shaft = cq.Workplane("XY").workplane(offset=z0 + bh).center(gx, gy).circle(2.3).extrude(2.4)
    return body.union(flange).union(shaft)


def build_cad_v4(pose_deg=None, explode: float = 0.0):
    """Construye el ensamblaje completo `CAD v4 Clean-DFA` (`B2 Stealth`) con 0.00 mm³ colisiones."""
    if pose_deg is None:
        pose_deg = HERO_POSE_DEG

    q1 = float(pose_deg["q1"])
    q2 = float(pose_deg["q2"])
    q3 = float(pose_deg["q3"])
    q4 = float(pose_deg["q4"])
    grip_open = float(pose_deg.get("gripper_open_mm", GRIP_V4["nominal_open_mm"]))

    black_named = {}
    white_named = {}
    servos = []
    elec_pcb = []
    steel_named = {}

    base_r = BASE_DIA / 2.0       # 53.0 mm
    cav_r = base_r - BASE_WALL    # 49.8 mm
    z_cover = 1.6                 # Piso de tapa inferior (Z = 0..1.6 mm)
    z_ballast_top = 10.0          # Bóveda inferior de lastre Z = 1.6 .. 10.0 mm (6 discos = 217.7 g B-Rep exactos!)
    z_tray0 = 10.1                # Bandeja electrónica aislante Z = 10.1 .. 12.1 mm (2.0 mm sólida -> piso ciego PCA!)
    z_tray1 = 12.1
    roof_z0 = 40.8                # Techo base Z = 40.8 .. 44.0 mm (3.2 mm sólido; retén axial en Z=37.3..40.5!)
    track_r = BASE_TRACK_DIA / 2.0  # 44.0 mm

    def apply_q1(shape):
        return shape.rotate((0, 0, 0), (0, 0, 1), q1) if abs(q1) > 1e-6 else shape

    # ==================================================================
    # 1. BASE FIJA COAXIAL Ø106 mm (`01_base_fija_v4`) — HALLAZGOS #4 y #6
    # ==================================================================
    base_shell = (
        cq.Workplane("XY")
        .circle(base_r)
        .extrude(BASE_LOWER_H)
        .edges(">Z or <Z")
        .chamfer(1.4)
    )
    base_shell = base_shell.cut(cq.Workplane("XY").workplane(offset=-0.5).circle(cav_r).extrude(roof_z0 + 0.5))
    base_shell = base_shell.cut(cq.Workplane("XY").workplane(offset=roof_z0 - 1.0).circle(17.4).extrude(6.0))
    track_groove = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - 1.4)
        .circle(track_r + 2.6)
        .circle(track_r - 2.6)
        .extrude(2.0)
    )
    base_shell = base_shell.cut(track_groove)

    # 4 jefes periféricos FUSIONADOS a la pared exterior (r=45.6 + 5.6 = 51.2 > 49.8!) en 62°, 118°, 242°, 298°
    # Comienzan en Z = z_tray1 + 0.2 = 12.3 mm -> los mismos 4× M3×16 prensan tapa inferior + lastre + bandeja!
    boss_angles_deg = (62.0, 118.0, 242.0, 298.0)
    for ang_d in boss_angles_deg:
        ang = math.radians(ang_d)
        bx, by = 45.6 * math.cos(ang), 45.6 * math.sin(ang)
        boss = cq.Workplane("XY").workplane(offset=z_tray1 + 0.2).center(bx, by).circle(5.6).extrude(10.0)
        m3_h = cq.Workplane("XY").workplane(offset=z_tray1).center(bx, by).circle(1.75).extrude(11.0)
        # Alojamiento hexagonal + ranura para tuerca M3 cautiva en Z = 14.4 .. 17.05 mm (M3×16 desde Z=1.8 llega a 17.8!)
        nut_hex = (
            cq.Workplane("XY").workplane(offset=14.4).center(bx, by)
            .transformed(rotate=(0, 0, ang_d))
            .polygon(6, M3_NUT_AF / math.cos(math.pi / 6.0)).extrude(M3_NUT_H)
        )
        nut_slot = (
            cq.Workplane("XY")
            .workplane(offset=14.4)
            .center(bx, by)
            .transformed(rotate=(0, 0, ang_d))
            .center(-3.2, 0.0)
            .rect(7.5, M3_NUT_AF)
            .extrude(M3_NUT_H)
        )
        base_shell = base_shell.union(boss).cut(m3_h).cut(nut_hex).cut(nut_slot)

    # Puente-cuna interno del MG90S J1 COAXIAL fusionado a la pared frontal +Y
    j1_z0 = 4.6
    j1_off_y = MG90S["body_l"] / 2.0 - MG90S["shaft_offset_from_end"]  # +5.4 mm
    j1_bridge = (
        cq.Workplane("XY")
        .workplane(offset=19.0)
        .center(0.0, 35.0)
        .rect(18.0, 34.0)
        .extrude(4.8)
    )
    j1_holder = (
        cq.Workplane("XY")
        .workplane(offset=19.0)
        .center(0.0, j1_off_y)
        .rect(MG90S["body_w"] + 5.8, MG90S["flange_l"] + 2.4)
        .extrude(4.8)
    )
    j1_pocket = (
        cq.Workplane("XY")
        .workplane(offset=18.0)
        .center(0.0, j1_off_y)
        .rect(MG90S["body_w"] + CLEARANCE_FIT * 2, MG90S["body_l"] + CLEARANCE_FIT * 2)
        .extrude(7.0)
    )
    j1_m2_a = cq.Workplane("XY").workplane(offset=18.0).center(0.0, j1_off_y + MG90S["hole_pitch"] / 2.0).circle(0.95).extrude(7.0)
    j1_m2_b = cq.Workplane("XY").workplane(offset=18.0).center(0.0, j1_off_y - MG90S["hole_pitch"] / 2.0).circle(0.95).extrude(7.0)

    # Bahía trasera plana en X = -50.0 mm para XIAO (subido sobre bandeja Z=18.0), AR5515 y KCD11-2P + repisa AR5515
    rear_flat = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(0.0, 21.5).rect(56.0, 26.0).extrude(6.0)
    cut_xiao_usbc = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(-16.5, 18.0).slot2D(XIAO_ESP32["usbc_w"] + 1.6, XIAO_ESP32["usbc_h"] + 1.4).extrude(16.0)
    cut_pd_usbc = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(3.5, 22.0).slot2D(USBC_PD_AR5515["usbc_w"] + 1.6, USBC_PD_AR5515["usbc_h"] + 1.4).extrude(16.0)
    cut_kcd11 = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(20.0, 22.5).rect(SWITCH_KCD11["cut_w"], SWITCH_KCD11["cut_h"]).extrude(16.0)
    rear_cable_exit = cq.Workplane("YZ").workplane(offset=-base_r - 2.0).center(0.0, 37.5).slot2D(16.0, 6.5).extrude(14.0)

    pd_shelf = (
        cq.Workplane("XY")
        .workplane(offset=15.0)
        .center(-33.5, 3.5)
        .rect(USBC_PD_AR5515["pcb_l"] + 11.0, USBC_PD_AR5515["pcb_w"] + 4.4)
        .extrude(4.2)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=18.2)
            .center(-31.0, 3.5)
            .rect(USBC_PD_AR5515["pcb_l"] + 1.0, USBC_PD_AR5515["pcb_w"] + 0.6)
            .extrude(4.0)
        )
    )

    base_shell = (
        base_shell.union(j1_bridge).union(j1_holder).union(pd_shelf)
        .cut(j1_pocket).cut(j1_m2_a).cut(j1_m2_b)
        .intersect(cq.Workplane("XY").circle(base_r - 0.05).extrude(BASE_LOWER_H))
        .cut(rear_flat).cut(cut_xiao_usbc).cut(cut_pd_usbc).cut(cut_kcd11).cut(rear_cable_exit)
    )
    black_named["01_base_fija_v4"] = base_shell

    # Dummies reales en la base (con envolventes de conectores enchufados, borneras y terminales faston!)
    servos.append(_mg90s_dummy_vertical_y().translate((0.0, 0.0, j1_z0)))
    pd_pcb = cq.Workplane("XY").workplane(offset=18.4).center(-31.0, 3.5).rect(USBC_PD_AR5515["pcb_l"], USBC_PD_AR5515["pcb_w"]).extrude(1.6)
    pd_usbc = cq.Workplane("XY").workplane(offset=20.0).center(-41.5, 3.5).rect(7.5, 9.0).extrude(3.2)
    pd_term = cq.Workplane("XY").workplane(offset=20.0).center(-20.5, 3.5).rect(7.5, 9.5).extrude(8.5)
    kcd_body = cq.Workplane("YZ").workplane(offset=-50.0).center(20.0, 22.5).rect(SWITCH_KCD11["cut_w"] - 0.5, SWITCH_KCD11["cut_h"] - 0.5).extrude(SWITCH_KCD11["depth_with_spades"])
    kcd_bezel = cq.Workplane("YZ").workplane(offset=-52.1).center(20.0, 22.5).rect(SWITCH_KCD11["bezel_w"], SWITCH_KCD11["bezel_h"]).extrude(1.9)
    elec_pcb.extend([pd_pcb, pd_term])
    steel_named["hw_pd_usbc"] = pd_usbc
    steel_named["hw_kcd_body"] = kcd_body
    steel_named["hw_kcd_bezel"] = kcd_bezel

    # ==================================================================
    # 2. TAPA INFERIOR (`03_tapa_inferior_v4`) — BÓVEDA DE LASTRE >=250g + PATAS Ø10.6 mm
    #    + BANDEJA ELECTRÓNICA AISLANTE (`03b_bandeja_electronica_v4`) — RONDA 2 P0-4 RESUELTO!
    # ==================================================================
    z_bot_exp = -42.0 * explode
    z_tray_exp = -22.0 * explode

    # Piso tapa inferior + pared perimetral de bóveda + isla protectora MG90S J1 + 4 torres pasantes M3×16 + 6 guías lastre
    bot_cover = cq.Workplane("XY").circle(cav_r - CLEARANCE_FIT).extrude(z_cover)
    vault_rim = (
        cq.Workplane("XY")
        .workplane(offset=z_cover)
        .circle(cav_r - CLEARANCE_FIT)
        .circle(cav_r - CLEARANCE_FIT - 1.6)
        .extrude(z_ballast_top - z_cover)
    )
    # Isla rectangular central alrededor del fondo del MG90S J1 (X=[-7.6,+7.6], Y=[-7.4,+18.4]) -> 0.00 mm³ choque con servo!
    j1_well = (
        cq.Workplane("XY")
        .workplane(offset=z_cover)
        .center(0.0, 5.5)
        .rect(15.2, 25.8)
        .extrude(z_ballast_top - z_cover)
        .cut(cq.Workplane("XY").workplane(offset=z_cover - 0.1).center(0.0, 5.5).rect(12.8, 23.4).extrude(z_ballast_top - z_cover + 0.5))
    )
    bot_cover = bot_cover.union(vault_rim).union(j1_well)

    # 4 torres pasantes M3 en r=45.6 (Z=1.8..11.2) -> soportan bandeja electrónica y prensan el lastre sin cascabeleo!
    for ang_d in boss_angles_deg:
        ang = math.radians(ang_d)
        bx, by = 45.6 * math.cos(ang), 45.6 * math.sin(ang)
        bot_cover = bot_cover.union(cq.Workplane("XY").workplane(offset=z_cover).center(bx, by).circle(5.2).extrude(z_ballast_top - z_cover))

    # 6 alojamientos reales de lastre (4× Ø28.6 mm [$10 MXN / rondana 1/2"] + 2× Ø26.2 mm [$5 MXN / rondana 3/8"])
    # 6 discos modelados (h=8.0 mm): volumen exacto B-Rep = 27.73 cm³ -> 217.7 g acero (SF=1.62x estable sin carga!)
    ballast_stacks = (
        (-28.0, +13.0, 14.3),
        (-28.0, -17.0, 13.1),
        (  0.0, -25.5, 14.3),
        (+28.0, -14.5, 14.3),
        (+28.0, +15.5, 14.3),
        (  0.0, +33.0, 13.1),
    )
    for b_idx, (lx, ly, lr) in enumerate(ballast_stacks):
        guide = cq.Workplane("XY").workplane(offset=z_cover).center(lx, ly).circle(lr + 0.9).circle(lr).extrude(2.4)
        bot_cover = bot_cover.union(guide)
        # Sólido real de lastre de acero modelado para auditoría B-Rep (6 discos = 217.7 g exactos!)
        b_disc = cq.Workplane("XY").workplane(offset=z_cover + 0.15 + z_bot_exp).center(lx, ly).circle(lr - 0.35).extrude(8.0)
        steel_named[f"hw_ballast_{b_idx:02d}"] = b_disc

    bot_cover = (
        bot_cover
        .intersect(cq.Workplane("XY").circle(cav_r - CLEARANCE_FIT).extrude(z_ballast_top + 0.5))
        .cut(cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(0.0, 10.0).rect(64.0, 30.0).extrude(6.8))
    )

    for b_idx, ang_d in enumerate(boss_angles_deg):
        ang = math.radians(ang_d)
        bx, by = 45.6 * math.cos(ang), 45.6 * math.sin(ang)
        bot_cover = bot_cover.cut(cq.Workplane("XY").workplane(offset=-0.5).center(bx, by).circle(1.75).extrude(z_ballast_top + 1.5))
        bot_cover = bot_cover.cut(cq.Workplane("XY").workplane(offset=-0.1).center(bx, by).circle(3.2).extrude(1.90))
        # Modelar tornillos reales M3×16 mm + tuercas hexagonales M3 cautivas (alineadas a ang_d!) para auditoría B-Rep!
        steel_named[f"hw_screw_base_{b_idx:02d}"] = _m3_button_screw_z(bx, by, 1.80 + z_bot_exp, 16.0, dir_z=+1)
        steel_named[f"hw_nut_base_{b_idx:02d}"] = _m3_nyloc_z(bx, by, 14.50, 16.90, af=5.5, rot_deg=ang_d)

    # 6 huecos para patas antideslizantes en el PERÍMETRO EXTERIOR (Ø10.6 mm -> calza topes silicona Ø10 mm Vmingo!)
    for k in range(6):
        ang_f = math.radians(k * 60.0)
        fx, fy = BASE_FEET_R * math.cos(ang_f), BASE_FEET_R * math.sin(ang_f)
        bot_cover = bot_cover.cut(cq.Workplane("XY").workplane(offset=-0.1).center(fx, fy).circle(BASE_FEET_DIA / 2.0).extrude(1.0))

    bot_cover = bot_cover.translate((0, 0, z_bot_exp))
    black_named["03_tapa_inferior_v4"] = bot_cover

    # Bandeja electrónica aislante (`03b_bandeja_electronica_v4`, Z = 10.1 .. 12.1 mm, 2.0 mm sólida, 0 soportes!)
    # Postes PCA ciegos (Z = 12.1 .. 13.7 mm, piloto Ø2.60 mm termina en Z = 11.15 -> 1.05 mm piso aislante macizo!)
    elec_tray = cq.Workplane("XY").workplane(offset=z_tray0).circle(cav_r - CLEARANCE_FIT - 0.1).extrude(z_tray1 - z_tray0)
    pca_cx, pca_cy = 22.5, 0.0
    pca_holes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            px = pca_cx + sx * (PCA9685["hole_dy"] / 2.0)
            py = pca_cy + sy * (PCA9685["hole_dx"] / 2.0)
            pca_holes.append((px, py))
            post = cq.Workplane("XY").workplane(offset=z_tray1).center(px, py).circle(3.1).extrude(1.60)
            # Barreno piloto CIEGO (Z = 11.15 .. 13.75 mm -> JAMÁS perfora Z=10.10; 100% aislado del lastre!)
            post_h = cq.Workplane("XY").workplane(offset=11.15).center(px, py).circle(1.30).extrude(2.65)
            elec_tray = elec_tray.union(post).cut(post_h)

    xiao_cx, xiao_cy = -31.5, -16.5
    xiao_cradle = (
        cq.Workplane("XY")
        .workplane(offset=z_tray1)
        .center(xiao_cx, xiao_cy)
        .rect(XIAO_ESP32["pcb_l"] + 3.0, XIAO_ESP32["pcb_w"] + 3.0)
        .extrude(3.8)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=z_tray1 + 1.6)
            .center(xiao_cx - 0.5, xiao_cy)
            .rect(XIAO_ESP32["pcb_l"] + 1.0, XIAO_ESP32["pcb_w"] + 0.6)
            .extrude(3.5)
        )
    )
    elec_tray = (
        elec_tray.union(xiao_cradle)
        .intersect(cq.Workplane("XY").workplane(offset=z_tray0 - 0.1).circle(cav_r - CLEARANCE_FIT - 0.1).extrude(10.0))
        .cut(cq.Workplane("XY").workplane(offset=z_tray0 - 0.5).center(0.0, 5.5).rect(14.0, 24.6).extrude(8.0))
        .cut(cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(0.0, 15.0).rect(64.0, 20.0).extrude(6.8))
    )
    for ang_d in boss_angles_deg:
        ang = math.radians(ang_d)
        bx, by = 45.6 * math.cos(ang), 45.6 * math.sin(ang)
        elec_tray = elec_tray.cut(cq.Workplane("XY").workplane(offset=z_tray0 - 0.5).center(bx, by).circle(1.75).extrude(4.0))

    elec_tray = elec_tray.translate((0, 0, z_tray_exp))
    black_named["03b_bandeja_electronica_v4"] = elec_tray

    # PCA9685 PCB (Z = 13.75 .. 15.35 mm, con sus 4 barrenos reales Ø3.2 mm) + 4× tornillos reales M3×4 mm!
    pca_z0 = z_tray1 + 1.65  # 13.75 mm
    pca_z1 = pca_z0 + 1.60   # 15.35 mm
    pca_pcb = cq.Workplane("XY").workplane(offset=pca_z0 + z_tray_exp).center(pca_cx, pca_cy).rect(PCA9685["pcb_w"], PCA9685["pcb_l"]).extrude(1.60)
    for p_idx, (px, py) in enumerate(pca_holes):
        pca_pcb = pca_pcb.cut(cq.Workplane("XY").workplane(offset=pca_z0 - 0.2 + z_tray_exp).center(px, py).circle(1.60).extrude(2.0))
        # M3×4 mm desde Z=15.35 -> punta en Z=11.35 mm (2.35 mm rosca en PLA+, 1.25 mm sobre piso bandeja, 1.60 mm sobre lastre!)
        steel_named[f"hw_screw_pca_{p_idx:02d}"] = _m3_selftap_screw_z(
            px, py, pca_z1 + z_tray_exp, 4.0, dir_z=-1, pilot_start_z=z_tray1 + 1.60 + z_tray_exp
        )
    # Envolvente Dupont 23.0 mm total desde base PCB (Z = 15.35 .. 36.75 mm; Y = ±24.8 mm cubre los 16×3 pines [±20.32] sin invadir barrenos ±28!)
    pca_dupont_env = cq.Workplane("XY").workplane(offset=pca_z1 + z_tray_exp).center(pca_cx, pca_cy).rect(PCA9685["pcb_w"] - 4.0, 49.6).extrude(PCA9685["height_with_dupont"] - 1.60)
    xiao_pcb = cq.Workplane("XY").workplane(offset=z_tray1 + 1.8 + z_tray_exp).center(xiao_cx, xiao_cy).rect(XIAO_ESP32["pcb_l"], XIAO_ESP32["pcb_w"]).extrude(1.6)
    xiao_usbc = cq.Workplane("XY").workplane(offset=z_tray1 + 3.4 + z_tray_exp).center(xiao_cx - XIAO_ESP32["pcb_l"] / 2.0 + 3.5, xiao_cy).rect(7.5, 9.0).extrude(3.2)
    cap_1000 = cq.Workplane("XY").workplane(offset=z_tray1 + 0.3 + z_tray_exp).center(-1.0, -34.0).circle(CAP_1000UF["dia"] / 2.0).extrude(CAP_1000UF["height"])
    elec_pcb.extend([pca_pcb, xiao_pcb, cap_1000])
    steel_named["hw_dupont_pca"] = pca_dupont_env
    steel_named["hw_xiao_usbc"] = xiao_usbc

    # ==================================================================
    # 3. ARO BLANCO BASE (`w01_aro_base_blanco` — 0% PURGA AMS)
    # ==================================================================
    z_ring_exp = 30.0 * explode
    base_ring = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H + z_ring_exp)
        .circle(base_r + 0.10)
        .circle(base_r - 3.4)
        .extrude(BASE_RING_H)
        .edges()
        .chamfer(0.3)
    )
    white_named["w01_aro_base_blanco"] = base_ring

    # ==================================================================
    # 4. TORRETA J1 COAXIAL + RETÉN AXIAL INDEPENDIENTE + HUB J2
    # ==================================================================
    z_tur_exp = 52.0 * explode
    tur_z0 = BASE_LOWER_H + BASE_RING_H  # 47.0 mm

    crown = (
        cq.Workplane("XY")
        .workplane(offset=tur_z0)
        .circle(base_r - 0.1)
        .workplane(offset=BASE_CROWN_H)
        .circle(base_r - 9.0)
        .loft(ruled=True)
    )
    track_lip = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - 1.0)
        .circle(track_r + 2.2)
        .circle(track_r - 2.2)
        .extrude(BASE_RING_H + 1.2)
    )
    neck = cq.Workplane("XY").workplane(offset=40.5).circle(17.0).circle(11.2).extrude(7.4)
    horn_boss = cq.Workplane("XY").workplane(offset=33.6).circle(10.5).extrude(14.0)
    horn_boss = horn_boss.cut(_horn_recess_xy(33.6, depth=2.2, arm_len=8.5, total_thk=28.0))

    j2_hub_r = J2_DRUM_DIA / 2.0 - 0.8  # 18.2 mm
    j2_col = (
        cq.Workplane("XY")
        .workplane(offset=tur_z0 + BASE_CROWN_H - 3.0)
        .rect(28.0, HUB_HALF_W * 2.0)
        .extrude(D1_BASE_TO_SHOULDER - (tur_z0 + BASE_CROWN_H) + 3.0)
        .edges("|Z")
        .fillet(4.0)
    )
    j1_driver_access = cq.Workplane("XY").workplane(offset=33.5).circle(3.0).extrude(34.0)
    j2_drum = _servo_hub_drum_xz((0.0, D1_BASE_TO_SHOULDER), j2_hub_r)
    j2_cuts = _servo_hub_cuts_xz((0.0, D1_BASE_TO_SHOULDER), tail_dir_xz=(0.0, -1.0))

    turret_solid = (
        crown.union(track_lip).union(neck).union(horn_boss).union(j2_col).union(j2_drum)
        .cut(j1_driver_access)
        .cut(j2_cuts)
    )
    # Cortar los 3 pilotos ciegos Ø2.60 mm DESPUÉS de unir crown+neck (Z = 40.4 .. 47.8 mm -> 0.75 mm libre sobre punta M3×8!)
    for k in range(3):
        ar = math.radians(k * 120.0 + 30.0)
        rx, ry = 14.1 * math.cos(ar), 14.1 * math.sin(ar)
        turret_solid = turret_solid.cut(cq.Workplane("XY").workplane(offset=40.4).center(rx, ry).circle(1.30).extrude(7.4))

    # Retén axial J1 (Z = 37.30 .. 40.50 mm, 3.20 mm espesor) con 3 avellanados Ø6.2 × 1.75 mm!
    # Las 3 cabezas M3×8 quedan EMBEBIDAS en Z = 37.40..39.05 -> +0.55/+0.65 mm LIBRES sobre Duponts (36.75) en 360°!
    reten_axial = cq.Workplane("XY").workplane(offset=37.30).circle(20.0).circle(11.4).extrude(3.20).edges().chamfer(0.25)
    for k in range(3):
        ar = math.radians(k * 120.0 + 30.0)
        rx, ry = 14.1 * math.cos(ar), 14.1 * math.sin(ar)
        reten_axial = reten_axial.cut(cq.Workplane("XY").workplane(offset=37.0).center(rx, ry).circle(1.70).extrude(4.0))
        reten_axial = reten_axial.cut(cq.Workplane("XY").workplane(offset=37.10).center(rx, ry).circle(3.10).extrude(1.95))
        steel_named[f"hw_screw_ret_j1_{k:02d}"] = apply_q1(
            _m3_selftap_screw_z(rx, ry, 39.05 - 14.0 * explode, 8.0, dir_z=+1, pilot_start_z=40.50 - 14.0 * explode)
        )

    black_named["04_torreta_j1_hombro_v4"] = apply_q1(turret_solid.translate((0, 0, z_tur_exp)))
    black_named["04b_reten_axial_j1"] = apply_q1(reten_axial.translate((0, 0, -14.0 * explode)))

    servos.append(apply_q1(_mg90s_dummy_v4(HUB_HALF_W, tail_dir_xz=(0.0, -1.0)).translate((0.0, 0.0, D1_BASE_TO_SHOULDER + z_tur_exp))))

    # Cinemática exacta de posiciones J2, J3, J4
    p2 = (0.0, D1_BASE_TO_SHOULDER)
    a2_rad = math.radians(q2)
    p3 = (p2[0] + A2_LOWER_ARM * math.cos(a2_rad), p2[1] + A2_LOWER_ARM * math.sin(a2_rad))
    a3_rad = math.radians(q2 + q3)
    p4 = (p3[0] + A3_FOREARM * math.cos(a3_rad), p3[1] + A3_FOREARM * math.sin(a3_rad))
    wrist_ang = q2 + q3 + q4
    a4_rad = math.radians(wrist_ang)

    # ==================================================================
    # 5. ESLABÓN L2 (`05_eslabon_l2_v4`) — 1 SOLO SÓLIDO + CANAL DOVETAIL + BAYONETA
    # ==================================================================
    exp_l2 = (22.0 * math.cos(a2_rad) * explode, 22.0 * math.sin(a2_rad) * explode + z_tur_exp)
    p2_e = (p2[0] + exp_l2[0], p2[1] + exp_l2[1])
    p3_e = (p3[0] + exp_l2[0], p3[1] + exp_l2[1])

    j3_hub_r = J3_DRUM_DIA / 2.0 - 0.8  # 17.2 mm
    l2_solid, l2_lid = _u_fork_beam_v4(
        length=A2_LOWER_ARM,
        prox_hub_r=j2_hub_r,
        prox_cap_d=J2_CAP_DIA,
        beam_w=16.5,
        beam_h=16.0,
        dist_hub_r=j3_hub_r,
        dist_tail_dir=(-1.0, 0.0),
    )
    black_named["05_eslabon_l2_v4"] = apply_q1(_place_xz(l2_solid, p2_e, q2))
    black_named["13_tapa_cable_l2"] = apply_q1(_place_xz(l2_lid.translate((0, 0, 12.0 * explode)), p2_e, q2))
    black_named["11_separador_m3_j2"] = apply_q1(_m3_pivot_spacer_xz((p2_e[0], p2_e[1]), exp_y=12.0 * explode))
    # Tornillo real M3×12 cabeza botón + Tuerca real M3 Nyloc en pivote pasivo J2 (rot_deg=-90 alineado al bolsillo!)
    steel_named["hw_screw_j2"] = apply_q1(_m3_button_screw_y(p2_e[0], p2_e[1], -(FORK_OUT_Y - 0.20) - 12.0 * explode, 12.0, dir_y=+1))
    steel_named["hw_nut_j2"] = apply_q1(_m3_nyloc_y(p2_e[0], p2_e[1], -(HUB_HALF_W - 2.00), -(HUB_HALF_W - 6.00), rot_deg=-90.0))

    for side, suf in ((-1, "izq"), (+1, "der")):
        cap, ring = _bayonet_cap_and_ring_xz((0.0, 0.0), J2_CAP_DIA, side, exp_y=18.0 * explode)
        black_named[f"tapa_j2_{suf}"] = apply_q1(_place_xz(cap, p2_e, q2))
        white_named[f"w_aro_j2_{suf}"] = apply_q1(_place_xz(ring, p2_e, q2))

    servos.append(apply_q1(_mg90s_dummy_v4(HUB_HALF_W, tail_dir_xz=(-math.cos(a2_rad), -math.sin(a2_rad))).translate((p3_e[0], 0.0, p3_e[1]))))

    # ==================================================================
    # 6. ANTEBRAZO L3 (`06_antebrazo_l3_v4`) — 1 SOLO SÓLIDO + CANAL DOVETAIL + BAYONETA
    # ==================================================================
    exp_l3 = (exp_l2[0] + 24.0 * math.cos(a3_rad) * explode, exp_l2[1] + 24.0 * math.sin(a3_rad) * explode)
    p3_f = (p3[0] + exp_l3[0], p3[1] + exp_l3[1])
    p4_f = (p4[0] + exp_l3[0], p4[1] + exp_l3[1])

    j4_hub_r = J4_DRUM_DIA / 2.0 - 0.8  # 15.2 mm
    l3_solid, l3_lid = _u_fork_beam_v4(
        length=A3_FOREARM,
        prox_hub_r=j3_hub_r,
        prox_cap_d=J3_CAP_DIA,
        beam_w=15.2,
        beam_h=14.6,
        dist_hub_r=j4_hub_r,
        dist_tail_dir=(-1.0, 0.0),
    )
    black_named["06_antebrazo_l3_v4"] = apply_q1(_place_xz(l3_solid, p3_f, q2 + q3))
    black_named["13_tapa_cable_l3"] = apply_q1(_place_xz(l3_lid.translate((0, 0, 12.0 * explode)), p3_f, q2 + q3))
    black_named["11_separador_m3_j3"] = apply_q1(_m3_pivot_spacer_xz((p3_f[0], p3_f[1]), exp_y=12.0 * explode))
    # Tornillo real M3×12 cabeza botón + Tuerca real M3 Nyloc en pivote pasivo J3 (rot_deg=q2+180 alineado al bolsillo!)
    steel_named["hw_screw_j3"] = apply_q1(_m3_button_screw_y(p3_f[0], p3_f[1], -(FORK_OUT_Y - 0.20) - 12.0 * explode, 12.0, dir_y=+1))
    steel_named["hw_nut_j3"] = apply_q1(_m3_nyloc_y(p3_f[0], p3_f[1], -(HUB_HALF_W - 2.00), -(HUB_HALF_W - 6.00), rot_deg=q2 + 180.0))

    for side, suf in ((-1, "izq"), (+1, "der")):
        cap, ring = _bayonet_cap_and_ring_xz((0.0, 0.0), J3_CAP_DIA, side, exp_y=18.0 * explode)
        black_named[f"tapa_j3_{suf}"] = apply_q1(_place_xz(cap, p3_f, q2 + q3))
        white_named[f"w_aro_j3_{suf}"] = apply_q1(_place_xz(ring, p3_f, q2 + q3))

    servos.append(apply_q1(_mg90s_dummy_v4(HUB_HALF_W, tail_dir_xz=(-math.cos(a3_rad), -math.sin(a3_rad))).translate((p4_f[0], 0.0, p4_f[1]))))

    # ==================================================================
    # 7. PINZA PARALELA ABIERTA MeArm MÓDULO 1.5 (12T, `TCP = 53.00 mm` @ g=15 mm!)
    # ==================================================================
    exp_l4 = (exp_l3[0] + 26.0 * math.cos(a4_rad) * explode, exp_l3[1] + 26.0 * math.sin(a4_rad) * explode)
    p4_g = (p4[0] + exp_l4[0], p4[1] + exp_l4[1])

    gx = GRIP_V4["gear_x"]       # 27.5 mm
    gy = GRIP_V4["gear_y"]       # 9.20 mm
    ix = GRIP_V4["idler_x"]      # 21.0 mm
    iy = GRIP_V4["idler_y"]      # 16.90 mm
    link_l = GRIP_V4["link_l"]   # 16.5 mm
    mod = GRIP_V4["module"]      # 1.5
    teeth = GRIP_V4["teeth"]     # 12T
    th_deg, tcp_x_real, _dx, _sdeg = gripper_kinematics_v4(grip_open)
    th_rad = math.radians(th_deg)
    arm_dx = link_l * math.cos(th_rad)
    arm_dy = link_l * math.sin(th_rad)
    piv_bore_r = M3_SPACER_OD / 2.0 + PIVOT_CLEARANCE  # 2.70 mm (Ø5.40 sobre casquillo Ø5.00!)

    # Horquilla proximal J4 de la palma (acceso Ø5.2 mm + separador M3 + bayoneta!)
    r_j4_ear = j4_hub_r + 1.0     # 16.2 mm
    w_bridge_x0 = j4_hub_r + 2.5  # 17.7 mm
    w_bridge_x1 = 21.0

    def _w_arm(y_start: float):
        ear = _cyl_y(0.0, 0.0, r_j4_ear, y_start, y_start + FORK_THK)
        strap = (
            cq.Workplane("XZ")
            .workplane(offset=-y_start)
            .center(w_bridge_x1 / 2.0, -1.2)
            .rect(w_bridge_x1, 10.0)
            .extrude(-FORK_THK)
        )
        return ear.union(strap)

    w_u_bridge = (
        cq.Workplane("XY")
        .workplane(offset=-3.4)
        .center(0.5 * (w_bridge_x0 + w_bridge_x1), 0.0)
        .rect(w_bridge_x1 - w_bridge_x0, FORK_OUT_Y * 2.0)
        .extrude(5.0)  # Z = -3.4 .. +1.6 mm (debajo de los engranes en Z >= +2.0!)
    )
    w_clear = cq.Workplane("XZ").circle(j4_hub_r + 2.1).extrude(FORK_IN_Y, both=True)
    w_fork = _w_arm(FORK_IN_Y).union(_w_arm(-FORK_OUT_Y)).union(w_u_bridge).cut(w_clear)
    # Despeje superior X > 16.4 mm sobre Z = +1.7 mm para que bielas y engranes giren 100% libres!
    w_fork = w_fork.cut(cq.Workplane("XY").workplane(offset=1.7).center(23.0, 0.0).rect(13.2, FORK_OUT_Y * 2.0 + 4.0).extrude(18.0))
    w_fork = w_fork.cut(_horn_recess_xz(FORK_IN_Y, depth=1.8, arm_len=12.0))
    w_fork = w_fork.cut(_cyl_y(0.0, 0.0, piv_bore_r, -FORK_OUT_Y - 1.0, -FORK_IN_Y + 1.0))
    w_fork = w_fork.cut(_cyl_y(0.0, 0.0, 4.60, -FORK_OUT_Y - 0.5, -(FORK_OUT_Y - 1.45)))
    w_fork = w_fork.cut(_bayonet_socket_cut_xz((0.0, 0.0), J4_CAP_DIA, +1))
    w_fork = w_fork.cut(_bayonet_socket_cut_xz((0.0, 0.0), J4_CAP_DIA, -1))

    # Placa base abierta arriba (`Z = -1.6 .. +1.6 mm`, CERO puente superior cerrado!)
    palm_deck = (
        cq.Workplane("XY")
        .workplane(offset=-1.6)
        .center(26.2, 0.0)
        .rect(17.2, 46.0)
        .extrude(3.2)
        .edges("|Z")
        .fillet(2.4)
    )
    # 2 pilares integrales Ø9.0 mm (Z = +1.6 .. +7.30 mm) en (ix, ±iy) con bolsillo cautivo M3 Nyloc ARRIBA de Z=+1.6!
    # 0.68 mm libres del cubo engrane + 100% por encima del cuerpo SG90 (Z<=+1.40) -> 0.000 mm³ colisión!
    idler_pillar_l = cq.Workplane("XY").workplane(offset=1.4).center(ix, +iy).circle(4.5).extrude(5.9)
    idler_pillar_r = cq.Workplane("XY").workplane(offset=1.4).center(ix, -iy).circle(4.5).extrude(5.9)

    # Carenado Stealth inferior para el SG90 coaxial girado hacia +Y bajo (gx, +gy) -> 12.4 mm LIBRE del engrane der!
    sg_cy = gy + (SG90["body_l"] / 2.0 - 6.0)  # +14.45 mm
    chin_shroud = (
        cq.Workplane("XY")
        .workplane(offset=-21.8)
        .center(gx, sg_cy)
        .rect(15.6, 35.4)
        .workplane(offset=20.4)
        .rect(16.8, 36.2)
        .loft(ruled=True)
    )
    sg_body_cut = cq.Workplane("XY").workplane(offset=-22.5).center(gx, sg_cy).rect(SG90["body_w"] + 0.6, SG90["body_l"] + 0.6).extrude(24.5)
    sg_flange_cut = cq.Workplane("XY").workplane(offset=-22.5).center(gx, sg_cy).rect(SG90["body_w"] + 0.6, SG90["flange_l"] + 0.8).extrude(19.5)
    sg_ear_h1 = cq.Workplane("XY").workplane(offset=-3.8).center(gx, sg_cy + 13.75).circle(0.90).extrude(5.5)
    sg_ear_h2 = cq.Workplane("XY").workplane(offset=-3.8).center(gx, sg_cy - 13.75).circle(0.90).extrude(5.5)

    # Ranura limpia alrededor del puente de muñeca en X = 17.1..18.7 (despeja tornillos traseros en X=20.2!)
    collar_groove = (
        cq.Workplane("YZ").workplane(offset=17.05).center(0.0, -1.2).rect(FORK_OUT_Y * 2.0 + 4.4, 6.2).extrude(1.75)
        .cut(cq.Workplane("YZ").workplane(offset=16.90).center(0.0, -1.2).rect(FORK_OUT_Y * 2.0 - 2.6, 3.4).extrude(2.1))
    )
    w02_collar = (
        cq.Workplane("YZ").workplane(offset=17.20).center(0.0, -1.2).rect(FORK_OUT_Y * 2.0 + 2.6, 5.6).extrude(1.40)
        .cut(cq.Workplane("YZ").workplane(offset=17.05).center(0.0, -1.2).rect(FORK_OUT_Y * 2.0 - 2.1, 3.8).extrude(1.75))
    )

    palm_full = (
        w_fork.union(palm_deck).union(idler_pillar_l).union(idler_pillar_r).union(chin_shroud)
        .cut(collar_groove)
        .cut(sg_body_cut).cut(sg_flange_cut).cut(sg_ear_h1).cut(sg_ear_h2)
        .cut(cq.Workplane("XZ").circle(j4_hub_r + 1.9).extrude(FORK_IN_Y, both=True))
    )
    # 1) Paso eje SG90 en (gx, +gy)
    palm_full = palm_full.cut(cq.Workplane("XY").workplane(offset=-2.5).center(gx, +gy).circle(3.0).extrude(5.0))
    # 2) Pivote engrane der (gx, -gy): M3×12 desde abajo con avellanado a Z=-0.20 (12.4 mm LIBRE del SG90!)
    palm_full = palm_full.cut(cq.Workplane("XY").workplane(offset=-2.5).center(gx, -gy).circle(1.70).extrude(5.0))
    palm_full = palm_full.cut(cq.Workplane("XY").workplane(offset=-4.0).center(gx, -gy).circle(3.20).extrude(3.80))
    # 3) 2 pivotes traseros bielas (ix, ±iy): M3×10 DESDE ARRIBA (sobre brida 1.30mm en sp_biela Z=11.90 -> punta Z=+1.90 mm!)
    #    hacia tuerca M3 Nyloc cautiva en pilar Z=+2.35..+6.60 (+0.55 mm salida rosca) + tope ciego Z=+1.70!
    #    -> +0.50 mm LIBRE sobre cuerpo SG90 (Z<=+1.40, 10× mayor margen!) y piso plástico macizo de barrera!
    for side in (+1, -1):
        py = side * iy
        palm_full = palm_full.cut(cq.Workplane("XY").workplane(offset=1.70).center(ix, py).circle(1.75).extrude(6.10))
        palm_full = palm_full.cut(
            cq.Workplane("XY").workplane(offset=2.35).center(ix, py)
            .polygon(6, M3_NUT_AF / math.cos(math.pi / 6.0)).extrude(M3_NYLOC_H)
        )
        palm_full = palm_full.cut(
            cq.Workplane("XY").workplane(offset=2.35).center(ix, py + side * 3.5)
            .rect(M3_NUT_AF, 7.0).extrude(M3_NYLOC_H)
        )

    # Recorte en esquina inferior delantera del chin_shroud para despejar L2 en Plegado Compacto
    chin_chamfer_cut = (
        cq.Workplane("XZ")
        .workplane(offset=-25.0)
        .polyline([(gx + 2.0, -23.0), (gx + 12.0, -23.0), (gx + 12.0, -13.0)])
        .close()
        .extrude(65.0)
    )
    palm_full = palm_full.cut(chin_chamfer_cut)

    black_named["07_palma_pinza_v4"] = apply_q1(_place_xz(palm_full, p4_g, wrist_ang))
    white_named["w02_collar_muneca_blanco"] = apply_q1(_place_xz(w02_collar, p4_g, wrist_ang))
    black_named["11_separador_m3_j4"] = apply_q1(_m3_pivot_spacer_xz((p4_g[0], p4_g[1]), exp_y=12.0 * explode))
    # Tornillo real M3×12 cabeza botón + Tuerca real M3 Nyloc en pivote pasivo J4 (rot_deg=q2+q3+180 alineado!)
    steel_named["hw_screw_j4"] = apply_q1(_m3_button_screw_y(p4_g[0], p4_g[1], -(FORK_OUT_Y - 0.20) - 12.0 * explode, 12.0, dir_y=+1))
    steel_named["hw_nut_j4"] = apply_q1(_m3_nyloc_y(p4_g[0], p4_g[1], -(HUB_HALF_W - 2.00), -(HUB_HALF_W - 6.00), rot_deg=q2 + q3 + 180.0))

    for side, suf in ((-1, "izq"), (+1, "der")):
        cap, ring = _bayonet_cap_and_ring_xz((0.0, 0.0), J4_CAP_DIA, side, exp_y=18.0 * explode)
        black_named[f"tapa_j4_{suf}"] = apply_q1(_place_xz(cap, p4_g, wrist_ang))
        white_named[f"w_aro_j4_{suf}"] = apply_q1(_place_xz(ring, p4_g, wrist_ang))

    servos.append(apply_q1(_place_xz(_sg90_dummy_coaxial_v4(), p4_g, wrist_ang)))

    # 2× Engranes-brazo 12T módulo 1.5 (Z = +2.0 .. +7.0 mm, 1 solo sólido rígido cada uno!)
    # Engrane derecho gira libre sobre casquillo liso Ø5.0 (`piv_bore_r = 2.70 mm` -> Ø5.40)!
    for side_name, side, fname, gear_phase, amin, amax in [
        ("izq", +1, "08_engrane_brazo_izq_m15", 0.0, -185.0, -25.0),
        ("der", -1, "09_engrane_brazo_der_m15", 180.0 / teeth, +25.0, +185.0),
    ]:
        c_bore = 2.50 if side == +1 else piv_bore_r
        g_base = _spur_gear_sector_xy(teeth, mod, 5.0, c_bore, gear_phase, amin, amax, hub_r=6.1)
        arm_bar = (
            cq.Workplane("XY")
            .center(link_l / 2.0, 0.0)
            .rect(link_l, 5.8)
            .extrude(5.0)
            .union(cq.Workplane("XY").center(link_l, 0.0).circle(3.85).extrude(5.0))
            .cut(cq.Workplane("XY").workplane(offset=-0.5).center(link_l, 0.0).circle(1.70).extrude(6.0))
            # Avellanado inferior Ø6.0 × 1.70 mm en la punta del brazo -> cabeza botón M3×16 queda 100% sobre Z=+2.05!
            .cut(cq.Workplane("XY").workplane(offset=-0.1).center(link_l, 0.0).circle(3.00).extrude(1.80))
        )
        gear_arm = (
            g_base.union(arm_bar)
            .cut(cq.Workplane("XY").workplane(offset=-0.5).circle(c_bore).extrude(6.0))
            .rotate((0, 0, 0), (0, 0, 1), side * th_deg)
        )
        if side == +1:
            gear_arm = gear_arm.cut(_horn_recess_xy(0.0, depth=2.0, arm_len=11.0, total_thk=5.0).rotate((0, 0, 0), (0, 0, 1), th_deg))
        gear_arm = gear_arm.translate((gx, side * gy, 2.0 + 4.0 * explode))
        black_named[fname] = apply_q1(_place_xz(gear_arm, p4_g, wrist_ang))

    # Casquillo liso M3 engrane derecho (Z = +1.65 .. +7.05 mm -> Nyloc aprieta casquillo y deja engrane libre!)
    sp_gear_r = (
        cq.Workplane("XY").workplane(offset=1.65 + 4.0 * explode).center(gx, -gy)
        .circle(M3_SPACER_OD / 2.0).circle(1.65).extrude(5.40)
    )
    black_named["11b_separador_pinza_engrane"] = apply_q1(_place_xz(sp_gear_r, p4_g, wrist_ang))

    # 2× Bielas traseras paralelas (`12_biela_pinza_izq/der_v4`, Z = +7.4 .. +10.4 mm, L = 16.5 mm)
    # Extremo proximal (sobre pilar palma) con barreno Ø5.40 mm para casquillo liso M3!
    for side_name, side in [("izq", +1), ("der", -1)]:
        biela = (
            cq.Workplane("XY")
            .center(link_l / 2.0, 0.0)
            .rect(link_l, 5.2)
            .extrude(3.0)
            .union(cq.Workplane("XY").circle(3.8).extrude(3.0))
            .union(cq.Workplane("XY").center(link_l, 0.0).circle(3.1).extrude(3.0))
            .cut(cq.Workplane("XY").workplane(offset=-0.5).circle(piv_bore_r).extrude(4.0))
            .cut(cq.Workplane("XY").workplane(offset=-0.5).center(link_l, 0.0).circle(1.70).extrude(4.0))
            .rotate((0, 0, 0), (0, 0, 1), side * th_deg)
            .translate((ix, side * iy, 7.4 + 9.0 * explode))
        )
        black_named[f"12_biela_pinza_{side_name}_v4"] = apply_q1(_place_xz(biela, p4_g, wrist_ang))
        sp_biela = (
            cq.Workplane("XY").workplane(offset=7.35 + 9.0 * explode).center(ix, side * iy)
            .circle(M3_SPACER_OD / 2.0).circle(1.65).extrude(3.25)
            .union(
                cq.Workplane("XY").workplane(offset=10.60 + 9.0 * explode).center(ix, side * iy)
                .circle(3.25).circle(1.65).extrude(1.30)
            )
        )
        black_named[f"11c_separador_pinza_biela_{side_name}"] = apply_q1(_place_xz(sp_biela, p4_g, wrist_ang))

    # 2× Dedos paralelos (`10_dedo_pinza_*_v4`) + `2×` Almohadillas blancas (`w04_almohadilla_*`)
    # Calibrados EXACTAMENTE para que el centro de w04 = (53.000, 0.0, +5.800) mm en g = 15 mm!
    f_front_x = gx + arm_dx
    f_rear_x = ix + arm_dx
    pad_len = GRIP_V4["pad_len"]          # 13.0 mm
    pad_cx = tcp_x_real                   # 53.000 mm exactos cuando g = 15.0 mm!
    pad_x0 = pad_cx - pad_len / 2.0       # 46.50 mm en nominal
    pad_x1 = pad_cx + pad_len / 2.0       # 59.50 mm en nominal
    jaw_x0 = pad_x0 - 0.25                # 46.25 mm -> +0.20 mm libre del jefe Ø7.7 del brazo en g=0..30 mm!
    jaw_x1 = pad_x1 + 0.6                 # 60.10 mm

    for side_name, side in [("izq", +1), ("der", -1)]:
        fy_front = side * (gy + arm_dy)
        fy_rear = side * (iy + arm_dy)
        inner_y = fy_front - side * GRIP_V4["pad_offset_y"]  # En g=0 -> 0.0; en g=15 -> ±7.50 mm exactos!

        # Puente diagonal rígido uniendo ambos pivotes del paralelogramo arriba (`Z = +10.8 .. +13.8 mm`)
        # Jefes reforzados Ø8.0 / Ø7.8 mm con barrenos Ø5.40 mm sobre casquillos escalonados lisos M3!
        boss_f = cq.Workplane("XY").workplane(offset=10.8).center(f_front_x, fy_front).circle(4.0).extrude(3.0)
        boss_r = cq.Workplane("XY").workplane(offset=10.8).center(f_rear_x, fy_rear).circle(3.9).extrude(3.0)
        dx_p = f_front_x - f_rear_x
        dy_p = fy_front - fy_rear
        diag_len = math.hypot(dx_p, dy_p)
        diag_ang = math.degrees(math.atan2(dy_p, dx_p))
        pivot_bar = (
            cq.Workplane("XY")
            .workplane(offset=10.8)
            .center(0.5 * (f_front_x + f_rear_x), 0.5 * (fy_front + fy_rear))
            .transformed(rotate=(0, 0, diag_ang))
            .rect(diag_len, 6.2)
            .extrude(3.0)
            .union(boss_f)
            .union(boss_r)
        )
        neck_pts = [
            (f_front_x, fy_front - side * 2.5),
            (jaw_x0 + 2.4, inner_y + side * 1.65),
            (jaw_x0 + 2.4, fy_front + side * 3.0),
            (f_front_x, fy_front + side * 3.0),
        ]
        if side < 0:
            neck_pts = list(reversed(neck_pts))
        neck = cq.Workplane("XY").workplane(offset=10.8).polyline(neck_pts).close().extrude(3.0)

        pts_jaw = [
            (jaw_x0, inner_y + side * 1.65),
            (jaw_x1, inner_y + side * 1.65),
            (jaw_x1, inner_y + side * 5.2),
            (jaw_x0 + 2.4, fy_front + side * 3.0),
            (jaw_x0, fy_front + side * 3.0),
        ]
        if side < 0:
            pts_jaw = list(reversed(pts_jaw))
        jaw = cq.Workplane("XY").workplane(offset=-1.2).polyline(pts_jaw).close().extrude(15.0).edges("|Z").fillet(0.30)

        finger = pivot_bar.union(neck).union(jaw)
        finger = finger.cut(cq.Workplane("XY").workplane(offset=10.0).center(f_front_x, fy_front).circle(piv_bore_r).extrude(4.5))
        finger = finger.cut(cq.Workplane("XY").workplane(offset=10.0).center(f_rear_x, fy_rear).circle(piv_bore_r).extrude(4.5))

        # Casquillos escalonados lisos M3 en pivotes delantero y trasero del dedo (evitan que la Nyloc trabe el dedo!)
        sp_df = (
            cq.Workplane("XY").workplane(offset=7.05).center(f_front_x, fy_front).circle(3.2).extrude(3.60)
            .union(cq.Workplane("XY").workplane(offset=10.65).center(f_front_x, fy_front).circle(M3_SPACER_OD / 2.0).extrude(3.40))
            .cut(cq.Workplane("XY").workplane(offset=6.8).center(f_front_x, fy_front).circle(1.65).extrude(7.6))
        )
        sp_dr = (
            cq.Workplane("XY").workplane(offset=10.45).center(f_rear_x, fy_rear).circle(3.1).extrude(0.25)
            .union(cq.Workplane("XY").workplane(offset=10.70).center(f_rear_x, fy_rear).circle(M3_SPACER_OD / 2.0).extrude(3.35))
            .cut(cq.Workplane("XY").workplane(offset=10.2).center(f_rear_x, fy_rear).circle(1.65).extrude(4.2))
        )
        black_named[f"11d_separador_pinza_dedo_f_{side_name}"] = apply_q1(_place_xz(sp_df.translate((0, side * 14.0 * explode, 0)), p4_g, wrist_ang))
        black_named[f"11e_separador_pinza_dedo_r_{side_name}"] = apply_q1(_place_xz(sp_dr.translate((0, side * 14.0 * explode, 0)), p4_g, wrist_ang))

        # Tornillos M3 reales con cabeza botón + Tuercas M3 Nyloc reales (auditados en B-Rep en g=0..30 mm!):
        # - Delantero: M3×16 avellanado bajo engrane (cabeza Z=2.05..3.70, punta Z=19.70; Nyloc 14.10..18.10 -> +1.60 mm!)
        # - Trasero  : M3×12 desde abajo (cabeza Z=5.70..7.35, punta Z=19.35; Nyloc 14.10..18.10 -> +1.25 mm!)
        steel_named[f"hw_screw_df_{side_name}"] = apply_q1(_place_xz(_m3_button_screw_z(f_front_x, fy_front, 3.70, 16.0, dir_z=+1), p4_g, wrist_ang))
        steel_named[f"hw_nut_df_{side_name}"] = apply_q1(_place_xz(_m3_nyloc_z(f_front_x, fy_front, 14.10, 18.10), p4_g, wrist_ang))
        steel_named[f"hw_screw_dr_{side_name}"] = apply_q1(_place_xz(_m3_button_screw_z(f_rear_x, fy_rear, 7.35, 12.0, dir_z=+1), p4_g, wrist_ang))
        steel_named[f"hw_nut_dr_{side_name}"] = apply_q1(_place_xz(_m3_nyloc_z(f_rear_x, fy_rear, 14.10, 18.10), p4_g, wrist_ang))

        # Almohadilla blanca w04 (13.0 × 10.4 × 1.6 mm, cara interna en ±g/2, centro = (53.000, 0, +5.800) mm @ g=15!)
        pts_pad = [
            (pad_x0, inner_y),
            (pad_x1, inner_y),
            (pad_x1, inner_y + side * 1.60),
            (pad_x0, inner_y + side * 1.60),
        ]
        if side < 0:
            pts_pad = list(reversed(pts_pad))
        pad = cq.Workplane("XY").workplane(offset=0.6).polyline(pts_pad).close().extrude(10.4)

        black_named[f"10_dedo_pinza_{side_name}_v4"] = apply_q1(_place_xz(finger.translate((0, side * 14.0 * explode, 0)), p4_g, wrist_ang))
        white_named[f"w04_almohadilla_{side_name}"] = apply_q1(_place_xz(pad.translate((0, side * 18.0 * explode, 0)), p4_g, wrist_ang))

    # Tornillos reales M3 + Tuercas M3 Nyloc de la palma (3 pivotes pasivos; el 4º es el eje SG90!):
    # - Engrane der (gx, -gy): M3×12 desde abajo (Z=-0.20..+11.80) + Nyloc Z=7.10..11.10 (+0.70 mm tras nylon, 12.4 mm libre SG90!)
    # - Bielas izq/der (ix, ±iy): M3×10 DESDE ARRIBA (brida Z=11.90 -> punta Z=+1.90 mm, +0.50 mm libre sobre SG90!) hacia Nyloc Z=2.45..6.45 (+0.55 mm!)
    steel_named["hw_screw_gear_r"] = apply_q1(_place_xz(_m3_button_screw_z(gx, -gy, -0.20, 12.0, dir_z=+1), p4_g, wrist_ang))
    steel_named["hw_nut_gear_r"] = apply_q1(_place_xz(_m3_nyloc_z(gx, -gy, 7.10, 11.10), p4_g, wrist_ang))
    for s_tag, sy in (("izq", +iy), ("der", -iy)):
        steel_named[f"hw_screw_biela_{s_tag}"] = apply_q1(_place_xz(_m3_button_screw_z(ix, sy, 11.90, 10.0, dir_z=-1), p4_g, wrist_ang))
        steel_named[f"hw_nut_biela_{s_tag}"] = apply_q1(_place_xz(_m3_nyloc_z(ix, sy, 2.45, 6.45), p4_g, wrist_ang))

    return {
        "black_named": black_named,
        "white_named": white_named,
        "black": list(black_named.values()),
        "white": list(white_named.values()),
        "servos": servos,
        "elec_pcb": elec_pcb,
        "steel": list(steel_named.values()),
        "steel_named": steel_named,
        "tcp_x_mm": tcp_x_real,
        "grip_theta_deg": th_deg,
    }


def export_all_v4(out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    blk_dir = os.path.join(out_dir, "stl_negro_mate")
    wht_dir = os.path.join(out_dir, "stl_blanco_mate")
    hw_dir = os.path.join(out_dir, "hardware_ref")
    for d in (blk_dir, wht_dir, hw_dir):
        os.makedirs(d, exist_ok=True)
        for old in glob.glob(os.path.join(d, "*.stl")):
            os.remove(old)

    parts = build_cad_v4(HERO_POSE_DEG, explode=0.0)

    assy = cq.Assembly(name="MiniPro_4DOF_B2_Stealth_v4_CleanDFA")
    for name, s in parts["black_named"].items():
        assy.add(s, name=name, color=cq.Color(0.11, 0.11, 0.13, 1.0))
        cq.exporters.export(s, os.path.join(blk_dir, f"{name}.stl"), tolerance=0.04, angularTolerance=0.1)
    for name, s in parts["white_named"].items():
        assy.add(s, name=name, color=cq.Color(0.95, 0.95, 0.96, 1.0))
        cq.exporters.export(s, os.path.join(wht_dir, f"{name}.stl"), tolerance=0.04, angularTolerance=0.1)

    hw_groups = [
        ("hw_servo", parts["servos"], cq.Color(0.10, 0.44, 0.85, 1.0)),
        ("hw_elec", parts["elec_pcb"], cq.Color(0.08, 0.56, 0.28, 1.0)),
        ("hw_steel", parts["steel"], cq.Color(0.75, 0.77, 0.80, 1.0)),
    ]
    for prefix, shapes, col in hw_groups:
        for idx, s in enumerate(shapes):
            nm = f"{prefix}_{idx:02d}"
            assy.add(s, name=nm, color=col)
            cq.exporters.export(s, os.path.join(hw_dir, f"{nm}.stl"), tolerance=0.06, angularTolerance=0.15)

    step_path = os.path.join(out_dir, "mini_pro_b2_stealth_v4.step")
    assy.save(step_path)
    print(f"[OK] Exported STEP v4 Clean-DFA: {step_path}")
    print(f"[OK] Negro Mate: {len(parts['black_named'])} STLs | Blanco Mate: {len(parts['white_named'])} STLs | Hardware: {len(parts['servos'])+len(parts['elec_pcb'])+len(parts['steel'])} STLs")
    print(f"[OK] Pinza v4 nominal (15 mm): theta = {parts['grip_theta_deg']:.2f} deg | centro almohadilla = {parts['tcp_x_mm']:.2f} mm (A4 = {A4_WRIST_TO_TCP:.2f} mm)")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    export_all_v4(os.path.join(here, "exports", "v4_clean_dfa"))
