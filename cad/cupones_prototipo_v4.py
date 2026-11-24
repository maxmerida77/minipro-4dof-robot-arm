"""
Kit Progresivo de Cupones de Prototipado — Mini-Pro 4-DOF (`B2 Stealth` v4 Clean-DFA)
======================================================================================
Implementa exactamente el orden recomendado de prototipado de la auditoría cruzada (Codex):
  1. `cupon_1_ajustes_pivote_bayoneta.3mf` (~18 min):
     Bloque compacto con alojamiento real MG90S (cuerpo+orejas+2×M2), ranura tuerca cautiva M3 +
     bolsillo Nyloc, alojamiento real de bayoneta 32° + tapa `tapa_j2_izq` + separador `11_separador_m3_j2`
     y mini-canal cola de milano con tapa deslizable. Valida 10 aperturas de bayoneta y ajuste sin juego!
  2. `cupon_2_articulacion_piloto_j2.3mf` (~40 min):
     UNA articulación completa J2 independiente (base corta con tambor J2 real + muñón de horquilla U
     de 32 mm con acceso Ø5.2 mm al tornillo del horn + separador M3 + 2 tapas bayoneta) para probar
     con 1 MG90S real, tuerca Nyloc y desarmador ANTES de imprimir las 3 articulaciones.
  3. `cupon_3_pinza_independiente_mearm15.3mf` (~35 min):
     Pinza paralela abierta MeArm módulo 1.5 (12T) completa orientada en Z=0 lista para probar
     apertura 0–30 mm, paralelismo, fuerza de cierre y posición TCP=53 mm con tu SG90.
"""

import math
import os
import sys
import cadquery as cq
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from params import (
    MG90S,
    CLEARANCE_FIT,
    M3_NUT_AF,
    M3_NUT_H,
    M3_NYLOC_H,
    M3_SPACER_OD,
    J2_DRUM_DIA,
    J2_CAP_DIA,
    HERO_POSE_DEG,
)
from mini_pro_b2_stealth_v4 import (
    HUB_HALF_W,
    FORK_IN_Y,
    FORK_THK,
    FORK_OUT_Y,
    _cyl_y,
    _horn_recess_xz,
    _bayonet_socket_cut_xz,
    _bayonet_cap_and_ring_xz,
    _m3_pivot_spacer_xz,
    _servo_hub_drum_xz,
    _servo_hub_cuts_xz,
)

V4_DIR = os.path.join(HERE, "exports", "v4_clean_dfa")
OUT_DIR = os.path.join(V4_DIR, "cupones_prueba")


def _cq_to_trimesh(wp: cq.Workplane, tmp_stl: str) -> trimesh.Trimesh:
    cq.exporters.export(wp, tmp_stl, tolerance=0.04, angularTolerance=0.1)
    m = trimesh.load(tmp_stl, force="mesh")
    os.remove(tmp_stl)
    assert m.is_watertight, "Cupón no estanco!"
    assert len(m.split(only_watertight=False)) == 1, f"Cupón con múltiples cuerpos: {len(m.split(only_watertight=False))}"
    return m


def _seat_z0(m: trimesh.Trimesh, rots=(), tx=0.0, ty=0.0) -> trimesh.Trimesh:
    out = m.copy()
    c = out.bounds.mean(axis=0)
    out.apply_translation(-c)
    axes = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
    for ax, deg in rots:
        out.apply_transform(trimesh.transformations.rotation_matrix(math.radians(deg), axes[ax]))
    bmin, bmax = out.bounds
    out.apply_translation([tx - 0.5 * (bmin[0] + bmax[0]), ty - 0.5 * (bmin[1] + bmax[1]), -bmin[2]])
    return out


def _export_plate(meshes_named, out_3mf: str, out_stl: str = None):
    scene = trimesh.Scene()
    for name, m in meshes_named:
        assert abs(m.bounds[0][2]) < 1e-3, f"{name} no apoyado en Z=0 ({m.bounds[0][2]:.3f})"
        assert m.is_watertight and len(m.split(only_watertight=False)) == 1, f"Fallo malla en {name}"
        scene.add_geometry(m, node_name=name, geom_name=name)
    with open(out_3mf, "wb") as f:
        f.write(scene.export(file_type="3mf"))
    if out_stl:
        trimesh.util.concatenate([m for _, m in meshes_named]).export(out_stl)


