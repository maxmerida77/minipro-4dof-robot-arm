"""
Iteración 2B — CAD Paramétrico Imprimible v2 (100% UNIT Electronics · B2 Stealth)
=================================================================================
Resuelve los 3 hallazgos del corte v1 e integra con medidas reales verificadas TODOS los
componentes del carrito de UNIT Electronics México (`docs/BOM_UNIT_ELECTRONICS.md`):

  - 4× MG90S 180° (`AR1240`, 22.8×12.2×28.5 mm, orientado a lo largo de cada eslabón para
    encapsulado 100% invisible dentro de los tambores; bolsillo apto también para MG92B).
  - 1× SG90 en la pinza paralela, 100% oculto por carenado inferior biselado negro mate.
  - 4× Rodamientos `608ZZ-7` (`AR4602`, 8×22×7 mm): Base J1 + doble apoyo J2, J3 y J4.
  - Base Ø 94 mm con 3 controles traseros al ras:
      1) XIAO ESP32-S3/C3 (USB-C para firmware/serial)
      2) Módulo USB-C PD `AR5515` (28×10×12 mm, fijado en 5V para cargador UGREEN 50W)
      3) Interruptor ON/OFF `KCD11-2P` negro (`AR0243`, recorte 13.5×9.0 mm)
    + `PCA9685` (`AR0389`), capacitor `1000 µF` (`AR1127`), transmisión 1:1 `22T:22T`
    y ranura curva dedicada para bajada limpia de cables sin pellizcos.
  - Insertos de latón M3 reales `AR2811` (`4.5 mm OD × 3.0 mm` -> barrenos Ø 4.1 × 3.8 mm).
  - Exporta `.STEP` completo + piezas `.STL` individuales separadas en:
      `cad/exports/stl_negro_mate/` y `cad/exports/stl_blanco_mate/` (0% purga AMS).
"""

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


def _place_xz(shape: cq.Workplane, origin_xz, angle_deg: float) -> cq.Workplane:
    ox, oz = origin_xz
    return shape.rotate((0, 0, 0), (0, 1, 0), -angle_deg).translate((ox, 0.0, oz))


def _spur_gear(teeth: int, module: float, thickness: float, bore_r: float) -> cq.Workplane:
    pitch_r = (teeth * module) / 2.0
    addendum = 0.92 * module
    dedendum = 1.15 * module
    r_out = pitch_r + addendum
    r_root = max(bore_r + 1.0, pitch_r - dedendum)
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
    return (
        cq.Workplane("XY")
        .polyline(pts)
        .close()
        .extrude(thickness)
        .faces(">Z")
        .workplane()
        .circle(bore_r)
        .cutThruAll()
    )


def _octagonal_beam_hollow(length: float, h0: float, h1: float, w0: float, w1: float, chamfer: float, duct_w: float, duct_h: float) -> cq.Workplane:
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
    duct = (
        cq.Workplane("YZ")
        .workplane(offset=6.0)
        .rect(duct_w, duct_h)
        .extrude(max(4.0, length - 12.0))
    )
    return outer.cut(duct)


def _mg90s_dummy_vertical() -> cq.Workplane:
    """MG90S real: origen en eje de salida (X=0,Y=0), cuerpo de Z=0 a Z=28.5, eje hacia +Z, cuerpo hacia +X."""
    bl, bw, bh = MG90S["body_l"], MG90S["body_w"], MG90S["body_h"]
    off_x = bl / 2.0 - MG90S["shaft_offset_from_end"]  # +5.4 mm
    body = cq.Workplane("XY").center(off_x, 0.0).rect(bl, bw).extrude(bh)
    flange = cq.Workplane("XY").workplane(offset=bh - 9.0).center(off_x, 0.0).rect(MG90S["flange_l"], bw).extrude(2.4)
    shaft = cq.Workplane("XY").workplane(offset=bh).circle(2.4).extrude(3.5)
    return body.union(flange).union(shaft)


def _mg90s_dummy_joint(tail_dir_xz=(0.0, -1.0), y_shaft_end=-9.0) -> cq.Workplane:
    """
    MG90S real orientado dentro de una articulación (eje Y):
      - Eje de salida apunta hacia -Y en Y = y_shaft_end (ej. -9.0 mm)
      - Cuerpo de 28.5 mm ocupa Y = y_shaft_end .. y_shaft_end + 28.5 (ej. -9.0 .. +19.5 mm)
      - La cola larga (+5.4 mm desde el eje) apunta en dirección `tail_dir_xz` en el plano XZ
        para alojarse 100% dentro de la torreta/eslabón sin sobresalir jamás del tambor!
    """
    bl, bw, bh = MG90S["body_l"], MG90S["body_w"], MG90S["body_h"]
    off_t = bl / 2.0 - MG90S["shaft_offset_from_end"]  # +5.4 mm hacia la cola
    ang_deg = math.degrees(math.atan2(tail_dir_xz[1], tail_dir_xz[0]))

    # Construir en plano XZ (eje extrusión es +Y de y_shaft_end a y_shaft_end + bh)
    # Nota: en CadQuery Workplane("XZ"), normal es -Y, así que extrudir negativo va hacia +Y
    body = (
        cq.Workplane("XZ")
        .workplane(offset=-y_shaft_end)  # plano en Y = y_shaft_end
        .center(off_t, 0.0)
        .rect(bl, bw)
        .extrude(-bh)  # hacia +Y hasta y_shaft_end + bh
    )
    flange = (
        cq.Workplane("XZ")
        .workplane(offset=-(y_shaft_end + 9.0))
        .center(off_t, 0.0)
        .rect(MG90S["flange_l"], bw)
        .extrude(2.4)
    )
    shaft = (
        cq.Workplane("XZ")
        .workplane(offset=-y_shaft_end)
        .circle(2.4)
        .extrude(3.2)  # hacia -Y para acoplar el horn
    )
    servo = body.union(flange).union(shaft)
    return servo.rotate((0, 0, 0), (0, 1, 0), -ang_deg)


