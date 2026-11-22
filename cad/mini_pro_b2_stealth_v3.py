"""
CAD Paramétrico v3 (DFM / Ensamble Real — Revisión A + B + C) — Mini-Pro 4-DOF (`B2 Stealth`)
=============================================================================================
Evolución de manufactura y ensamble real sobre v2 resolviendo los 6 puntos críticos de taller:

  [Revisión A — Articulaciones J2, J3, J4 y Cables Continuos]
    1. Eje metálico real en rodamientos 608ZZ: elimina el muñón impreso que no cabía en la
       horquilla; cada articulación usa un buje centrador (`11_buje_608zz_*`) + tornillo M3×10
       entrando desde -Y hasta un inserto térmico de latón `AR2811` (Ø 4.1 mm) en el eslabón.
    2. Acceso real por cara +Y para insertar/retirar cada `MG90S` con sus orejas (`32.5 mm`),
       escalón de apoyo interno y 2 barrenos piloto M2 (`hole_pitch = 27.5 mm`).
    3. Bolsillo empotrado de `1.9 mm` con la silueta del *horn* plástico del `MG90S` en cada
       disco motriz (`L2`, `L3`, `Palma`) + barreno central + 2 pilotos M1.6 (cero juego).
    4. Ductos internos de cables continuos (`10 × 8 mm`) abiertos hasta la cavidad de cada servo
       y salidas ovaladas cerca del eje para pasar conectores Dupont de 3 pines sin desarmarlos.
    5. Tapas laterales Stealth (`tapa_j2/j3/j4`) con ceja de encaje centradora + 2 barrenos M3
       avellanados alineados con barrenos piloto en los tambores.

  [Revisión B — Pinza Paralela Real de 4 Barras (`SG90` Coaxial)]
    6. `SG90` reubicado en orientación transversal y **coaxial bajo el engrane izquierdo `14T`**
       (`G_L = (30.0, +7.12)`), accesible desde abajo con escalones de montaje para sus orejas.
    7. Paralelogramo verdadero de 4 barras: 2 engranes-brazo `14T` de una sola pieza
       (`08/09_engrane_brazo_*`, el izquierdo con bolsillo de *horn* `SG90`), 2 bielas traseras
       de paralelismo (`12_biela_pinza_*`, L=16 mm) y 2 dedos con puente de doble pivote M3
       (`|G-I| = 9.0 mm`, apertura paralela real 0–30 mm, TCP exacto en a4 = 53 mm).

  [Revisión C — Base Fija, Transmisión 22T Antideslizamiento y Electrónica]
    8. Corte plano en D (chaveta `1.1 mm`) en el eje inferior de `04_torreta_j1_hombro` + barreno
       en D en `04b_engrane_torreta_22t` (cero patinaje en J1) + bolsillo *horn* en `02_pinon_base_22t`.
    9. Barrenos M3 en los 4 postes del `PCA9685`, pilotos M2 en `MG90S J1`, pestañas de retención
       para `XIAO` y `AR5515`, avellanados M3 y 4 huecos para gomitas antideslizantes en la tapa base.

Exporta:
  - `cad/exports/mini_pro_b2_stealth_v3.step` (ensamble completo nombrado para SolidWorks)
  - `cad/exports/stl_negro_mate/` (23 STLs estancos)
  - `cad/exports/stl_blanco_mate/` (12 STLs estancos)
  - `cad/exports/hardware_ref/` (mallas internas para Visor 3D y Gemelo Digital)
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
    BASE_LOWER_H,
    BASE_RING_H,
    BASE_CROWN_H,
    J2_DRUM_DIA,
    J2_DRUM_W,
    J2_CAP_DIA,
    J3_DRUM_DIA,
    J3_DRUM_W,
    J3_CAP_DIA,
    J4_DRUM_DIA,
    J4_DRUM_W,
    J4_CAP_DIA,
    MG90S,
    SG90,
    BEARING_608,
    PCA9685,
    XIAO_ESP32,
    USBC_PD_AR5515,
    SWITCH_KCD11,
    CAP_1000UF,
    CLEARANCE_FIT,
    BEARING_FIT,
    INSERT_M3_DIA,
    INSERT_M3_DEPTH,
    HERO_POSE_DEG,
)

# --- Constantes cinemáticas exactas de la Pinza Paralela de 4 Barras (Revisión B) ---
GRIP_GEAR_X = 30.0     # Centro X de los 2 engranes motrices 14T (módulo 1.0)
GRIP_GEAR_Y = 7.12     # Mitad de distancia entre centros (14.24 mm = 14T + 0.24 mm holgura PLA)
GRIP_IDLER_X = 21.0    # Centro X de los 2 pivotes traseros de paralelismo (|G - I| = 9.0 mm)
GRIP_LINK_L = 16.0     # Longitud centro-a-centro de brazos motrices y bielas paralelas
GRIP_PIVOT_SEP = GRIP_GEAR_X - GRIP_IDLER_X  # 9.0 mm exactos


def gripper_angle_deg(grip_open_mm: float) -> float:
    """Ángulo de apertura (en grados desde +X) del paralelogramo de 4 barras para apertura `grip_open_mm`."""
    # Con mordaza interior a 7.1 mm hacia adentro del pivote del dedo:
    # half_gap = GRIP_GEAR_Y + GRIP_LINK_L * sin(theta) - 7.1  ->  sin(theta) = (grip_open_mm / 2.0) / GRIP_LINK_L
    # Verificación: grip=0 -> theta=0° (half_gap=0); grip=16 -> theta=30° (half_gap=8); grip=30 -> theta=69.6° (half_gap=15)
    s = max(0.0, min(0.95, (grip_open_mm / 2.0) / GRIP_LINK_L))
    return math.degrees(math.asin(s))


def _place_xz(shape: cq.Workplane, origin_xz, angle_deg: float) -> cq.Workplane:
    ox, oz = origin_xz
    return shape.rotate((0, 0, 0), (0, 1, 0), -angle_deg).translate((ox, 0.0, oz))


def _spur_gear(teeth: int, module: float, thickness: float, bore_r: float) -> cq.Workplane:
    pitch_r = (teeth * module) / 2.0
    addendum = 0.90 * module
    dedendum = 1.15 * module
    r_out = pitch_r + addendum
    r_root = max(bore_r + 0.8, pitch_r - dedendum)
    pts = []
    step = 2.0 * math.pi / teeth
    for i in range(teeth):
        a0 = i * step
        a1 = a0 + step * 0.16
        a2 = a0 + step * 0.30
        a3 = a0 + step * 0.56
        a4 = a0 + step * 0.70
        pts.append((r_root * math.cos(a1), r_root * math.sin(a1)))
        pts.append((r_out * math.cos(a2), r_out * math.sin(a2)))
        pts.append((r_out * math.cos(a3), r_out * math.sin(a3)))
        pts.append((r_root * math.cos(a4), r_root * math.sin(a4)))
    g = cq.Workplane("XY").polyline(pts).close().extrude(thickness)
    if bore_r > 0.1:
        g = g.cut(cq.Workplane("XY").workplane(offset=-0.5).circle(bore_r).extrude(thickness + 1.0))
    return g


def _horn_recess_xy(depth: float = 2.0, arm_len: float = 15.0, z0: float = 0.0) -> cq.Workplane:
    """Silueta 3D exacta del horn plástico estándar de MG90S/SG90 para sustraer (cero juego)."""
    hub = cq.Workplane("XY").workplane(offset=z0).circle(3.15).extrude(depth)
    arm = (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .polyline([(0.0, -2.1), (arm_len, -1.55), (arm_len, 1.55), (0.0, 2.1)])
        .close()
        .extrude(depth)
    )
    tip = cq.Workplane("XY").workplane(offset=z0).center(arm_len, 0.0).circle(1.55).extrude(depth)
    return hub.union(arm).union(tip)


def _horn_recess_xz(y_face: float, depth: float = 1.9, arm_len: float = 14.5, dir_sign: float = -1.0) -> cq.Workplane:
    """Bolsillo de horn MG90S tallado en plano XZ (entra desde `y_face` en dirección `dir_sign` hacia Y)."""
    # En Workplane("XZ"), normal es -Y -> offset = -y_face pone el plano en Y = y_face; extrude(+d) va hacia -Y
    ext = depth if dir_sign < 0 else -depth
    hub = cq.Workplane("XZ").workplane(offset=-y_face).circle(3.15).extrude(ext)
    arm = (
        cq.Workplane("XZ")
        .workplane(offset=-y_face)
        .polyline([(0.0, -2.1), (arm_len, -1.55), (arm_len, 1.55), (0.0, 2.1)])
        .close()
        .extrude(ext)
    )
    tip = cq.Workplane("XZ").workplane(offset=-y_face).center(arm_len, 0.0).circle(1.55).extrude(ext)
    # Barreno central de tornillo del eje + 2 pilotos M1.6 sobre el brazo del horn
    scr_c = cq.Workplane("XZ").workplane(offset=-(y_face + 1.0)).circle(1.30).extrude(ext + (2.0 if ext > 0 else -2.0))
    p1 = cq.Workplane("XZ").workplane(offset=-y_face).center(8.5, 0.0).circle(0.75).extrude(ext * 1.9)
    p2 = cq.Workplane("XZ").workplane(offset=-y_face).center(12.5, 0.0).circle(0.75).extrude(ext * 1.9)
    return hub.union(arm).union(tip).union(scr_c).union(p1).union(p2)


def _octagonal_beam_continuous_duct(length: float, h0: float, h1: float, w0: float, w1: float, chamfer: float, duct_w: float, duct_h: float) -> cq.Workplane:
    """Viga octagonal hueca con canal CONTINUO abierto en ambos extremos para conectores Dupont 3-pin."""
    def oct_pts(w, h, c):
        hw, hh = w / 2.0, h / 2.0
        c = min(c, hw * 0.44, hh * 0.44)
        return [
            (-hw + c, -hh), (hw - c, -hh), (hw, -hh + c), (hw, hh - c),
            (hw - c, hh), (-hw + c, hh), (-hw, hh - c), (-hw, -hh + c),
        ]

    outer = (
        cq.Workplane("YZ")
        .polyline(oct_pts(w0, h0, chamfer))
        .close()
        .workplane(offset=length)
        .polyline(oct_pts(w1, h1, chamfer * 0.85))
        .close()
        .loft(ruled=True)
    )
    # Ducto interno pasante desde X = 14 mm hasta el bolsillo del servo distal (length - 4 mm)
    duct = (
        cq.Workplane("YZ")
        .workplane(offset=14.0)
        .rect(duct_w, duct_h)
        .extrude(max(6.0, length - 14.0))
    )
    # Ventana ovalada de salida inferior (-Z) en el extremo proximal (X = 18..28 mm) para bajada limpia del cable
    exit_port = (
        cq.Workplane("XY")
        .workplane(offset=-h0 / 2.0 - 2.0)
        .center(22.0, 0.0)
        .slot2D(11.0, duct_w, angle=0.0)
        .extrude(h0 / 2.0 + 2.5)
    )
    return outer.cut(duct).cut(exit_port)


def _bushing_608_m3() -> cq.Workplane:
    """Buje centrador impreso (`Ø 7.86 -> Ø 3.3 mm`) con pestaña externa para tornillo M3×10 en 608ZZ."""
    shaft_r = (BEARING_608["id"] - BEARING_FIT) / 2.0  # 3.93 mm
    flange = cq.Workplane("XY").circle(5.8).extrude(1.4)
    sleeve = cq.Workplane("XY").workplane(offset=1.4).circle(shaft_r).extrude(BEARING_608["w"] + 0.1)
    bore = cq.Workplane("XY").workplane(offset=-0.5).circle(1.65).extrude(BEARING_608["w"] + 2.5)
    return flange.union(sleeve).cut(bore)


def _mg90s_dummy_vertical() -> cq.Workplane:
    bl, bw, bh = MG90S["body_l"], MG90S["body_w"], MG90S["body_h"]
    off_x = bl / 2.0 - MG90S["shaft_offset_from_end"]  # +5.4 mm
    body = cq.Workplane("XY").center(off_x, 0.0).rect(bl, bw).extrude(bh)
    flange = cq.Workplane("XY").workplane(offset=bh - 9.0).center(off_x, 0.0).rect(MG90S["flange_l"], bw).extrude(2.4)
    shaft = cq.Workplane("XY").workplane(offset=bh).circle(2.4).extrude(3.5)
    return body.union(flange).union(shaft)


def _mg90s_dummy_joint(tail_dir_xz=(0.0, -1.0), y_shaft_end=-7.5) -> cq.Workplane:
    bl, bw, bh = MG90S["body_l"], MG90S["body_w"], MG90S["body_h"]
    off_t = bl / 2.0 - MG90S["shaft_offset_from_end"]  # +5.4 mm
    ang_deg = math.degrees(math.atan2(tail_dir_xz[1], tail_dir_xz[0]))
    body = (
        cq.Workplane("XZ")
        .workplane(offset=-y_shaft_end)
        .center(off_t, 0.0)
        .rect(bl, bw)
        .extrude(-bh)
    )
    flange = (
        cq.Workplane("XZ")
        .workplane(offset=-(y_shaft_end + 8.5))
        .center(off_t, 0.0)
        .rect(MG90S["flange_l"], bw)
        .extrude(2.4)
    )
    shaft = (
        cq.Workplane("XZ")
        .workplane(offset=-y_shaft_end)
        .circle(2.4)
        .extrude(3.2)
    )
    return body.union(flange).union(shaft).rotate((0, 0, 0), (0, 1, 0), -ang_deg)


def _sg90_dummy_coaxial() -> cq.Workplane:
    """SG90 real orientado transversalmente con su eje coaxial en (GRIP_GEAR_X, +GRIP_GEAR_Y) apuntando hacia +Z."""
    bl, bw, bh = SG90["body_l"], SG90["body_w"], SG90["body_h"]
    cy = GRIP_GEAR_Y - (bl / 2.0 - 6.0)
    z0 = -23.0
    body = cq.Workplane("XY").workplane(offset=z0).center(GRIP_GEAR_X, cy).rect(bw, bl).extrude(bh)
    flange = cq.Workplane("XY").workplane(offset=z0 + bh - 6.8).center(GRIP_GEAR_X, cy).rect(bw, SG90["flange_l"]).extrude(2.2)
    shaft = cq.Workplane("XY").workplane(offset=z0 + bh).center(GRIP_GEAR_X, GRIP_GEAR_Y).circle(2.4).extrude(3.6)
    return body.union(flange).union(shaft)


def _bearing_608_dummy() -> cq.Workplane:
    return cq.Workplane("XY").circle(BEARING_608["od"] / 2.0).circle(BEARING_608["id"] / 2.0).extrude(BEARING_608["w"])


def build_cad_v3(pose_deg=None, explode: float = 0.0):
    """
    Construye el ensamblaje CAD v3 (DFM / Ensamble Real — Revisión A + B + C).
    Todas las dimensiones DH permanecen idénticas (`d1=82, a2=82, a3=70, a4=53 mm`).
    """
    if pose_deg is None:
        pose_deg = HERO_POSE_DEG

    q1 = float(pose_deg["q1"])
    q2 = float(pose_deg["q2"])
    q3 = float(pose_deg["q3"])
    q4 = float(pose_deg["q4"])
    grip_open = float(pose_deg.get("gripper_open_mm", 16.0))

    black_named = {}
    white_named = {}
    servos = []
    elec_pcb = []
    steel = []

    base_r = BASE_DIA / 2.0      # 47.0 mm
    wall = 3.2
    cav_r = base_r - wall        # 43.8 mm
    z_cover = 3.6                # Espesor reforzado para avellanados M3 + huecos gomitas
    brg_w = BEARING_608["w"]     # 7.0 mm
    brg_seat_d = BEARING_608["od"] + BEARING_FIT  # 22.14 mm
    shaft_r = (BEARING_608["id"] - BEARING_FIT) / 2.0  # 3.93 mm

    # ==================================================================
    # 1. BASE FIJA HUECA [REVISIÓN C] — OREJAS MG90S J1 + CLIPS AR5515
    # ==================================================================
    base_shell = (
        cq.Workplane("XY")
        .circle(base_r)
        .extrude(BASE_LOWER_H)
        .edges(">Z or <Z")
        .chamfer(1.4)
    )
    base_shell = base_shell.cut(
        cq.Workplane("XY").workplane(offset=-0.5).circle(cav_r).extrude(BASE_LOWER_H - brg_w + 0.5)
    )
    # Asiento de precisión 608ZZ central (Ø 22.14 × 7.0 mm) + paso inferior Ø 15.5 mm (hombro de retención!)
    base_shell = base_shell.cut(
        cq.Workplane("XY").workplane(offset=BASE_LOWER_H - brg_w).circle(brg_seat_d / 2.0).extrude(brg_w + 1.0)
    )
    base_shell = base_shell.cut(
        cq.Workplane("XY").workplane(offset=BASE_LOWER_H - brg_w - 3.0).circle(7.8).extrude(6.0)
    )
    # Ranura curva dedicada para paso de los 4 cables de servo (lado -X)
    cable_slot = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - brg_w - 2.0)
        .center(-18.5, 0.0)
        .slot2D(22.0, 9.0, angle=90.0)
        .extrude(brg_w + 4.0)
    )
    base_shell = base_shell.cut(cable_slot)

    # 4 jefes internos con barrenos exactos para insertos UNIT `AR2811` (Ø 4.1 × 3.8 mm)
    for k in range(4):
        ang = math.radians(45.0 + k * 90.0)
        bx, by = (cav_r - 3.8) * math.cos(ang), (cav_r - 3.8) * math.sin(ang)
        boss = cq.Workplane("XY").workplane(offset=z_cover).center(bx, by).circle(4.6).extrude(10.0)
        hole = cq.Workplane("XY").workplane(offset=z_cover - 0.5).center(bx, by).circle(INSERT_M3_DIA / 2.0).extrude(INSERT_M3_DEPTH + 1.0)
        base_shell = base_shell.union(boss).cut(hole)

    # Bahía plana trasera en -X para XIAO, AR5515 y KCD11-2P
    rear_flat = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(0.0, 17.5).rect(50.0, 26.0).extrude(6.5)
    cut_xiao_usbc = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(-14.5, 10.8).slot2D(XIAO_ESP32["usbc_w"] + 1.6, XIAO_ESP32["usbc_h"] + 1.4).extrude(15.0)
    cut_pd_usbc = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(1.5, 21.0).slot2D(USBC_PD_AR5515["usbc_w"] + 1.6, USBC_PD_AR5515["usbc_h"] + 1.4).extrude(15.0)
    cut_kcd11 = cq.Workplane("YZ").workplane(offset=-base_r - 3.0).center(16.5, 21.5).rect(SWITCH_KCD11["cut_w"], SWITCH_KCD11["cut_h"]).extrude(15.0)

    # Repisa elevada AR5515 con tope trasero de retención (evita que el PCB se empuje al enchufar el cable USB-C!)
    pd_shelf = (
        cq.Workplane("XY")
        .workplane(offset=15.0)
        .center(-28.5, 1.5)
        .rect(USBC_PD_AR5515["pcb_l"] + 3.6, USBC_PD_AR5515["pcb_w"] + 4.4)
        .extrude(3.8)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=16.4)
            .center(-29.2, 1.5)
            .rect(USBC_PD_AR5515["pcb_l"] + 0.6, USBC_PD_AR5515["pcb_w"] + 0.5)
            .extrude(4.0)
        )
    )

    # Soporte interno MG90S J1 (en X = +22 mm) con barrenos piloto M2 reales (`hole_pitch = 27.5 mm`)
    j1_x = 22.0
    j1_cx = j1_x + 5.4
    j1_holder = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - brg_w - 11.0)
        .center(j1_cx, 0.0)
        .rect(MG90S["flange_l"] + 4.0, MG90S["body_w"] + 6.4)
        .extrude(11.0)
    )
    j1_pocket = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - brg_w - 12.0)
        .center(j1_cx, 0.0)
        .rect(MG90S["body_l"] + CLEARANCE_FIT * 2, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(13.0)
    )
    j1_screw_l = cq.Workplane("XY").workplane(offset=BASE_LOWER_H - brg_w - 12.0).center(j1_cx - MG90S["hole_pitch"] / 2.0, 0.0).circle(0.95).extrude(10.0)
    j1_screw_r = cq.Workplane("XY").workplane(offset=BASE_LOWER_H - brg_w - 12.0).center(j1_cx + MG90S["hole_pitch"] / 2.0, 0.0).circle(0.95).extrude(10.0)

    base_shell = base_shell.union(pd_shelf).union(j1_holder).cut(j1_pocket).cut(j1_screw_l).cut(j1_screw_r)
    base_shell = base_shell.intersect(cq.Workplane("XY").circle(base_r - 0.05).extrude(BASE_LOWER_H))
    base_shell = base_shell.cut(rear_flat).cut(cut_xiao_usbc).cut(cut_pd_usbc).cut(cut_kcd11)
    black_named["01_base_fija_hueca"] = base_shell

    # Hardware base + Piñón 22T con bolsillo real de horn MG90S
    z_brg_exp = 22.0 * explode
    steel.append(_bearing_608_dummy().translate((0.0, 0.0, BASE_LOWER_H - brg_w + z_brg_exp)))
    servos.append(_mg90s_dummy_vertical().translate((j1_x, 0.0, BASE_LOWER_H - brg_w - MG90S["body_h"] - 4.5)))

    j1_pinion = _spur_gear(22, 1.0, 5.4, 1.35)
    j1_pinion = j1_pinion.cut(_horn_recess_xy(depth=2.0, arm_len=8.5, z0=-0.1))
    j1_pinion = j1_pinion.translate((j1_x, 0.0, BASE_LOWER_H - brg_w - 6.3))
    black_named["02_pinon_base_22t"] = j1_pinion

    # Dummies electrónicos traseros
    pd_pcb = cq.Workplane("XY").workplane(offset=18.0).center(-28.5, 1.5).rect(USBC_PD_AR5515["pcb_l"], USBC_PD_AR5515["pcb_w"]).extrude(1.6)
    pd_usbc = cq.Workplane("XY").workplane(offset=19.6).center(-39.5, 1.5).rect(7.5, 9.0).extrude(3.2)
    pd_term = cq.Workplane("XY").workplane(offset=19.6).center(-18.5, 1.5).rect(7.5, 9.5).extrude(8.5)
    kcd_body = cq.Workplane("YZ").workplane(offset=-base_r + 3.5).center(16.5, 21.5).rect(SWITCH_KCD11["cut_w"] - 0.4, SWITCH_KCD11["cut_h"] - 0.4).extrude(SWITCH_KCD11["depth"])
    kcd_bezel = cq.Workplane("YZ").workplane(offset=-base_r + 2.2).center(16.5, 21.5).rect(SWITCH_KCD11["bezel_w"], SWITCH_KCD11["bezel_h"]).extrude(2.2)
    elec_pcb.extend([pd_pcb, pd_term])
    steel.extend([pd_usbc, kcd_body, kcd_bezel])

    # ==================================================================
    # 2. TAPA INFERIOR [REVISIÓN C] — POSTES BARRENADOS + RETENEDORES + GOMITAS
    # ==================================================================
    z_bot_exp = -42.0 * explode
    bot_cover = cq.Workplane("XY").circle(cav_r - CLEARANCE_FIT).extrude(z_cover)

    # 4 postes reforzados para PCA9685 con barrenos piloto M3 (`Ø 2.6 mm`)!
    pca_cx, pca_cy = -6.0, 0.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            px = pca_cx + sx * (PCA9685["hole_dy"] / 2.0)
            py = pca_cy + sy * (PCA9685["hole_dx"] / 2.0)
            post = cq.Workplane("XY").workplane(offset=z_cover).center(px, py).circle(3.2).extrude(4.5)
            post_h = cq.Workplane("XY").workplane(offset=z_cover - 0.5).center(px, py).circle(1.30).extrude(5.8)
            bot_cover = bot_cover.union(post).cut(post_h)

    # Cuna XIAO ESP32-S3 con tope posterior (evita deslizamiento al enchufar USB-C!)
    xiao_cx, xiao_cy = -29.5, -14.5
    xiao_cradle = (
        cq.Workplane("XY")
        .workplane(offset=z_cover)
        .center(xiao_cx, xiao_cy)
        .rect(XIAO_ESP32["pcb_l"] + 3.4, XIAO_ESP32["pcb_w"] + 3.4)
        .extrude(5.5)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=z_cover + 2.0)
            .center(xiao_cx - 0.5, xiao_cy)
            .rect(XIAO_ESP32["pcb_l"] + 1.2, XIAO_ESP32["pcb_w"] + 0.45)
            .extrude(4.5)
        )
    )
    bot_cover = bot_cover.union(xiao_cradle)

    # 4 barrenos M3 con avellanado inferior (`Ø 6.0 × 2.0 mm`) + 4 huecos gomitas antideslizantes (`Ø 10.5 × 1.2 mm`)
    for k in range(4):
        ang = math.radians(45.0 + k * 90.0)
        bx, by = (cav_r - 3.8) * math.cos(ang), (cav_r - 3.8) * math.sin(ang)
        bot_cover = bot_cover.cut(cq.Workplane("XY").workplane(offset=-0.5).center(bx, by).circle(1.7).extrude(z_cover + 1.0))
        bot_cover = bot_cover.cut(cq.Workplane("XY").workplane(offset=-0.1).center(bx, by).circle(3.1).extrude(2.1))
        ang_f = math.radians(k * 90.0)
        fx, fy = 31.0 * math.cos(ang_f), 31.0 * math.sin(ang_f)
        bot_cover = bot_cover.cut(cq.Workplane("XY").workplane(offset=-0.1).center(fx, fy).circle(5.25).extrude(1.3))

    bot_cover = bot_cover.translate((0, 0, z_bot_exp))
    black_named["03_tapa_inferior_electronica"] = bot_cover

    pca_pcb = cq.Workplane("XY").workplane(offset=z_cover + 4.5 + z_bot_exp).center(pca_cx, pca_cy).rect(PCA9685["pcb_w"], PCA9685["pcb_l"]).extrude(1.6)
    pca_headers = cq.Workplane("XY").workplane(offset=z_cover + 6.1 + z_bot_exp).center(pca_cx + 6.2, pca_cy).rect(8.5, 50.0).extrude(8.5)
    xiao_pcb = cq.Workplane("XY").workplane(offset=z_cover + 5.6 + z_bot_exp).center(xiao_cx, xiao_cy).rect(XIAO_ESP32["pcb_l"], XIAO_ESP32["pcb_w"]).extrude(1.6)
    xiao_usbc = cq.Workplane("XY").workplane(offset=z_cover + 7.2 + z_bot_exp).center(xiao_cx - XIAO_ESP32["pcb_l"] / 2.0 + 3.5, xiao_cy).rect(7.5, 9.0).extrude(3.2)
    cap_1000 = cq.Workplane("XY").workplane(offset=z_cover + 1.0 + z_bot_exp).center(12.0, 26.0).circle(CAP_1000UF["dia"] / 2.0).extrude(CAP_1000UF["height"])
    elec_pcb.extend([pca_pcb, xiao_pcb, cap_1000])
    steel.extend([pca_headers, xiao_usbc])

    # ==================================================================
    # 3. ARO BLANCO BASE (SEPARADO — 0% PURGA AMS)
    # ==================================================================
    z_ring_exp = 34.0 * explode
    base_ring = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H + z_ring_exp)
        .circle(base_r + 0.15)
        .circle(base_r - 3.2)
        .extrude(BASE_RING_H)
        .edges()
        .chamfer(0.3)
    )
    white_named["w01_aro_base_blanco"] = base_ring

    # ==================================================================
    # 4. TORRETA J1 [REVISIÓN A + C] — EJE CON CORTE EN D + ACCESO +Y MG90S J2
    # ==================================================================
    z_tur_exp = 52.0 * explode
    tur_z0 = BASE_LOWER_H + BASE_RING_H  # 47.0 mm

    crown = (
        cq.Workplane("XY")
        .workplane(offset=tur_z0)
        .circle(base_r)
        .workplane(offset=BASE_CROWN_H)
        .circle(base_r - 8.5)
        .loft(ruled=True)
    )
    # Eje Ø 7.86 mm con CORTE EN D (1.1 mm plano en la zona inferior Z = 30.8..36.6) para engrane 22T antideslizamiento!
    spigot_z0 = BASE_LOWER_H - brg_w - 6.0  # 31.0 mm
    spigot = cq.Workplane("XY").workplane(offset=spigot_z0).circle(shaft_r).extrude(brg_w + BASE_RING_H + 10.5)
    d_flat_cut = cq.Workplane("XY").workplane(offset=spigot_z0 - 0.5).center(shaft_r + 0.9, 0.0).rect(4.0, 12.0).extrude(6.2)
    spigot_m3 = cq.Workplane("XY").workplane(offset=spigot_z0 - 0.5).circle(1.45).extrude(11.0)
    spigot = spigot.cut(d_flat_cut)

    # Engrane 22T conducido SEPARADO con barreno en D exacto (+0.2 mm holgura)
    turret_gear = _spur_gear(22, 1.0, 5.4, 0.0)
    d_bore = (
        cq.Workplane("XY")
        .workplane(offset=-0.5)
        .circle(shaft_r + 0.14)
        .extrude(6.4)
        .cut(cq.Workplane("XY").workplane(offset=-1.0).center(shaft_r + 1.05, 0.0).rect(4.0, 12.0).extrude(7.4))
    )
    turret_gear = turret_gear.cut(d_bore).translate((0.0, 0.0, spigot_z0))

    # Tambor J2 + columnas con acceso abierto por +Y para insertar MG90S J2 y escalón de orejas!
    j2_drum = (
        cq.Workplane("XZ")
        .center(0.0, D1_BASE_TO_SHOULDER)
        .circle(J2_DRUM_DIA / 2.0)
        .extrude(J2_DRUM_W / 2.0, both=True)
        .edges()
        .chamfer(1.4)
    )
    col_r = (
        cq.Workplane("XY")
        .workplane(offset=tur_z0 + BASE_CROWN_H - 3.0)
        .center(0.0, 6.4)
        .rect(34.0, 30.8)
        .extrude(D1_BASE_TO_SHOULDER - (tur_z0 + BASE_CROWN_H) + 3.0)
        .edges("|Z")
        .fillet(4.0)
    )
    col_l = (
        cq.Workplane("XY")
        .workplane(offset=tur_z0 + BASE_CROWN_H - 3.0)
        .center(0.0, -16.6)
        .rect(34.0, 9.0)
        .extrude(D1_BASE_TO_SHOULDER - (tur_z0 + BASE_CROWN_H) + 3.0)
        .edges("|Z")
        .fillet(3.0)
    )
    turret_solid = crown.union(spigot).union(col_r).union(col_l).union(j2_drum).cut(spigot_m3)

    # Ranura central J2 (`5.6 mm` de ancho: Y = -12.8 .. -7.2 mm) para encaje holgado del disco de 5.0 mm de L2
    j2_hub_slot = cq.Workplane("XZ").workplane(offset=7.2).center(0.0, D1_BASE_TO_SHOULDER).circle(J2_DRUM_DIA / 2.0 + 2.0).extrude(5.6)

    # [REVISIÓN A] Acceso abierto desde +Y para meter el MG90S J2 con sus orejas (`32.5 mm`) + 2 pilotos M2!
    j2_body_cut = (
        cq.Workplane("XZ")
        .workplane(offset=7.4)  # Y = -7.4 mm hasta más allá de +22 mm (abierto en +Y!)
        .center(0.0, D1_BASE_TO_SHOULDER - 5.4)
        .rect(MG90S["body_w"] + CLEARANCE_FIT * 2, MG90S["body_l"] + CLEARANCE_FIT * 2)
        .extrude(-(J2_DRUM_W / 2.0 + 10.0))
    )
    j2_flange_cut = (
        cq.Workplane("XZ")
        .workplane(offset=-1.0)  # Escalón de orejas en Y = +1.0 mm, abierto hasta +23 mm
        .center(0.0, D1_BASE_TO_SHOULDER - 5.4)
        .rect(MG90S["body_w"] + CLEARANCE_FIT * 2, MG90S["flange_l"] + 0.6)
        .extrude(-(J2_DRUM_W / 2.0 + 3.0))
    )
    j2_ear_holes = (
        cq.Workplane("XZ")
        .workplane(offset=-1.5)
        .center(0.0, D1_BASE_TO_SHOULDER - 5.4 + MG90S["hole_pitch"] / 2.0)
        .circle(0.85)
        .extrude(7.0)
        .union(
            cq.Workplane("XZ")
            .workplane(offset=-1.5)
            .center(0.0, D1_BASE_TO_SHOULDER - 5.4 - MG90S["hole_pitch"] / 2.0)
            .circle(0.85)
            .extrude(7.0)
        )
    )
    # Asiento 608ZZ abierto desde -Y (`Y = -22 .. -12.8`) con hombro interno Ø 15.5 mm
    j2_brg_seat = cq.Workplane("XZ").workplane(offset=12.8).center(0.0, D1_BASE_TO_SHOULDER).circle(brg_seat_d / 2.0).extrude(11.0)
    j2_brg_lip = cq.Workplane("XZ").workplane(offset=11.0).center(0.0, D1_BASE_TO_SHOULDER).circle(7.6).extrude(3.0)
    # Paso de cables en la corona alineado con la ranura curva de la base
    tur_cable_hole = cq.Workplane("XY").workplane(offset=tur_z0 - 1.0).center(-18.5, 0.0).circle(6.0).extrude(BASE_CROWN_H + 5.0)
    # Rebajes circulares de 1.8 mm en ambas caras ±Y + 2 barrenos piloto M3 (`45° / 225°`) para atornillar tapas Stealth
    j2_cap_rec_l = cq.Workplane("XZ").workplane(offset=J2_DRUM_W / 2.0 - 1.5).center(0.0, D1_BASE_TO_SHOULDER).circle(J2_CAP_DIA / 2.0 + 0.25).extrude(3.0)
    j2_cap_rec_r = cq.Workplane("XZ").workplane(offset=-(J2_DRUM_W / 2.0 - 1.5)).center(0.0, D1_BASE_TO_SHOULDER).circle(J2_CAP_DIA / 2.0 + 0.25).extrude(-3.0)

    turret_solid = (
        turret_solid
        .cut(j2_hub_slot)
        .cut(j2_body_cut)
        .cut(j2_flange_cut)
        .cut(j2_ear_holes)
        .cut(j2_brg_seat)
        .cut(j2_brg_lip)
        .cut(tur_cable_hole)
        .cut(j2_cap_rec_l)
        .cut(j2_cap_rec_r)
    )
    for ang_d in (45.0, 225.0):
        ang = math.radians(ang_d)
        bx = (J2_CAP_DIA * 0.31) * math.cos(ang)
        bz = D1_BASE_TO_SHOULDER + (J2_CAP_DIA * 0.31) * math.sin(ang)
        turret_solid = turret_solid.cut(cq.Workplane("XZ").workplane(offset=J2_DRUM_W / 2.0 - 6.5).center(bx, bz).circle(1.30).extrude(7.0))
        turret_solid = turret_solid.cut(cq.Workplane("XZ").workplane(offset=-(J2_DRUM_W / 2.0 - 6.5)).center(bx, bz).circle(1.30).extrude(-7.0))

    def apply_q1(shape):
        return shape.rotate((0, 0, 0), (0, 0, 1), q1) if abs(q1) > 1e-6 else shape

    black_named["04_torreta_j1_hombro"] = apply_q1(turret_solid.translate((0, 0, z_tur_exp)))
    black_named["04b_engrane_torreta_22t"] = apply_q1(turret_gear.translate((0, 0, -14.0 * explode)))

    # Hardware J2 + Buje centrador 608ZZ (se inserta desde -Y!)
    j2_servo = _mg90s_dummy_joint(tail_dir_xz=(0.0, -1.0), y_shaft_end=-7.5).translate((0.0, 0.0, D1_BASE_TO_SHOULDER + z_tur_exp))
    j2_brg = _bearing_608_dummy().rotate((0, 0, 0), (1, 0, 0), 90.0).translate((0.0, -12.8, D1_BASE_TO_SHOULDER + z_tur_exp))
    j2_bush = _bushing_608_m3().rotate((0, 0, 0), (1, 0, 0), -90.0).translate((0.0, -21.2 - 14.0 * explode, D1_BASE_TO_SHOULDER + z_tur_exp))
    servos.append(apply_q1(j2_servo))
    steel.append(apply_q1(j2_brg))
    black_named["11_buje_608zz_j2"] = apply_q1(j2_bush)

    def add_stealth_caps(tag: str, center_xz, drum_w, cap_d, z_off=0.0, exp_y=0.0):
        """Tapas Stealth con ceja centradora interior y 2 barrenos M3 avellanados reales + aros blancos."""
        cx, cz = center_xz[0], center_xz[1] + z_off
        for side in (-1, 1):
            suf = "izq" if side == -1 else "der"
            y_face = side * (drum_w / 2.0 + exp_y)
            # Aro blanco incrustado
            white_ring = (
                cq.Workplane("XZ")
                .workplane(offset=-(y_face - side * 1.4))
                .center(cx, cz)
                .circle(cap_d / 2.0)
                .circle((cap_d - 2.8) / 2.0)
                .extrude(-side * 1.8)
            )
            # Tapa negra con disco exterior + ceja centradora de 1.2 mm + 2 barrenos avellanados M3
            cap_ext = (
                cq.Workplane("XZ")
                .workplane(offset=-(y_face - side * 1.4))
                .center(cx, cz)
                .circle((cap_d - 3.1) / 2.0)
                .extrude(-side * 1.8)
                .edges()
                .chamfer(0.35)
            )
            cap_lip = (
                cq.Workplane("XZ")
                .workplane(offset=-(y_face - side * 2.5))
                .center(cx, cz)
                .circle((cap_d - 6.0) / 2.0)
                .circle((cap_d - 9.0) / 2.0)
                .extrude(-side * 1.2)
            )
            inner_cap = cap_ext.union(cap_lip)
            bcd = cap_d * 0.62
            for ang_d in (45.0, 225.0):
                ang = math.radians(ang_d)
                bx = cx + (bcd / 2.0) * math.cos(ang)
                bz = cz + (bcd / 2.0) * math.sin(ang)
                h_m3 = cq.Workplane("XZ").workplane(offset=-(y_face - side * 3.0)).center(bx, bz).circle(1.65).extrude(-side * 5.0)
                inner_cap = inner_cap.cut(h_m3)
                bolt = cq.Workplane("XZ").workplane(offset=-(y_face + side * 0.3)).center(bx, bz).circle(2.4).extrude(-side * 1.0)
                steel.append(apply_q1(bolt))
            white_named[f"w_aro_{tag}_{suf}"] = apply_q1(white_ring)
            black_named[f"tapa_{tag}_{suf}"] = apply_q1(inner_cap)

    p2 = (0.0, D1_BASE_TO_SHOULDER)
    a2_rad = math.radians(q2)
    p3 = (p2[0] + A2_LOWER_ARM * math.cos(a2_rad), p2[1] + A2_LOWER_ARM * math.sin(a2_rad))
    a3_rad = math.radians(q2 + q3)
    p4 = (p3[0] + A3_FOREARM * math.cos(a3_rad), p3[1] + A3_FOREARM * math.sin(a3_rad))

    add_stealth_caps("j2", p2, J2_DRUM_W, J2_CAP_DIA, z_off=z_tur_exp, exp_y=20.0 * explode)

    # ==================================================================
    # 5. ESLABÓN L2 [REVISIÓN A] — INSERTO AR2811 + BOLSILLO HORN + DUCTO CONTINUO + ACCESO MG90S J3
    # ==================================================================
    exp_l2 = (22.0 * math.cos(a2_rad) * explode, 22.0 * math.sin(a2_rad) * explode + z_tur_exp)
    p2_e = (p2[0] + exp_l2[0], p2[1] + exp_l2[1])
    p3_e = (p3[0] + exp_l2[0], p3[1] + exp_l2[1])

    # Disco motriz de 5.0 mm (Y = -12.5 .. -7.5) — entra holgado en la ranura de 5.6 mm sin muñón saliente!
    l2_hub = cq.Workplane("XZ").workplane(offset=12.5).circle(16.5).extrude(-5.0)
    # Barreno inserto térmico AR2811 desde cara -Y (Y = -12.5 .. -9.2) + bolsillo horn MG90S desde cara +Y (Y = -7.5 .. -9.4)
    l2_ins_cut = cq.Workplane("XZ").workplane(offset=12.6).circle(INSERT_M3_DIA / 2.0).extrude(-3.3)
    l2_horn_cut = _horn_recess_xz(y_face=-7.4, depth=2.0, arm_len=14.5, dir_sign=-1.0)

    l2_beam = _octagonal_beam_continuous_duct(A2_LOWER_ARM, 25.0, 22.0, 24.0, 22.0, chamfer=3.8, duct_w=10.0, duct_h=8.0)
    l2_j2_clear = cq.Workplane("XZ").workplane(offset=7.5).circle(19.5).extrude(-32.0)
    l2_beam = l2_beam.cut(l2_j2_clear)

    j3_drum = cq.Workplane("XZ").center(A2_LOWER_ARM, 0.0).circle(J3_DRUM_DIA / 2.0).extrude(J3_DRUM_W / 2.0, both=True).edges().chamfer(1.2)
    j3_slot = cq.Workplane("XZ").workplane(offset=7.2).center(A2_LOWER_ARM, 0.0).circle(J3_DRUM_DIA / 2.0 + 2.0).extrude(5.6)
    j3_body_cut = (
        cq.Workplane("XZ")
        .workplane(offset=7.4)
        .center(A2_LOWER_ARM - 5.4, 0.0)
        .rect(MG90S["body_l"] + CLEARANCE_FIT * 2, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-(J3_DRUM_W / 2.0 + 10.0))
    )
    j3_flange_cut = (
        cq.Workplane("XZ")
        .workplane(offset=-1.0)
        .center(A2_LOWER_ARM - 5.4, 0.0)
        .rect(MG90S["flange_l"] + 0.6, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-(J3_DRUM_W / 2.0 + 3.0))
    )
    j3_ear_holes = (
        cq.Workplane("XZ").workplane(offset=-1.5).center(A2_LOWER_ARM - 5.4 + MG90S["hole_pitch"] / 2.0, 0.0).circle(0.85).extrude(7.0)
        .union(cq.Workplane("XZ").workplane(offset=-1.5).center(A2_LOWER_ARM - 5.4 - MG90S["hole_pitch"] / 2.0, 0.0).circle(0.85).extrude(7.0))
    )
    j3_brg_cut = cq.Workplane("XZ").workplane(offset=12.8).center(A2_LOWER_ARM, 0.0).circle(brg_seat_d / 2.0).extrude(11.0)
    j3_brg_lip = cq.Workplane("XZ").workplane(offset=11.0).center(A2_LOWER_ARM, 0.0).circle(7.6).extrude(3.0)
    j3_cap_l = cq.Workplane("XZ").workplane(offset=J3_DRUM_W / 2.0 - 1.5).center(A2_LOWER_ARM, 0.0).circle(J3_CAP_DIA / 2.0 + 0.25).extrude(3.0)
    j3_cap_r = cq.Workplane("XZ").workplane(offset=-(J3_DRUM_W / 2.0 - 1.5)).center(A2_LOWER_ARM, 0.0).circle(J3_CAP_DIA / 2.0 + 0.25).extrude(-3.0)

    l2_part = (
        l2_hub.union(l2_beam).union(j3_drum)
        .cut(l2_ins_cut).cut(l2_horn_cut)
        .cut(j3_slot).cut(j3_body_cut).cut(j3_flange_cut).cut(j3_ear_holes)
        .cut(j3_brg_cut).cut(j3_brg_lip).cut(j3_cap_l).cut(j3_cap_r)
    )
    for ang_d in (45.0, 225.0):
        ang = math.radians(ang_d)
        bx = A2_LOWER_ARM + (J3_CAP_DIA * 0.31) * math.cos(ang)
        bz = (J3_CAP_DIA * 0.31) * math.sin(ang)
        l2_part = l2_part.cut(cq.Workplane("XZ").workplane(offset=J3_DRUM_W / 2.0 - 6.5).center(bx, bz).circle(1.30).extrude(7.0))
        l2_part = l2_part.cut(cq.Workplane("XZ").workplane(offset=-(J3_DRUM_W / 2.0 - 6.5)).center(bx, bz).circle(1.30).extrude(-7.0))
    black_named["05_eslabon_l2_codo"] = apply_q1(_place_xz(l2_part, p2_e, q2))

    j3_tail = (-math.cos(a2_rad), -math.sin(a2_rad))
    j3_servo = _mg90s_dummy_joint(tail_dir_xz=j3_tail, y_shaft_end=-7.5).translate((p3_e[0], 0.0, p3_e[1]))
    j3_brg = _bearing_608_dummy().rotate((0, 0, 0), (1, 0, 0), 90.0).translate((p3_e[0], -12.8, p3_e[1]))
    j3_bush = _bushing_608_m3().rotate((0, 0, 0), (1, 0, 0), -90.0).translate((p3_e[0], -21.0 - 14.0 * explode, p3_e[1]))
    servos.append(apply_q1(j3_servo))
    steel.append(apply_q1(j3_brg))
    black_named["11_buje_608zz_j3"] = apply_q1(j3_bush)
    add_stealth_caps("j3", p3_e, J3_DRUM_W, J3_CAP_DIA, z_off=0.0, exp_y=20.0 * explode)

    # ==================================================================
    # 6. ANTEBRAZO L3 [REVISIÓN A] — INSERTO AR2811 + HORN + DUCTO + ACCESO MG90S J4
    # ==================================================================
    exp_l3 = (exp_l2[0] + 26.0 * math.cos(a3_rad) * explode, exp_l2[1] + 26.0 * math.sin(a3_rad) * explode)
    p3_f = (p3[0] + exp_l3[0], p3[1] + exp_l3[1])
    p4_f = (p4[0] + exp_l3[0], p4[1] + exp_l3[1])

    l3_hub = cq.Workplane("XZ").workplane(offset=12.5).circle(15.0).extrude(-5.0)
    l3_ins_cut = cq.Workplane("XZ").workplane(offset=12.6).circle(INSERT_M3_DIA / 2.0).extrude(-3.3)
    l3_horn_cut = _horn_recess_xz(y_face=-7.4, depth=2.0, arm_len=13.5, dir_sign=-1.0)

    l3_beam = _octagonal_beam_continuous_duct(A3_FOREARM, 21.0, 18.5, 20.5, 18.5, chamfer=3.2, duct_w=9.5, duct_h=7.5)
    l3_j3_clear = cq.Workplane("XZ").workplane(offset=7.5).circle(17.5).extrude(-30.0)
    l3_beam = l3_beam.cut(l3_j3_clear)

    j4_drum = cq.Workplane("XZ").center(A3_FOREARM, 0.0).circle(J4_DRUM_DIA / 2.0).extrude(J4_DRUM_W / 2.0, both=True).edges().chamfer(1.0)
    j4_slot = cq.Workplane("XZ").workplane(offset=7.2).center(A3_FOREARM, 0.0).circle(J4_DRUM_DIA / 2.0 + 2.0).extrude(5.6)
    j4_body_cut = (
        cq.Workplane("XZ")
        .workplane(offset=7.4)
        .center(A3_FOREARM - 5.4, 0.0)
        .rect(MG90S["body_l"] + CLEARANCE_FIT * 2, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-(J4_DRUM_W / 2.0 + 10.0))
    )
    j4_flange_cut = (
        cq.Workplane("XZ")
        .workplane(offset=-1.0)
        .center(A3_FOREARM - 5.4, 0.0)
        .rect(MG90S["flange_l"] + 0.6, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-(J4_DRUM_W / 2.0 + 3.0))
    )
    j4_ear_holes = (
        cq.Workplane("XZ").workplane(offset=-1.5).center(A3_FOREARM - 5.4 + MG90S["hole_pitch"] / 2.0, 0.0).circle(0.85).extrude(7.0)
        .union(cq.Workplane("XZ").workplane(offset=-1.5).center(A3_FOREARM - 5.4 - MG90S["hole_pitch"] / 2.0, 0.0).circle(0.85).extrude(7.0))
    )
    j4_brg_cut = cq.Workplane("XZ").workplane(offset=12.8).center(A3_FOREARM, 0.0).circle(brg_seat_d / 2.0).extrude(11.0)
    j4_brg_lip = cq.Workplane("XZ").workplane(offset=11.0).center(A3_FOREARM, 0.0).circle(7.6).extrude(3.0)
    j4_cap_l = cq.Workplane("XZ").workplane(offset=J4_DRUM_W / 2.0 - 1.5).center(A3_FOREARM, 0.0).circle(J4_CAP_DIA / 2.0 + 0.25).extrude(3.0)
    j4_cap_r = cq.Workplane("XZ").workplane(offset=-(J4_DRUM_W / 2.0 - 1.5)).center(A3_FOREARM, 0.0).circle(J4_CAP_DIA / 2.0 + 0.25).extrude(-3.0)

    l3_part = (
        l3_hub.union(l3_beam).union(j4_drum)
        .cut(l3_ins_cut).cut(l3_horn_cut)
        .cut(j4_slot).cut(j4_body_cut).cut(j4_flange_cut).cut(j4_ear_holes)
        .cut(j4_brg_cut).cut(j4_brg_lip).cut(j4_cap_l).cut(j4_cap_r)
    )
    for ang_d in (45.0, 225.0):
        ang = math.radians(ang_d)
        bx = A3_FOREARM + (J4_CAP_DIA * 0.31) * math.cos(ang)
        bz = (J4_CAP_DIA * 0.31) * math.sin(ang)
        l3_part = l3_part.cut(cq.Workplane("XZ").workplane(offset=J4_DRUM_W / 2.0 - 6.0).center(bx, bz).circle(1.30).extrude(6.5))
        l3_part = l3_part.cut(cq.Workplane("XZ").workplane(offset=-(J4_DRUM_W / 2.0 - 6.0)).center(bx, bz).circle(1.30).extrude(-6.5))
    black_named["06_antebrazo_l3_muneca"] = apply_q1(_place_xz(l3_part, p3_f, q2 + q3))

    j4_tail = (-math.cos(a3_rad), -math.sin(a3_rad))
    j4_servo = _mg90s_dummy_joint(tail_dir_xz=j4_tail, y_shaft_end=-7.5).translate((p4_f[0], 0.0, p4_f[1]))
    j4_brg = _bearing_608_dummy().rotate((0, 0, 0), (1, 0, 0), 90.0).translate((p4_f[0], -12.8, p4_f[1]))
    j4_bush = _bushing_608_m3().rotate((0, 0, 0), (1, 0, 0), -90.0).translate((p4_f[0], -20.5 - 14.0 * explode, p4_f[1]))
    servos.append(apply_q1(j4_servo))
    steel.append(apply_q1(j4_brg))
    black_named["11_buje_608zz_j4"] = apply_q1(j4_bush)
    add_stealth_caps("j4", p4_f, J4_DRUM_W, J4_CAP_DIA, z_off=0.0, exp_y=18.0 * explode)

    # ==================================================================
    # 7. PINZA PARALELA REAL DE 4 BARRAS [REVISIÓN B] — SG90 COAXIAL + BIELAS
    # ==================================================================
    wrist_ang = q2 + q3 + q4
    a4_rad = math.radians(wrist_ang)
    exp_l4 = (exp_l3[0] + 30.0 * math.cos(a4_rad) * explode, exp_l3[1] + 30.0 * math.sin(a4_rad) * explode)
    p4_g = (p4[0] + exp_l4[0], p4[1] + exp_l4[1])

    # Disco de muñeca (5.0 mm, inserto AR2811 en -Y, horn MG90S J4 en +Y)
    w_hub = cq.Workplane("XZ").workplane(offset=12.5).circle(12.2).extrude(-5.0)
    w_ins_cut = cq.Workplane("XZ").workplane(offset=12.6).circle(INSERT_M3_DIA / 2.0).extrude(-3.3)
    w_horn_cut = _horn_recess_xz(y_face=-7.4, depth=1.9, arm_len=11.0, dir_sign=-1.0)
    w_bridge = cq.Workplane("XY").workplane(offset=-5.0).center(9.5, -5.0).rect(15.0, 14.0).extrude(10.0)
    collar = cq.Workplane("YZ").workplane(offset=11.0).circle(12.2).extrude(7.5).edges().chamfer(0.7)
    collar_ring = cq.Workplane("YZ").workplane(offset=14.4).circle(12.6).circle(10.4).extrude(2.2)

    # Palma con pila Z 100% libre de colisiones:
    #   SG90 cuerpo:      Z = -23.0 .. -0.3 (eje coaxial hasta +3.3 dentro del engrane izq!)
    #   palm_deck:        Z = -3.0  .. -0.2 (X = 16..34, bajo engranes)
    #   Engranes-brazo:   Z = +0.4  .. +4.8 (0.6 mm holgura arriba de palm_deck)
    #   Bielas traseras:  Z = +5.4  .. +8.4 (0.6 mm holgura arriba de engranes!)
    #   palm_top_bridge:  Z = +9.0  .. +11.4 (0.6 mm holgura arriba de bielas!)
    sg_cy = GRIP_GEAR_Y - (SG90["body_l"] / 2.0 - 6.0)  # +1.87 mm (coaxial bajo engrane izquierdo!)
    palm_deck = (
        cq.Workplane("XY")
        .workplane(offset=-3.0)
        .center(25.0, 0.0)
        .rect(18.0, 34.0)
        .extrude(2.8)
        .edges("|Z")
        .fillet(2.4)
    )
    # Carenado inferior biselado (Z = -24.2 .. -2.8) que oculta 100% el SG90 transversal + sus orejas (32 mm)!
    chin_shroud = (
        cq.Workplane("XY")
        .workplane(offset=-24.2)
        .center(GRIP_GEAR_X, sg_cy)
        .rect(17.2, 34.8)
        .workplane(offset=21.4)
        .rect(19.2, 36.4)
        .loft(ruled=True)
    )
    # Bolsillo abierto por abajo para deslizar el SG90 hacia arriba + escalón de orejas en Z = -7.1 mm + 2 pilotos M2!
    sg_body_cut = (
        cq.Workplane("XY")
        .workplane(offset=-25.0)
        .center(GRIP_GEAR_X, sg_cy)
        .rect(SG90["body_w"] + 0.5, SG90["body_l"] + 0.5)
        .extrude(24.9)
    )
    sg_flange_cut = (
        cq.Workplane("XY")
        .workplane(offset=-25.0)
        .center(GRIP_GEAR_X, sg_cy)
        .rect(SG90["body_w"] + 0.5, SG90["flange_l"] + 0.6)
        .extrude(18.0)  # Escalón de orejas en Z = -7.0 mm
    )
    sg_ear_h1 = cq.Workplane("XY").workplane(offset=-7.5).center(GRIP_GEAR_X, sg_cy + 13.75).circle(0.85).extrude(7.5)
    sg_ear_h2 = cq.Workplane("XY").workplane(offset=-7.5).center(GRIP_GEAR_X, sg_cy - 13.75).circle(0.85).extrude(7.5)

    # Puente superior sujetando los ejes en doble apoyo (Z = +9.0 .. +11.4), sostenido por poste trasero en X = 15..18.5
    palm_top_bridge = (
        cq.Workplane("XY")
        .workplane(offset=9.0)
        .center(25.0, 0.0)
        .rect(18.5, 22.0)
        .extrude(2.4)
        .edges("|Z")
        .fillet(2.4)
    )
    palm_rear_post = cq.Workplane("XY").workplane(offset=-3.0).center(16.8, 0.0).rect(3.8, 9.6).extrude(12.6)

    palm_full = (
        w_hub.union(w_bridge).union(collar).union(palm_deck).union(chin_shroud).union(palm_top_bridge).union(palm_rear_post)
        .cut(w_ins_cut).cut(w_horn_cut)
        .cut(sg_body_cut).cut(sg_flange_cut).cut(sg_ear_h1).cut(sg_ear_h2)
    )
    # 4 barrenos M3 exactos de los pivotes de tierra del paralelogramo: G_L, G_R, I_L, I_R!
    for px, py, rad in [
        (GRIP_GEAR_X, +GRIP_GEAR_Y, 2.8),   # Paso eje SG90 bajo engrane izq
        (GRIP_GEAR_X, -GRIP_GEAR_Y, 1.55),  # Pivote M3 engrane derecho
        (GRIP_IDLER_X, +GRIP_GEAR_Y, 1.55), # Pivote M3 biela trasera izq
        (GRIP_IDLER_X, -GRIP_GEAR_Y, 1.55), # Pivote M3 biela trasera der
    ]:
        palm_full = palm_full.cut(cq.Workplane("XY").workplane(offset=-4.5).center(px, py).circle(rad).extrude(17.5))

    black_named["07_palma_pinza_sg90"] = apply_q1(_place_xz(palm_full, p4_g, wrist_ang))
    white_named["w02_collar_muneca_blanco"] = apply_q1(_place_xz(collar_ring, p4_g, wrist_ang))

    # SG90 real coaxial bajo el engrane izquierdo (100% oculto dentro del carenado!)
    servos.append(apply_q1(_place_xz(_sg90_dummy_coaxial(), p4_g, wrist_ang)))

    # --- Cinemática exacta del paralelogramo de 4 barras en Pose Héroe (`grip_open`) ---
    th_deg = gripper_angle_deg(grip_open)
    th_rad = math.radians(th_deg)
    arm_dx = GRIP_LINK_L * math.cos(th_rad)
    arm_dy = GRIP_LINK_L * math.sin(th_rad)

    # Engranes-Brazo 14T de UNA SOLA PIEZA en Z = +0.4 .. +4.8 mm (4.4 mm espesor)
    for side_name, side, fname, gear_phase in [
        ("izq", +1, "08_engrane_brazo_izq", 0.0),
        ("der", -1, "09_engrane_brazo_der", 360.0 / 28.0),
    ]:
        gx, gy = GRIP_GEAR_X, side * GRIP_GEAR_Y
        g_base = _spur_gear(14, 1.0, 4.4, 1.65).rotate((0, 0, 0), (0, 0, 1), gear_phase)
        arm_bar = (
            cq.Workplane("XY")
            .center(GRIP_LINK_L / 2.0, 0.0)
            .rect(GRIP_LINK_L, 5.4)
            .extrude(4.4)
            .union(cq.Workplane("XY").center(GRIP_LINK_L, 0.0).circle(3.1).extrude(4.4))
            .cut(cq.Workplane("XY").workplane(offset=-0.5).center(GRIP_LINK_L, 0.0).circle(1.65).extrude(5.4))
            .rotate((0, 0, 0), (0, 0, 1), side * th_deg)
        )
        gear_arm = g_base.union(arm_bar)
        if side == +1:
            gear_arm = gear_arm.cut(_horn_recess_xy(depth=1.9, arm_len=11.0, z0=-0.1).rotate((0, 0, 0), (0, 0, 1), th_deg))
        gear_arm = gear_arm.translate((gx, gy, 0.4 + 4.0 * explode))
        black_named[fname] = apply_q1(_place_xz(gear_arm, p4_g, wrist_ang))

    # Aros blancos sobre el puente superior + 4 pernos M3 de tierra
    for idx_g, sy in enumerate((-GRIP_GEAR_Y, GRIP_GEAR_Y)):
        hr = cq.Workplane("XY").workplane(offset=11.4 + 14.0 * explode).center(GRIP_GEAR_X, sy).circle(3.6).circle(2.1).extrude(0.6)
        pin_g = cq.Workplane("XY").workplane(offset=-2.5).center(GRIP_GEAR_X, sy).circle(1.5).extrude(14.5)
        pin_i = cq.Workplane("XY").workplane(offset=-2.5).center(GRIP_IDLER_X, sy).circle(1.5).extrude(14.5)
        white_named[f"w03_aro_engrane_{idx_g}"] = apply_q1(_place_xz(hr, p4_g, wrist_ang))
        steel.extend([apply_q1(_place_xz(pin_g, p4_g, wrist_ang)), apply_q1(_place_xz(pin_i, p4_g, wrist_ang))])

    # 2× Bielas Traseras de Paralelismo en Z = +5.4 .. +8.4 mm (¡0.6 mm limpias encima de los engranes!)
    for side_name, side in [("izq", +1), ("der", -1)]:
        ix, iy = GRIP_IDLER_X, side * GRIP_GEAR_Y
        biela = (
            cq.Workplane("XY")
            .center(GRIP_LINK_L / 2.0, 0.0)
            .rect(GRIP_LINK_L, 4.6)
            .extrude(3.0)
            .union(cq.Workplane("XY").circle(2.8).extrude(3.0))
            .union(cq.Workplane("XY").center(GRIP_LINK_L, 0.0).circle(2.8).extrude(3.0))
            .cut(cq.Workplane("XY").workplane(offset=-0.5).circle(1.65).extrude(4.0))
            .cut(cq.Workplane("XY").workplane(offset=-0.5).center(GRIP_LINK_L, 0.0).circle(1.65).extrude(4.0))
            .rotate((0, 0, 0), (0, 0, 1), side * th_deg)
            .translate((ix, iy, 5.4 + 10.0 * explode))
        )
        black_named[f"12_biela_pinza_{side_name}"] = apply_q1(_place_xz(biela, p4_g, wrist_ang))

    # 2× Dedos Paralelos con puente de doble pivote M3 en Z = -3.4 .. -0.2 mm (libre de palm_deck) + Almohadillas blancas
    f_front_x = GRIP_GEAR_X + arm_dx
    f_rear_x = GRIP_IDLER_X + arm_dx
    for side_name, side in [("izq", +1), ("der", -1)]:
        fy = side * (GRIP_GEAR_Y + arm_dy)
        inner_y = fy - side * 7.1
        pivot_bar = (
            cq.Workplane("XY")
            .workplane(offset=-3.4)
            .center(0.5 * (f_front_x + f_rear_x), fy)
            .rect(GRIP_PIVOT_SEP + 6.4, 6.2)
            .extrude(3.2)
            .edges("|Z")
            .fillet(2.4)
        )
        x_jaw0 = f_front_x - 3.0
        x_jaw1 = f_front_x + 18.5
        pts_jaw = [
            (x_jaw0, inner_y + side * 1.55),
            (x_jaw1, inner_y + side * 1.55),
            (x_jaw1, inner_y + side * 4.8),
            (x_jaw0 + 4.0, fy + side * 3.1),
            (x_jaw0, fy + side * 3.1),
        ]
        if side < 0:
            pts_jaw = list(reversed(pts_jaw))
        jaw = cq.Workplane("XY").workplane(offset=-3.4).polyline(pts_jaw).close().extrude(12.2).edges("|Z").fillet(0.7)

        finger = pivot_bar.union(jaw)
        for px in (f_rear_x, f_front_x):
            finger = finger.cut(cq.Workplane("XY").workplane(offset=-4.2).center(px, fy).circle(1.65).extrude(14.5))
            pin_f = cq.Workplane("XY").workplane(offset=-3.8).center(px, fy).circle(1.45).extrude(13.0)
            steel.append(apply_q1(_place_xz(pin_f, p4_g, wrist_ang)))

        pts_pad = [
            (x_jaw0 + 4.5, inner_y),
            (x_jaw1 - 0.6, inner_y),
            (x_jaw1 - 0.6, inner_y + side * 1.55),
            (x_jaw0 + 4.5, inner_y + side * 1.55),
        ]
        if side < 0:
            pts_pad = list(reversed(pts_pad))
        pad = cq.Workplane("XY").workplane(offset=-2.0).polyline(pts_pad).close().extrude(9.2)

        black_named[f"10_dedo_pinza_{side_name}"] = apply_q1(_place_xz(finger.translate((0, side * 14.0 * explode, 0)), p4_g, wrist_ang))
        white_named[f"w04_almohadilla_{side_name}"] = apply_q1(_place_xz(pad.translate((0, side * 18.0 * explode, 0)), p4_g, wrist_ang))

    return {
        "black_named": black_named,
        "white_named": white_named,
        "black": list(black_named.values()),
        "white": list(white_named.values()),
        "servos": servos,
        "elec_pcb": elec_pcb,
        "steel": steel,
    }


def export_all_v3():
    here = os.path.dirname(os.path.abspath(__file__))
    exp_dir = os.path.join(here, "exports")
    stl_blk = os.path.join(exp_dir, "stl_negro_mate")
    stl_wht = os.path.join(exp_dir, "stl_blanco_mate")
    stl_hw = os.path.join(exp_dir, "hardware_ref")
    for d in (stl_blk, stl_wht, stl_hw):
        os.makedirs(d, exist_ok=True)
        for old in glob.glob(os.path.join(d, "*.stl")):
            os.remove(old)

    parts = build_cad_v3(explode=0.0)

    servo_names = [
        "hw_mg90s_j1_base",
        "hw_mg90s_j2_hombro",
        "hw_mg90s_j3_codo",
        "hw_mg90s_j4_muneca",
        "hw_sg90_pinza",
    ]
    elec_names = [
        "hw_ar5515_usbc_pd_pcb",
        "hw_ar5515_bornera",
        "hw_pca9685_pcb",
        "hw_xiao_esp32_pcb",
        "hw_capacitor_1000uf",
    ]
    steel_named_map = {
        0: "hw_rodamiento_608zz_base",
        1: "hw_ar5515_puerto_usbc",
        2: "hw_switch_kcd11_cuerpo",
        3: "hw_switch_kcd11_bisel",
        4: "hw_pca9685_pines",
        5: "hw_xiao_puerto_usbc",
        6: "hw_rodamiento_608zz_j2",
        11: "hw_rodamiento_608zz_j3",
        16: "hw_rodamiento_608zz_j4",
    }

    assy = cq.Assembly(name="MiniPro_4DOF_B2_Stealth_v3_DFM")
    for name, s in parts["black_named"].items():
        assy.add(s, name=name, color=cq.Color(0.15, 0.15, 0.16, 1.0))
    for name, s in parts["white_named"].items():
        assy.add(s, name=name, color=cq.Color(0.96, 0.96, 0.95, 1.0))
    for idx, s in enumerate(parts["servos"]):
        nm = servo_names[idx] if idx < len(servo_names) else f"hw_servo_{idx}"
        assy.add(s, name=nm, color=cq.Color(0.16, 0.44, 0.74, 1.0))
        cq.exporters.export(s, os.path.join(stl_hw, f"{nm}.stl"), tolerance=0.05, angularTolerance=0.12)
    for idx, s in enumerate(parts["elec_pcb"]):
        nm = elec_names[idx] if idx < len(elec_names) else f"hw_elec_{idx}"
        assy.add(s, name=nm, color=cq.Color(0.12, 0.56, 0.30, 1.0))
        cq.exporters.export(s, os.path.join(stl_hw, f"{nm}.stl"), tolerance=0.05, angularTolerance=0.12)
    for idx, s in enumerate(parts["steel"]):
        nm = steel_named_map.get(idx, f"hw_tornilleria_{idx:02d}")
        assy.add(s, name=nm, color=cq.Color(0.70, 0.72, 0.75, 1.0))
        if idx in steel_named_map:
            cq.exporters.export(s, os.path.join(stl_hw, f"{nm}.stl"), tolerance=0.05, angularTolerance=0.12)

    step_path = os.path.join(exp_dir, "mini_pro_b2_stealth_v3.step")
    assy.export(step_path)
    print(f"Exported STEP v3 DFM: {step_path}")

    for name, s in parts["black_named"].items():
        cq.exporters.export(s, os.path.join(stl_blk, f"{name}.stl"), tolerance=0.03, angularTolerance=0.08)
    for name, s in parts["white_named"].items():
        cq.exporters.export(s, os.path.join(stl_wht, f"{name}.stl"), tolerance=0.03, angularTolerance=0.08)

    print(f"Exported {len(parts['black_named'])} Negro Mate STLs -> {stl_blk}")
    print(f"Exported {len(parts['white_named'])} Blanco Mate STLs -> {stl_wht}")
    print(f"Exported hardware ref STLs -> {stl_hw}")


if __name__ == "__main__":
    export_all_v3()