def build_cupon_1():
    """Cupón 1: Ajustes MG90S + tuercas cautivas M3/Nyloc + bayoneta 32° + separador M3 + cola de milano."""
    tmp = os.path.join(OUT_DIR, "_tmp1.stl")

    # Bloque calibrador 66 × 40 × 10 mm con pruebas de holgura reales
    blk = cq.Workplane("XY").rect(66.0, 40.0).extrude(10.0).edges("|Z").fillet(2.0)
    # 1) Alojamiento MG90S (cuerpo + orejas + 2× M2) en X = -18
    mg_body = cq.Workplane("XY").workplane(offset=-0.5).center(-18.0, 0.0).rect(MG90S["body_w"] + CLEARANCE_FIT * 2, MG90S["body_l"] + CLEARANCE_FIT * 2).extrude(12.0)
    mg_flng = cq.Workplane("XY").workplane(offset=5.2).center(-18.0, 0.0).rect(MG90S["body_w"] + CLEARANCE_FIT * 2, MG90S["flange_l"] + 0.8).extrude(6.0)
    mg_m2a = cq.Workplane("XY").workplane(offset=-0.5).center(-18.0, +MG90S["hole_pitch"] / 2.0).circle(0.95).extrude(12.0)
    mg_m2b = cq.Workplane("XY").workplane(offset=-0.5).center(-18.0, -MG90S["hole_pitch"] / 2.0).circle(0.95).extrude(12.0)

    # 2) Prueba tuerca M3 estándar y Nyloc cautivas en X = +2
    m3_a = cq.Workplane("XY").workplane(offset=-0.5).center(2.0, -10.0).circle(1.70).extrude(12.0)
    hex_std = cq.Workplane("XY").workplane(offset=3.5).center(2.0, -10.0).polygon(6, M3_NUT_AF / math.cos(math.pi / 6.0)).extrude(M3_NUT_H)
    slot_std = cq.Workplane("XY").workplane(offset=3.5).center(2.0, -16.0).rect(M3_NUT_AF, 12.0).extrude(M3_NUT_H)

    m3_b = cq.Workplane("XY").workplane(offset=-0.5).center(2.0, +10.0).circle(1.70).extrude(12.0)
    hex_nyl = cq.Workplane("XY").workplane(offset=3.0).center(2.0, +10.0).polygon(6, M3_NUT_AF / math.cos(math.pi / 6.0)).extrude(M3_NYLOC_H)
    slot_nyl = cq.Workplane("XY").workplane(offset=3.0).center(2.0, +16.0).rect(M3_NUT_AF, 12.0).extrude(M3_NYLOC_H)

    # 3) Mini-canal cola de milano (`dovetail`) en X = +20..+30 (eje Y)
    ch_w_bot, ch_w_top, ch_d = 8.0, 6.6, 4.8
    dove_pts = [
        (-ch_w_top / 2.0, 10.2), (ch_w_top / 2.0, 10.2),
        (ch_w_bot / 2.0, 10.0 - 1.6), (ch_w_bot / 2.0, 10.0 - ch_d),
        (-ch_w_bot / 2.0, 10.0 - ch_d), (-ch_w_bot / 2.0, 10.0 - 1.6),
    ]
    dove_cut = cq.Workplane("XZ").workplane(offset=-21.0).center(22.0, 0.0).polyline(dove_pts).close().extrude(-42.0)

    blk = blk.cut(mg_body).cut(mg_flng).cut(mg_m2a).cut(mg_m2b).cut(m3_a).cut(hex_std).cut(slot_std).cut(m3_b).cut(hex_nyl).cut(slot_nyl).cut(dove_cut)

    # Tapa mini cola de milano
    tol = 0.25
    lid_pts = [
        (-(ch_w_top / 2.0 - tol), 1.45), (+(ch_w_top / 2.0 - tol), 1.45),
        (+(ch_w_bot / 2.0 - tol), 0.0), (-(ch_w_bot / 2.0 - tol), 0.0),
    ]
    mini_lid = cq.Workplane("XZ").polyline(lid_pts).close().extrude(26.0)

    # Placa de prueba de bayoneta real J2 (espesor 4.6 mm con rebaje + labio + ranura + barreno separador M3)
    bay_plate = _cyl_y(0.0, 0.0, J2_CAP_DIA / 2.0 + 3.5, -FORK_OUT_Y, -FORK_IN_Y)
    bay_plate = bay_plate.cut(_cyl_y(0.0, 0.0, (M3_SPACER_OD + 0.40) / 2.0, -FORK_OUT_Y - 1.0, -FORK_IN_Y + 1.0))
    bay_plate = bay_plate.cut(_cyl_y(0.0, 0.0, 4.60, -FORK_OUT_Y - 0.5, -(FORK_OUT_Y - 1.45)))
    bay_plate = bay_plate.cut(_bayonet_socket_cut_xz((0.0, 0.0), J2_CAP_DIA, -1))

    cap_j2, _ring = _bayonet_cap_and_ring_xz((0.0, 0.0), J2_CAP_DIA, -1)
    spacer_j2 = _m3_pivot_spacer_xz((0.0, 0.0))

    m_blk = _seat_z0(_cq_to_trimesh(blk, tmp), (), tx=95.0, ty=128.0)
    m_bay = _seat_z0(_cq_to_trimesh(bay_plate, tmp), [("x", -90.0)], tx=155.0, ty=146.0)
    m_cap = _seat_z0(_cq_to_trimesh(cap_j2, tmp), [("x", +90.0)], tx=155.0, ty=106.0)
    m_spc = _seat_z0(_cq_to_trimesh(spacer_j2, tmp), [("x", +90.0)], tx=188.0, ty=146.0)
    m_lid = _seat_z0(_cq_to_trimesh(mini_lid, tmp), [("x", +90.0)], tx=188.0, ty=112.0)

    out_3mf = os.path.join(OUT_DIR, "cupon_1_ajustes_pivote_bayoneta.3mf")
    out_stl = os.path.join(OUT_DIR, "cupon_1_ajustes_pivote_bayoneta.stl")
    _export_plate([
        ("bloque_ajustes_mg90s_m3_dovetail", m_blk),
        ("disco_alojamiento_bayoneta_j2", m_bay),
        ("tapa_bayoneta_j2_prueba", m_cap),
        ("separador_m3_pivote_prueba", m_spc),
        ("tapa_dovetail_prueba", m_lid),
    ], out_3mf, out_stl)
    print(f"[OK] Cupón 1 exportado (5 piezas @ Z=0): {out_3mf}")