def _bearing_608_dummy() -> cq.Workplane:
    return cq.Workplane("XY").circle(BEARING_608["od"] / 2.0).circle(BEARING_608["id"] / 2.0).extrude(BEARING_608["w"])


def build_cad_v2(pose_deg=None, explode: float = 0.0):
    """
    Construye el ensamblaje completo v2 (100% UNIT Electronics, cero colisiones).
    Retorna:
      - 'black_named': dict[nombre_archivo -> Workplane] (piezas PLA Negro Mate listas para STL)
      - 'white_named': dict[nombre_archivo -> Workplane] (piezas PLA Blanco Mate listas para STL)
      - 'black', 'white', 'servos', 'elec_pcb', 'steel', 'switch_red_or_blk' para render VTK y STEP
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
    z_cover = 3.2
    brg_w = BEARING_608["w"]     # 7.0 mm

    # ==================================================================
    # 1. BASE FIJA HUECA (PLA Negro Mate) — 608ZZ + 3 CONTROLES TRASEROS
    # ==================================================================
    base_shell = (
        cq.Workplane("XY")
        .circle(base_r)
        .extrude(BASE_LOWER_H)
        .edges(">Z or <Z")
        .chamfer(1.4)
    )
    # Cavidad interna principal (Z = 0 .. 37 mm; techo 7 mm donde asienta el 608ZZ)
    base_shell = base_shell.cut(
        cq.Workplane("XY").workplane(offset=-0.5).circle(cav_r).extrude(BASE_LOWER_H - brg_w + 0.5)
    )
    # Asiento de precisión para 608ZZ central (Ø 22.14 × 7.0 mm en Z = 37..44 mm)
    brg_seat_d = BEARING_608["od"] + BEARING_FIT
    base_shell = base_shell.cut(
        cq.Workplane("XY").workplane(offset=BASE_LOWER_H - brg_w).circle(brg_seat_d / 2.0).extrude(brg_w + 1.0)
    )
    # Paso central bajo el 608ZZ para el cubo/eje del engrane 22T (Ø 16 mm)
    base_shell = base_shell.cut(
        cq.Workplane("XY").workplane(offset=BASE_LOWER_H - brg_w - 3.0).circle(8.2).extrude(6.0)
    )
    # Ranura curva dedicada para paso de los 4 cables de servo en el techo (lado -X, radio 18 mm, ancho 8 mm)
    cable_slot = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - brg_w - 2.0)
        .center(-18.5, 0.0)
        .slot2D(22.0, 8.5, angle=90.0)
        .extrude(brg_w + 4.0)
    )
    base_shell = base_shell.cut(cable_slot)

    # 4 jefes internos con barrenos exactos para insertos UNIT `AR2811` (Ø 4.1 × 3.8 mm)
    for k in range(4):
        ang = math.radians(45.0 + k * 90.0)
        bx, by = (cav_r - 3.5) * math.cos(ang), (cav_r - 3.5) * math.sin(ang)
        boss = cq.Workplane("XY").workplane(offset=z_cover).center(bx, by).circle(4.4).extrude(10.0)
        hole = cq.Workplane("XY").workplane(offset=z_cover - 0.5).center(bx, by).circle(INSERT_M3_DIA / 2.0).extrude(INSERT_M3_DEPTH + 1.0)
        base_shell = base_shell.union(boss).cut(hole)

    # Bahía plana trasera en -X (ancho 50 mm en Y) para los 3 controles al ras:
    #   Y = -14.5 mm, Z = 10.5 mm -> USB-C de XIAO ESP32-S3/C3
    #   Y =  +1.5 mm, Z = 21.0 mm -> USB-C de potencia `AR5515` (5V PD desde tu UGREEN 50W)
    #   Y = +16.5 mm, Z = 21.5 mm -> Interruptor ON/OFF `KCD11-2P` negro (`13.5 × 9.0 mm`)
    rear_flat = (
        cq.Workplane("YZ")
        .workplane(offset=-base_r - 3.0)
        .center(0.0, 17.5)
        .rect(50.0, 26.0)
        .extrude(6.5)
    )
    cut_xiao_usbc = (
        cq.Workplane("YZ")
        .workplane(offset=-base_r - 3.0)
        .center(-14.5, 10.5)
        .slot2D(XIAO_ESP32["usbc_w"] + 1.6, XIAO_ESP32["usbc_h"] + 1.4)
        .extrude(15.0)
    )
    cut_pd_usbc = (
        cq.Workplane("YZ")
        .workplane(offset=-base_r - 3.0)
        .center(1.5, 21.0)
        .slot2D(USBC_PD_AR5515["usbc_w"] + 1.6, USBC_PD_AR5515["usbc_h"] + 1.4)
        .extrude(15.0)
    )
    cut_kcd11 = (
        cq.Workplane("YZ")
        .workplane(offset=-base_r - 3.0)
        .center(16.5, 21.5)
        .rect(SWITCH_KCD11["cut_w"], SWITCH_KCD11["cut_h"])
        .extrude(15.0)
    )
    # Repisa interna elevada (Z = 16.5 mm) en la pared trasera para soportar el módulo USB-C PD `AR5515`
    pd_shelf = (
        cq.Workplane("XY")
        .workplane(offset=15.0)
        .center(-28.5, 1.5)
        .rect(USBC_PD_AR5515["pcb_l"] + 2.0, USBC_PD_AR5515["pcb_w"] + 4.4)
        .extrude(3.0)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=16.2)
            .center(-28.5, 1.5)
            .rect(USBC_PD_AR5515["pcb_l"] + 0.5, USBC_PD_AR5515["pcb_w"] + 0.5)
            .extrude(4.0)
        )
    )
    # Soporte interno fijo para el servo J1 MG90S (en X = +22 mm, Y = 0)
    j1_x = 22.0
    j1_holder = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - brg_w - 11.0)
        .center(j1_x + 5.4, 0.0)
        .rect(MG90S["body_l"] + 6.4, MG90S["body_w"] + 6.4)
        .extrude(11.0)
    )
    j1_pocket = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - brg_w - 12.0)
        .center(j1_x + 5.4, 0.0)
        .rect(MG90S["body_l"] + CLEARANCE_FIT * 2, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(13.0)
    )
    base_shell = base_shell.union(pd_shelf).union(j1_holder).cut(j1_pocket)
    base_shell = base_shell.intersect(cq.Workplane("XY").circle(base_r - 0.05).extrude(BASE_LOWER_H))
    base_shell = base_shell.cut(rear_flat).cut(cut_xiao_usbc).cut(cut_pd_usbc).cut(cut_kcd11)

    black_named["01_base_fija_hueca"] = base_shell

    # Hardware real dentro de la base (para inspección de colisiones)
    z_brg_exp = 22.0 * explode
    steel.append(_bearing_608_dummy().translate((0.0, 0.0, BASE_LOWER_H - brg_w + z_brg_exp)))
    servos.append(_mg90s_dummy_vertical().translate((j1_x, 0.0, BASE_LOWER_H - brg_w - MG90S["body_h"] - 4.5)))
    j1_pinion = _spur_gear(22, 1.0, 5.2, 2.4).translate((j1_x, 0.0, BASE_LOWER_H - brg_w - 6.2))
    black_named["02_pinon_base_22t"] = j1_pinion

    # Módulo USB-C PD `AR5515` (28×10×12 mm) + Interruptor `KCD11-2P` montados atrás
    pd_pcb = (
        cq.Workplane("XY")
        .workplane(offset=18.0)
        .center(-28.5, 1.5)
        .rect(USBC_PD_AR5515["pcb_l"], USBC_PD_AR5515["pcb_w"])
        .extrude(1.6)
    )
    pd_usbc = (
        cq.Workplane("XY")
        .workplane(offset=19.6)
        .center(-39.5, 1.5)
        .rect(7.5, 9.0)
        .extrude(3.2)
    )
    pd_term = (
        cq.Workplane("XY")
        .workplane(offset=19.6)
        .center(-18.5, 1.5)
        .rect(7.5, 9.5)
        .extrude(8.5)
    )
    kcd_body = (
        cq.Workplane("YZ")
        .workplane(offset=-base_r + 3.5)
        .center(16.5, 21.5)
        .rect(SWITCH_KCD11["cut_w"] - 0.4, SWITCH_KCD11["cut_h"] - 0.4)
        .extrude(SWITCH_KCD11["depth"])
    )
    kcd_bezel = (
        cq.Workplane("YZ")
        .workplane(offset=-base_r + 2.2)
        .center(16.5, 21.5)
        .rect(SWITCH_KCD11["bezel_w"], SWITCH_KCD11["bezel_h"])
        .extrude(2.2)
    )
    elec_pcb.extend([pd_pcb, pd_term])
    steel.extend([pd_usbc, kcd_body, kcd_bezel])

    # ==================================================================
    # 2. TAPA INFERIOR + POSTES PCA9685 + CUNA XIAO ESP32-S3/C3
    # ==================================================================
    z_bot_exp = -42.0 * explode
    bot_cover = cq.Workplane("XY").circle(cav_r - CLEARANCE_FIT).extrude(z_cover)

    # PCA9685 centrado en X = -6.0 mm (X in [-18.7, +6.7], Y in [-31.25, +31.25]) -> cero colisión!
    pca_cx, pca_cy = -6.0, 0.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            px = pca_cx + sx * (PCA9685["hole_dy"] / 2.0)
            py = pca_cy + sy * (PCA9685["hole_dx"] / 2.0)
            bot_cover = bot_cover.union(
                cq.Workplane("XY").workplane(offset=z_cover).center(px, py).circle(2.8).extrude(4.5)
            )
    # Cuna deslizable modular para XIAO ESP32-S3/C3 (100% dentro del radio de la base, USB-C al ras en -40.0)
    xiao_cx, xiao_cy = -29.5, -14.5
    xiao_cradle = (
        cq.Workplane("XY")
        .workplane(offset=z_cover)
        .center(xiao_cx, xiao_cy)
        .rect(XIAO_ESP32["pcb_l"] + 3.0, XIAO_ESP32["pcb_w"] + 3.0)
        .extrude(5.5)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=z_cover + 2.2)
            .center(xiao_cx, xiao_cy)
            .rect(XIAO_ESP32["pcb_l"] + 0.4, XIAO_ESP32["pcb_w"] + 0.4)
            .extrude(4.5)
        )
    )
    # 4 barrenos avellanados M3 en la tapa inferior para fijación a los insertos `AR2811`
    for k in range(4):
        ang = math.radians(45.0 + k * 90.0)
        bx, by = (cav_r - 3.5) * math.cos(ang), (cav_r - 3.5) * math.sin(ang)
        bot_cover = bot_cover.cut(cq.Workplane("XY").workplane(offset=-0.5).center(bx, by).circle(1.7).extrude(z_cover + 1.0))

    bot_cover = bot_cover.union(xiao_cradle).translate((0, 0, z_bot_exp))
    black_named["03_tapa_inferior_electronica"] = bot_cover

    # Dummies electrónicos reales en la tapa
    pca_pcb = cq.Workplane("XY").workplane(offset=z_cover + 4.5 + z_bot_exp).center(pca_cx, pca_cy).rect(PCA9685["pcb_w"], PCA9685["pcb_l"]).extrude(1.6)
    pca_headers = cq.Workplane("XY").workplane(offset=z_cover + 6.1 + z_bot_exp).center(pca_cx + 6.2, pca_cy).rect(8.5, 50.0).extrude(8.5)
    xiao_pcb = cq.Workplane("XY").workplane(offset=z_cover + 5.4 + z_bot_exp).center(xiao_cx, xiao_cy).rect(XIAO_ESP32["pcb_l"], XIAO_ESP32["pcb_w"]).extrude(1.6)
    xiao_usbc = cq.Workplane("XY").workplane(offset=z_cover + 7.0 + z_bot_exp).center(xiao_cx - XIAO_ESP32["pcb_l"] / 2.0 + 3.5, xiao_cy).rect(7.5, 9.0).extrude(3.2)
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
    # 4. TORRETA GIRATORIA J1 + ENGRANE 22T + HORQUILLA HOMBRO J2 (ENCAPSULADO 100%)
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
    # Eje Ø 7.86 mm que entra al 608ZZ central + engrane inferior 22T SEPARADO (para ensamblar a través del 608ZZ!)
    shaft_r = (BEARING_608["id"] - BEARING_FIT) / 2.0  # 3.93 mm
    spigot = (
        cq.Workplane("XY")
        .workplane(offset=BASE_LOWER_H - brg_w - 5.8)
        .circle(shaft_r)
        .extrude(brg_w + BASE_RING_H + 10.5)
    )
    # Barreno central M3 en la punta inferior del eje para fijar el engrane 22T con un tornillo M3×8
    spigot_m3 = cq.Workplane("XY").workplane(offset=BASE_LOWER_H - brg_w - 6.5).circle(1.45).extrude(11.0)
    turret_gear = _spur_gear(22, 1.0, 5.2, shaft_r + 0.12).translate((0.0, 0.0, BASE_LOWER_H - brg_w - 6.0))

    # Pedestal robusto del hombro subiendo hasta Z = 82 mm:
    #   Lado +Y (Y = -8.5 .. +22): aloja MG90S J2 vertical hacia abajo (100% oculto!)
    #   Lado -Y (Y = -22 .. -12.5): aloja rodamiento 608ZZ (Ø 22.14 × 7.0 mm)
    j2_drum = (
        cq.Workplane("XZ")
        .center(0.0, D1_BASE_TO_SHOULDER)
        .circle(J2_DRUM_DIA / 2.0)
        .extrude(J2_DRUM_W / 2.0, both=True)
        .edges()
        .chamfer(1.4)
    )
    # Columna derecha (+Y) envolviendo la cola vertical del MG90S hacia abajo hasta la corona
    col_r = (
        cq.Workplane("XY")
        .workplane(offset=tur_z0 + BASE_CROWN_H - 3.0)
        .center(0.0, 6.2)
        .rect(34.0, 30.4)
        .extrude(D1_BASE_TO_SHOULDER - (tur_z0 + BASE_CROWN_H) + 3.0)
        .edges("|Z")
        .fillet(4.0)
    )
    # Columna izquierda (-Y) soportando la pared del 608ZZ (remetida 0.8 mm del bisel del tambor para unión limpia)
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

    # Recorte central del tambor J2 para el brazo articulado de L2 (Y = -12.8 .. -8.2 mm)
    j2_hub_slot = (
        cq.Workplane("XZ")
        .workplane(offset=8.2)  # plano en Y = -8.2 mm
        .center(0.0, D1_BASE_TO_SHOULDER)
        .circle(J2_DRUM_DIA / 2.0 + 2.0)
        .extrude(4.8)  # hacia -Y hasta Y = -13.0 mm
    )
    # Bolsillo exacto para MG90S J2 (Y = -8.8 .. +20.2 mm, cola hacia -Z dentro de col_r)
    j2_servo_pocket = (
        cq.Workplane("XZ")
        .workplane(offset=8.8)  # Y = -8.8
        .center(0.0, D1_BASE_TO_SHOULDER - 5.4)
        .rect(MG90S["body_w"] + CLEARANCE_FIT * 2, MG90S["body_l"] + CLEARANCE_FIT * 2)
        .extrude(-MG90S["pocket_depth"])  # hacia +Y hasta Y = +20.2
    )
    # Asiento 608ZZ en -Y de J2 (Y = -19.8 .. -12.5 mm)
    j2_brg_seat = (
        cq.Workplane("XZ")
        .workplane(offset=19.8)  # Y = -19.8
        .center(0.0, D1_BASE_TO_SHOULDER)
        .circle(brg_seat_d / 2.0)
        .extrude(-brg_w - 0.5)  # hacia +Y hasta -12.3
    )
    # Paso de cables en la corona alineado con la ranura curva de la base
    tur_cable_hole = (
        cq.Workplane("XY")
        .workplane(offset=tur_z0 - 1.0)
        .center(-18.5, 0.0)
        .circle(5.5)
        .extrude(BASE_CROWN_H + 4.0)
    )
    turret_solid = turret_solid.cut(j2_hub_slot).cut(j2_servo_pocket).cut(j2_brg_seat).cut(tur_cable_hole)

    # Helpers de rotación Q1 y tapas B2 Stealth
    def apply_q1(shape):
        return shape.rotate((0, 0, 0), (0, 0, 1), q1) if abs(q1) > 1e-6 else shape

    black_named["04_torreta_j1_hombro"] = apply_q1(turret_solid.translate((0, 0, z_tur_exp)))
    black_named["04b_engrane_torreta_22t"] = apply_q1(turret_gear.translate((0, 0, -14.0 * explode)))

    # Servo real J2 MG90S (cola hacia -Z, 100% encapsulado en Y = -9.0 .. +19.5!) + Rodamiento 608ZZ
    j2_servo = _mg90s_dummy_joint(tail_dir_xz=(0.0, -1.0), y_shaft_end=-9.0).translate((0.0, 0.0, D1_BASE_TO_SHOULDER + z_tur_exp))
    j2_brg = _bearing_608_dummy().rotate((0, 0, 0), (1, 0, 0), 90.0).translate((0.0, -12.5, D1_BASE_TO_SHOULDER + z_tur_exp))
    servos.append(apply_q1(j2_servo))
    steel.append(apply_q1(j2_brg))

    def add_stealth_caps(tag: str, center_xz, drum_w, cap_d, z_off=0.0, exp_y=0.0):
        cx, cz = center_xz[0], center_xz[1] + z_off
        for s_idx, side in enumerate((-1, 1)):
            suf = "izq" if side == -1 else "der"
            y_pos = side * (drum_w / 2.0 + exp_y)
            white_ring = (
                cq.Workplane("XZ")
                .workplane(offset=-y_pos + side * 0.6)
                .center(cx, cz)
                .circle(cap_d / 2.0)
                .circle((cap_d - 2.8) / 2.0)
                .extrude(-side * 1.8)
            )
            inner_cap = (
                cq.Workplane("XZ")
                .workplane(offset=-y_pos + side * 0.6)
                .center(cx, cz)
                .circle((cap_d - 3.1) / 2.0)
                .extrude(-side * 1.8)
                .edges()
                .chamfer(0.35)
            )
            white_named[f"w_aro_{tag}_{suf}"] = apply_q1(white_ring)
            black_named[f"tapa_{tag}_{suf}"] = apply_q1(inner_cap)
            bcd = cap_d * 0.66
            br = 1.5 if cap_d >= 26 else 1.25
            for k in range(4):
                ang = math.radians(45.0 + k * 90.0)
                bx = cx + (bcd / 2.0) * math.cos(ang)
                bz = cz + (bcd / 2.0) * math.sin(ang)
                bolt = (
                    cq.Workplane("XZ")
                    .workplane(offset=-(y_pos + side * 0.6))
                    .center(bx, bz)
                    .circle(br)
                    .extrude(-side * 1.0)
                )
                steel.append(apply_q1(bolt))

    p2 = (0.0, D1_BASE_TO_SHOULDER)
    a2_rad = math.radians(q2)
    p3 = (p2[0] + A2_LOWER_ARM * math.cos(a2_rad), p2[1] + A2_LOWER_ARM * math.sin(a2_rad))
    a3_rad = math.radians(q2 + q3)
    p4 = (p3[0] + A3_FOREARM * math.cos(a3_rad), p3[1] + A3_FOREARM * math.sin(a3_rad))

    add_stealth_caps("j2", p2, J2_DRUM_W, J2_CAP_DIA, z_off=z_tur_exp, exp_y=20.0 * explode)

    # ==================================================================
    # 5. ESLABÓN INFERIOR L2 (a2 = 82 mm) + CANAL OCULTO + TAMBOR CODO J3
    # ==================================================================
    exp_l2 = (22.0 * math.cos(a2_rad) * explode, 22.0 * math.sin(a2_rad) * explode + z_tur_exp)
    p2_e = (p2[0] + exp_l2[0], p2[1] + exp_l2[1])
    p3_e = (p3[0] + exp_l2[0], p3[1] + exp_l2[1])

    # Disco motriz en J2 (encaja en ranura Y = -12.6 .. -8.5) + muñón Ø 7.86 mm hacia 608ZZ
    l2_hub = cq.Workplane("XZ").workplane(offset=12.6).circle(16.0).extrude(-4.2)  # Y = -12.6 .. -8.4
    l2_pin = cq.Workplane("XZ").workplane(offset=12.6).circle(shaft_r).extrude(7.2)  # hacia -Y hasta -19.8
    # Viga octagonal hueca B2 Stealth (centrada en Y = 0, conectada limpiamente al disco motriz)
    l2_beam = _octagonal_beam_hollow(A2_LOWER_ARM, 25.0, 22.0, 24.0, 22.0, chamfer=3.8, duct_w=8.5, duct_h=7.0)
    # Recorte en el extremo inicial de L2 para no chocar con el cuerpo interno del MG90S J2
    l2_j2_clear = cq.Workplane("XZ").workplane(offset=8.4).circle(19.0).extrude(-30.0)
    l2_beam = l2_beam.cut(l2_j2_clear)

    # Tambor de Codo J3 al final de L2 (Ø 38 × 43 mm) con bolsillo MG90S J3 (cola hacia -X dentro de L2!) + asiento 608ZZ
    j3_drum = (
        cq.Workplane("XZ")
        .center(A2_LOWER_ARM, 0.0)
        .circle(J3_DRUM_DIA / 2.0)
        .extrude(J3_DRUM_W / 2.0, both=True)
        .edges()
        .chamfer(1.2)
    )
    j3_slot = cq.Workplane("XZ").workplane(offset=8.2).center(A2_LOWER_ARM, 0.0).circle(J3_DRUM_DIA / 2.0 + 2.0).extrude(4.6)
    j3_servo_cut = (
        cq.Workplane("XZ")
        .workplane(offset=8.8)
        .center(A2_LOWER_ARM - 5.4, 0.0)
        .rect(MG90S["body_l"] + CLEARANCE_FIT * 2, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-MG90S["pocket_depth"])
    )
    j3_brg_cut = (
        cq.Workplane("XZ")
        .workplane(offset=19.5)
        .center(A2_LOWER_ARM, 0.0)
        .circle(brg_seat_d / 2.0)
        .extrude(-brg_w - 0.5)
    )
    l2_part = l2_hub.union(l2_pin).union(l2_beam).union(j3_drum).cut(j3_slot).cut(j3_servo_cut).cut(j3_brg_cut)
    black_named["05_eslabon_l2_codo"] = apply_q1(_place_xz(l2_part, p2_e, q2))

    # Servo real J3 MG90S (cola a lo largo de -L2 -> 100% oculto!) + 608ZZ J3
    j3_tail = (-math.cos(a2_rad), -math.sin(a2_rad))
    j3_servo = _mg90s_dummy_joint(tail_dir_xz=j3_tail, y_shaft_end=-9.0).translate((p3_e[0], 0.0, p3_e[1]))
    j3_brg = _bearing_608_dummy().rotate((0, 0, 0), (1, 0, 0), 90.0).translate((p3_e[0], -12.5, p3_e[1]))
    servos.append(apply_q1(j3_servo))
    steel.append(apply_q1(j3_brg))
    add_stealth_caps("j3", p3_e, J3_DRUM_W, J3_CAP_DIA, z_off=0.0, exp_y=20.0 * explode)

    # ==================================================================
    # 6. ANTEBRAZO L3 (a3 = 70 mm) + CANAL OCULTO + TAMBOR MUÑECA J4
    # ==================================================================
    exp_l3 = (exp_l2[0] + 26.0 * math.cos(a3_rad) * explode, exp_l2[1] + 26.0 * math.sin(a3_rad) * explode)
    p3_f = (p3[0] + exp_l3[0], p3[1] + exp_l3[1])
    p4_f = (p4[0] + exp_l3[0], p4[1] + exp_l3[1])

    l3_hub = cq.Workplane("XZ").workplane(offset=12.4).circle(14.5).extrude(-4.0)
    l3_pin = cq.Workplane("XZ").workplane(offset=12.4).circle(shaft_r).extrude(7.0)
    l3_beam = _octagonal_beam_hollow(A3_FOREARM, 21.0, 18.0, 20.5, 18.0, chamfer=3.2, duct_w=7.2, duct_h=6.0)
    l3_j3_clear = cq.Workplane("XZ").workplane(offset=8.4).circle(17.0).extrude(-28.0)
    l3_beam = l3_beam.cut(l3_j3_clear)

    j4_drum = (
        cq.Workplane("XZ")
        .center(A3_FOREARM, 0.0)
        .circle(J4_DRUM_DIA / 2.0)
        .extrude(J4_DRUM_W / 2.0, both=True)
        .edges()
        .chamfer(1.0)
    )
    j4_slot = cq.Workplane("XZ").workplane(offset=8.2).center(A3_FOREARM, 0.0).circle(J4_DRUM_DIA / 2.0 + 2.0).extrude(4.4)
    j4_servo_cut = (
        cq.Workplane("XZ")
        .workplane(offset=8.8)
        .center(A3_FOREARM - 5.4, 0.0)
        .rect(MG90S["body_l"] + CLEARANCE_FIT * 2, MG90S["body_w"] + CLEARANCE_FIT * 2)
        .extrude(-MG90S["pocket_depth"])
    )
    j4_brg_cut = (
        cq.Workplane("XZ")
        .workplane(offset=19.2)
        .center(A3_FOREARM, 0.0)
        .circle(brg_seat_d / 2.0)
        .extrude(-brg_w - 0.5)
    )
    l3_part = l3_hub.union(l3_pin).union(l3_beam).union(j4_drum).cut(j4_slot).cut(j4_servo_cut).cut(j4_brg_cut)
    black_named["06_antebrazo_l3_muneca"] = apply_q1(_place_xz(l3_part, p3_f, q2 + q3))

    # Servo real J4 MG90S (cola a lo largo de -L3 -> 100% oculto!) + 608ZZ J4
    j4_tail = (-math.cos(a3_rad), -math.sin(a3_rad))
    j4_servo = _mg90s_dummy_joint(tail_dir_xz=j4_tail, y_shaft_end=-9.0).translate((p4_f[0], 0.0, p4_f[1]))
    j4_brg = _bearing_608_dummy().rotate((0, 0, 0), (1, 0, 0), 90.0).translate((p4_f[0], -12.2, p4_f[1]))
    servos.append(apply_q1(j4_servo))
    steel.append(apply_q1(j4_brg))
    add_stealth_caps("j4", p4_f, J4_DRUM_W, J4_CAP_DIA, z_off=0.0, exp_y=18.0 * explode)

    # ==================================================================
    # 7. PINZA PARALELA SG90 — CARENADO INFERIOR BISELADO (SG90 100% OCULTO!)
    # ==================================================================
    wrist_ang = q2 + q3 + q4
    a4_rad = math.radians(wrist_ang)
    exp_l4 = (exp_l3[0] + 30.0 * math.cos(a4_rad) * explode, exp_l3[1] + 30.0 * math.sin(a4_rad) * explode)
    p4_g = (p4[0] + exp_l4[0], p4[1] + exp_l4[1])

    w_hub = cq.Workplane("XZ").workplane(offset=12.2).circle(11.5).extrude(-3.8)
    w_pin = cq.Workplane("XZ").workplane(offset=12.2).circle(shaft_r).extrude(6.8)
    w_bridge = cq.Workplane("XY").workplane(offset=-5.0).center(10.0, -5.0).rect(14.0, 14.0).extrude(10.0)
    collar = cq.Workplane("YZ").workplane(offset=11.0).circle(12.2).extrude(8.0).edges().chamfer(0.7)
    collar_ring = cq.Workplane("YZ").workplane(offset=14.8).circle(12.6).circle(10.4).extrude(2.2)

    # Palma stealth con carenado inferior biselado (Z = -21.5 .. +7.0 mm) que OCULTA 100% el SG90 (22.7 mm alto)!
    palm_upper = (
        cq.Workplane("YZ")
        .workplane(offset=18.5)
        .rect(28.0, 14.5)
        .extrude(16.0)
        .edges()
        .chamfer(1.2)
    )
    # Carenado inferior biselado minimalista envolviendo 100% el cuerpo del SG90 (cero esquinas visibles!)
    chin_shroud = (
        cq.Workplane("XY")
        .workplane(offset=-21.5)
        .center(27.0, 0.0)
        .rect(28.5, 18.0)
        .workplane(offset=16.5)
        .rect(29.5, 23.0)
        .loft(ruled=True)
    )
    # Bolsillo interno exacto para el SG90 (22.9 × 12.2 × 23.0 mm, accesible desde abajo)
    sg90_pocket = (
        cq.Workplane("XY")
        .workplane(offset=-19.8)
        .center(26.5, 0.0)
        .rect(SG90["body_l"] + 0.4, SG90["body_w"] + 0.4)
        .extrude(SG90["body_h"] + 1.5)
    )
    palm_top = cq.Workplane("XY").workplane(offset=7.4).center(29.0, 0.0).rect(17.5, 25.0).extrude(2.6).edges("|Z").fillet(2.4)
    palm_full = w_hub.union(w_pin).union(w_bridge).union(collar).union(palm_upper).union(chin_shroud).union(palm_top).cut(sg90_pocket)

    black_named["07_palma_pinza_sg90"] = apply_q1(_place_xz(palm_full, p4_g, wrist_ang))
    white_named["w02_collar_muneca_blanco"] = apply_q1(_place_xz(collar_ring, p4_g, wrist_ang))

    # SG90 real 100% oculto dentro del carenado inferior (Z = -19.2 .. +3.5 mm)
    sg90_real = cq.Workplane("XY").workplane(offset=-19.2).center(26.5, 0.0).rect(SG90["body_l"], SG90["body_w"]).extrude(SG90["body_h"])
    servos.append(apply_q1(_place_xz(sg90_real, p4_g, wrist_ang)))

    # 2 Engranes 14T B2 Stealth (negros + aros blancos centrales)
    gear_x, gear_y = 31.5, 7.1
    g_l = _spur_gear(14, 1.0, 4.6, 2.0).translate((gear_x, gear_y, 2.4))
    g_r = _spur_gear(14, 1.0, 4.6, 2.0).rotate((0, 0, 0), (0, 0, 1), 360.0 / 28.0).translate((gear_x, -gear_y, 2.4))
    black_named["08_engrane_pinza_izq"] = apply_q1(_place_xz(g_l, p4_g, wrist_ang))
    black_named["09_engrane_pinza_der"] = apply_q1(_place_xz(g_r, p4_g, wrist_ang))

    for idx_g, sy in enumerate((-gear_y, gear_y)):
        hr = cq.Workplane("XY").workplane(offset=6.9).center(gear_x, sy).circle(3.6).circle(2.1).extrude(0.6)
        pin = cq.Workplane("XY").workplane(offset=1.8).center(gear_x, sy).circle(1.85).extrude(8.8)
        white_named[f"w03_aro_engrane_{idx_g}"] = apply_q1(_place_xz(hr, p4_g, wrist_ang))
        steel.append(apply_q1(_place_xz(pin, p4_g, wrist_ang)))

    # 2 Dedos paralelos biselados + almohadillas blancas (TCP exacto a a4 = 53 mm desde J4)
    half_gap = max(2.5, min(15.0, grip_open / 2.0))
    for side_name, side in [("izq", 1), ("der", -1)]:
        pts_arm = [
            (gear_x - 2.0, side * (gear_y - 2.0)),
            (gear_x + 9.5, side * (half_gap + 1.4)),
            (gear_x + 9.5, side * (half_gap + 5.2)),
            (gear_x - 2.0, side * (gear_y + 2.0)),
        ]
        if side < 0:
            pts_arm = list(reversed(pts_arm))
        arm_f = (
            cq.Workplane("XY").workplane(offset=-3.2)
            .polyline(pts_arm).close().extrude(6.4)
        )
        pts_jaw = [
            (gear_x + 8.0, side * (half_gap + 1.4)),
            (gear_x + 28.5, side * (half_gap + 1.4)),
            (gear_x + 28.5, side * (half_gap + 4.5)),
            (gear_x + 11.0, side * (half_gap + 6.8)),
            (gear_x + 8.0, side * (half_gap + 5.6)),
        ]
        if side < 0:
            pts_jaw = list(reversed(pts_jaw))
        jaw = (
            cq.Workplane("XY").workplane(offset=-4.8)
            .polyline(pts_jaw).close().extrude(9.6).edges("|Z").fillet(0.75)
        )
        pts_pad = [
            (gear_x + 12.0, side * half_gap),
            (gear_x + 27.8, side * half_gap),
            (gear_x + 27.8, side * (half_gap + 1.55)),
            (gear_x + 12.0, side * (half_gap + 1.55)),
        ]
        if side < 0:
            pts_pad = list(reversed(pts_pad))
        pad = (
            cq.Workplane("XY").workplane(offset=-4.0)
            .polyline(pts_pad).close().extrude(8.0)
        )
        black_named[f"10_dedo_pinza_{side_name}"] = apply_q1(_place_xz(arm_f.union(jaw), p4_g, wrist_ang))
        white_named[f"w04_almohadilla_{side_name}"] = apply_q1(_place_xz(pad, p4_g, wrist_ang))

    return {
        "black_named": black_named,
        "white_named": white_named,
        "black": list(black_named.values()),
        "white": list(white_named.values()),
        "servos": servos,
        "elec_pcb": elec_pcb,
        "steel": steel,
    }


def export_all_v2():
    here = os.path.dirname(os.path.abspath(__file__))
    exp_dir = os.path.join(here, "exports")
    stl_blk = os.path.join(exp_dir, "stl_negro_mate")
    stl_wht = os.path.join(exp_dir, "stl_blanco_mate")
    stl_hw  = os.path.join(exp_dir, "hardware_ref")
    os.makedirs(stl_blk, exist_ok=True)
    os.makedirs(stl_wht, exist_ok=True)
    os.makedirs(stl_hw, exist_ok=True)

    parts = build_cad_v2(explode=0.0)

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
        15: "hw_rodamiento_608zz_j3",
        24: "hw_rodamiento_608zz_j4",
    }

    # 1. Exportar STEP ensamblado completo (con nombres descriptivos para el árbol de SolidWorks!)
    assy = cq.Assembly(name="MiniPro_4DOF_B2_Stealth_v2_UNIT")
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

    step_path = os.path.join(exp_dir, "mini_pro_b2_stealth_v2.step")
    assy.export(step_path)
    print(f"Exported STEP: {step_path}")

    # 2. Exportar STLs individuales separados por filamento (0% purga AMS en Bambu Lab A1 Combo!)
    for name, s in parts["black_named"].items():
        cq.exporters.export(s, os.path.join(stl_blk, f"{name}.stl"), tolerance=0.03, angularTolerance=0.08)
    for name, s in parts["white_named"].items():
        cq.exporters.export(s, os.path.join(stl_wht, f"{name}.stl"), tolerance=0.03, angularTolerance=0.08)

    print(f"Exported {len(parts['black_named'])} Negro Mate STLs -> {stl_blk}")
    print(f"Exported {len(parts['white_named'])} Blanco Mate STLs -> {stl_wht}")
    print(f"Exported hardware ref STLs -> {stl_hw}")


if __name__ == "__main__":
    export_all_v2()