def build_cupon_2():
    """Cupón 2: Articulación piloto J2 completa independiente (hub MG90S + muñón horquilla U + separador + 2 bayonetas)."""
    tmp = os.path.join(OUT_DIR, "_tmp2.stl")
    j2_hub_r = J2_DRUM_DIA / 2.0 - 0.8  # 18.2 mm

    # Base fija de mesa con tambor J2 exacto a Z = 32 mm
    pedestal = cq.Workplane("XY").rect(42.0, HUB_HALF_W * 2.0).extrude(32.0).edges("|Z").fillet(3.0)
    drum = _servo_hub_drum_xz((0.0, 32.0), j2_hub_r)
    cuts = _servo_hub_cuts_xz((0.0, 32.0), tail_dir_xz=(0.0, -1.0))
    j2_test_hub = pedestal.union(drum).cut(cuts)

    # Muñón corto de horquilla U (35 mm) con acceso Ø5.2 mm al horn + separador M3 + bayonetas
    bridge_x0 = j2_hub_r + 3.4
    bridge_x1 = bridge_x0 + 12.0
    r_ear = j2_hub_r + 1.0
    def _arm(y0):
        return _cyl_y(0.0, 0.0, r_ear, y0, y0 + FORK_THK).union(
            cq.Workplane("XZ").workplane(offset=-y0).center(bridge_x1 / 2.0, 0.0).rect(bridge_x1, 17.0).extrude(-FORK_THK)
        )
    bridge = cq.Workplane("XY").workplane(offset=-8.0).center(0.5 * (bridge_x0 + bridge_x1), 0.0).rect(bridge_x1 - bridge_x0, FORK_OUT_Y * 2.0).extrude(16.0).edges("|X").chamfer(2.2)
    stub_fork = (
        _arm(FORK_IN_Y).union(_arm(-FORK_OUT_Y)).union(bridge)
        .cut(cq.Workplane("XZ").circle(j2_hub_r + 2.5).extrude(FORK_IN_Y, both=True))
        .cut(_horn_recess_xz(FORK_IN_Y, depth=1.8, arm_len=13.5))
        .cut(_cyl_y(0.0, 0.0, (M3_SPACER_OD + 0.40) / 2.0, -FORK_OUT_Y - 1.0, -FORK_IN_Y + 1.0))
        .cut(_cyl_y(0.0, 0.0, 4.60, -FORK_OUT_Y - 0.5, -(FORK_OUT_Y - 1.45)))
        .cut(_bayonet_socket_cut_xz((0.0, 0.0), J2_CAP_DIA, +1))
        .cut(_bayonet_socket_cut_xz((0.0, 0.0), J2_CAP_DIA, -1))
    )

    cap_l, _ = _bayonet_cap_and_ring_xz((0.0, 0.0), J2_CAP_DIA, -1)
    cap_r, _ = _bayonet_cap_and_ring_xz((0.0, 0.0), J2_CAP_DIA, +1)
    spacer = _m3_pivot_spacer_xz((0.0, 0.0))

    m_hub = _seat_z0(_cq_to_trimesh(j2_test_hub, tmp), (), tx=95.0, ty=128.0)
    m_frk = _seat_z0(_cq_to_trimesh(stub_fork, tmp), [("x", +90.0)], tx=160.0, ty=128.0)
    m_cl  = _seat_z0(_cq_to_trimesh(cap_l, tmp), [("x", +90.0)], tx=95.0, ty=176.0)
    m_cr  = _seat_z0(_cq_to_trimesh(cap_r, tmp), [("x", -90.0)], tx=140.0, ty=176.0)
    m_spc = _seat_z0(_cq_to_trimesh(spacer, tmp), [("x", +90.0)], tx=175.0, ty=176.0)

    out_3mf = os.path.join(OUT_DIR, "cupon_2_articulacion_piloto_j2.3mf")
    _export_plate([
        ("hub_piloto_j2_mg90s", m_hub),
        ("horquilla_piloto_j2", m_frk),
        ("tapa_bayoneta_j2_izq", m_cl),
        ("tapa_bayoneta_j2_der", m_cr),
        ("separador_m3_j2", m_spc),
    ], out_3mf)
    print(f"[OK] Cupón 2 exportado (5 piezas @ Z=0): {out_3mf}")


def build_cupon_3():
    """Cupón 3: Pinza paralela independiente MeArm Módulo 1.5 completa orientada en Z=0 (lista para probar con SG90)."""
    q1 = float(HERO_POSE_DEG["q1"])
    wrist_ang = float(HERO_POSE_DEG["q2"] + HERO_POSE_DEG["q3"] + HERO_POSE_DEG["q4"])
    blk_dir = os.path.join(V4_DIR, "stl_negro_mate")
    wht_dir = os.path.join(V4_DIR, "stl_blanco_mate")

    specs = [
        (blk_dir, "07_palma_pinza_v4", [("z", -q1), ("y", +wrist_ang)], 92.0, 128.0),
        (blk_dir, "08_engrane_brazo_izq_m15", [("z", -q1), ("y", +wrist_ang), ("x", 180.0)], 148.0, 148.0),
        (blk_dir, "09_engrane_brazo_der_m15", [("z", -q1), ("y", +wrist_ang)], 148.0, 108.0),
        (blk_dir, "10_dedo_pinza_izq_v4", [("z", -q1), ("y", +wrist_ang), ("x", 180.0)], 190.0, 150.0),
        (blk_dir, "10_dedo_pinza_der_v4", [("z", -q1), ("y", +wrist_ang), ("x", 180.0)], 190.0, 108.0),
        (blk_dir, "12_biela_pinza_izq_v4", [("z", -q1), ("y", +wrist_ang)], 148.0, 74.0),
        (blk_dir, "12_biela_pinza_der_v4", [("z", -q1), ("y", +wrist_ang)], 182.0, 74.0),
        (wht_dir, "w04_almohadilla_izq", [("z", -q1), ("y", +wrist_ang), ("x", 90.0)], 92.0, 74.0),
        (wht_dir, "w04_almohadilla_der", [("z", -q1), ("y", +wrist_ang), ("x", 90.0)], 116.0, 74.0),
    ]
    placed = []
    for folder, name, rots, tx, ty in specs:
        m = trimesh.load(os.path.join(folder, f"{name}.stl"), force="mesh")
        placed.append((name, _seat_z0(m, rots, tx=tx, ty=ty)))

    out_3mf = os.path.join(OUT_DIR, "cupon_3_pinza_independiente_mearm15.3mf")
    _export_plate(placed, out_3mf)
    print(f"[OK] Cupón 3 exportado (9 piezas pinza @ Z=0): {out_3mf}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    build_cupon_1()
    build_cupon_2()
    build_cupon_3()
    print(f"[EXITO] Kit progresivo de prototipado v4 listo en: {OUT_DIR}")
