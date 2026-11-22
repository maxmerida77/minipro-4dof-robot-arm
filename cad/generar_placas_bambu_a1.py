"""
Iteración 3 — Generador de Placas Planas Z=0 para Bambu Lab A1 Combo (`256 × 256 mm`)
=====================================================================================
Orienta analíticamente las 35 piezas estancas del CAD v3.1 (`23 Negro Mate` + `12 Blanco Mate`)
en su cara óptima de impresión (máxima área de contacto PEI, fibra continua, cero soportes en
cavidades de servo y bolsillos de horn, 0% purga AMS) y las divide estratégicamente en 3 placas
profesionales para Bambu Studio:

  1. `placa_1a_negro_estructura_020mm.3mf` — 6 piezas estructurales (~198 g, capa 0.20 mm, 4 paredes,
     25% Gyroid, amplio espacio entre piezas para Soporte Árbol solo en cama en 5/6 piezas).
  2. `placa_1b_negro_precision_012mm.3mf`  — 17 piezas de precisión (~16 g, capa 0.12 mm Fine,
     0 / 17 SOPORTES: engranes 22T/14T, bielas 4 barras, dedos paralelos, bujes 608ZZ y 6 tapas).
  3. `placa_2_blanco_mate_016mm.3mf`       — 12 piezas Blanco Mate (~3.6 g, capa 0.16 mm,
     0 / 12 SOPORTES, 0% purga AMS: aros Stealth, collar muñeca y almohadillas).

También exporta respaldos `.stl` por placa, los 35 `.stl` individuales ya orientados en `Z = 0`,
`manifiesto_placas_bambu_a1.json` y el tablero visual `docs/renders/placas_impresion_bambu_a1.png`.
"""

import json
import math
import os
import sys
import numpy as np
import trimesh
import vtk
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from params import HERO_POSE_DEG

BLK_IN = os.path.join(HERE, "exports", "stl_negro_mate")
WHT_IN = os.path.join(HERE, "exports", "stl_blanco_mate")
OUT_DIR = os.path.join(HERE, "exports", "placas_bambu_a1")
OUT_BLK_IND = os.path.join(OUT_DIR, "stl_orientados_negro")
OUT_WHT_IND = os.path.join(OUT_DIR, "stl_orientados_blanco")
RENDER_OUT = os.path.join(ROOT, "docs", "renders", "placas_impresion_bambu_a1.png")

BED_W = 256.0
BED_D = 256.0
MARGIN = 12.0       # Zona segura libre de línea de purga y bordes PEI
PLA_DENSITY = 1.24  # g/cm³ (PLA Mate Bambu)
INFILL_EFF = 0.56   # Factor masa efectivo (~4 paredes + 25% Gyroid)

Q1 = float(HERO_POSE_DEG["q1"])
Q2 = float(HERO_POSE_DEG["q2"])
Q3 = float(HERO_POSE_DEG["q3"])
Q4 = float(HERO_POSE_DEG["q4"])
WRIST_ANG = Q2 + Q3 + Q4


def _rot_matrix(axis, deg):
    axes = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
    return trimesh.transformations.rotation_matrix(math.radians(deg), axes[axis])


def _orient_mesh(mesh: trimesh.Trimesh, rotations):
    m = mesh.copy()
    c = m.bounds.mean(axis=0)
    m.apply_translation(-c)
    for ax, deg in rotations:
        if abs(deg) > 1e-6:
            m.apply_transform(_rot_matrix(ax, deg))
    bmin, bmax = m.bounds
    cx = 0.5 * (bmin[0] + bmax[0])
    cy = 0.5 * (bmin[1] + bmax[1])
    m.apply_translation([-cx, -cy, -bmin[2]])
    return m


def _contact_area_mm2(mesh: trimesh.Trimesh, z_tol=0.25) -> float:
    tri_z = mesh.triangles[:, :, 2]
    on_bed = np.all(tri_z <= z_tol, axis=1)
    down = mesh.face_normals[:, 2] < -0.85
    return float(mesh.area_faces[on_bed & down].sum())


def _est_grams(mesh: trimesh.Trimesh) -> float:
    vol_cm3 = abs(float(mesh.volume)) / 1000.0
    h_min = float(min(mesh.bounding_box.extents))
    eff = 0.92 if h_min <= 4.5 else INFILL_EFF
    return vol_cm3 * PLA_DENSITY * eff


# ============================================================================
# REGLAS ANALÍTICAS DE ORIENTACIÓN ÓPTIMA POR PLACA (VERIFICADAS POR APOYO PEI)
# ============================================================================
BLACK_STRUCT_SPECS = {
    "01_base_fija_hueca": (
        [("x", 180.0)],
        "Árbol (solo cama)",
        "Boca abajo: techo Ø91 mm (5965 mm² en PEI) y asiento 608ZZ planos; insertos AR2811 hacia arriba",
    ),
    "04_torreta_j1_hombro": (
        [("z", -Q1)],
        "Árbol (solo cama) + Brim 5 mm",
        "Vertical: eje con corte en D circular y concéntrico; soporte árbol solo bajo corona y tambor J2",
    ),
    "03_tapa_inferior_electronica": (
        [],
        "Ninguno",
        "Cara plana inferior en PEI (5495 mm²); postes PCA9685 y cuna XIAO suben sin soportes",
    ),
    "05_eslabon_l2_codo": (
        [("z", -Q1), ("y", +Q2), ("x", +90.0)],
        "Árbol (solo cama)",
        "Sobre cara -Y (312 mm²): fibra continua, bahía MG90S J3 y bolsillo horn hacia arriba (0 soporte interno)",
    ),
    "06_antebrazo_l3_muneca": (
        [("z", -Q1), ("y", +(Q2 + Q3)), ("x", +90.0)],
        "Árbol (solo cama)",
        "Sobre cara -Y (235 mm²): fibra continua, bahía MG90S J4 y bolsillo horn hacia arriba (0 soporte interno)",
    ),
    "07_palma_pinza_sg90": (
        [("z", -Q1), ("y", +WRIST_ANG)],
        "Árbol (solo cama)",
        "Sobre base plana del carenado SG90 (174 mm² en PEI): cavidad SG90 vertical limpia y pivotes M3 circulares",
    ),
}

BLACK_PREC_SPECS = {
    "02_pinon_base_22t": (
        [("x", 180.0)],
        "Ninguno",
        "Boca abajo: dientes 22T continuos en XY y bolsillo horn MG90S hacia arriba",
    ),
    "04b_engrane_torreta_22t": (
        [("z", -Q1)],
        "Ninguno",
        "Plano en XY: dientes 22T y chaveta en D con precisión 0.12 mm",
    ),
    "08_engrane_brazo_izq": (
        [("z", -Q1), ("y", +WRIST_ANG), ("x", 180.0)],
        "Ninguno",
        "Boca abajo: dientes 14T continuos y bolsillo horn SG90 hacia arriba",
    ),
    "09_engrane_brazo_der": (
        [("z", -Q1), ("y", +WRIST_ANG)],
        "Ninguno",
        "Plano en XY: dientes 14T y brazo en fibra continua",
    ),
    "10_dedo_pinza_izq": (
        [("z", -Q1), ("y", +WRIST_ANG), ("x", 180.0)],
        "Ninguno",
        "Boca abajo: puente doble pivote + cuello + mordaza 100% coplanares en PEI (0 soportes)",
    ),
    "10_dedo_pinza_der": (
        [("z", -Q1), ("y", +WRIST_ANG), ("x", 180.0)],
        "Ninguno",
        "Boca abajo: puente doble pivote + cuello + mordaza 100% coplanares en PEI (0 soportes)",
    ),
    "12_biela_pinza_izq": (
        [("z", -Q1), ("y", +WRIST_ANG)],
        "Ninguno",
        "Plana en XY: máxima resistencia entre pivotes M3 (L=16 mm)",
    ),
    "12_biela_pinza_der": (
        [("z", -Q1), ("y", +WRIST_ANG)],
        "Ninguno",
        "Plana en XY: máxima resistencia entre pivotes M3 (L=16 mm)",
    ),
    "11_buje_608zz_j2": (
        [("z", -Q1), ("x", +90.0)],
        "Ninguno (Brim 3 mm opc.)",
        "Vertical sobre pestaña Ø11.6 mm: manguito Ø7.86 y barreno M3 circulares",
    ),
    "11_buje_608zz_j3": (
        [("z", -Q1), ("x", +90.0)],
        "Ninguno (Brim 3 mm opc.)",
        "Vertical sobre pestaña Ø11.6 mm: manguito Ø7.86 y barreno M3 circulares",
    ),
    "11_buje_608zz_j4": (
        [("z", -Q1), ("x", +90.0)],
        "Ninguno (Brim 3 mm opc.)",
        "Vertical sobre pestaña Ø11.6 mm: manguito Ø7.86 y barreno M3 circulares",
    ),
    "tapa_j2_izq": (
        [("z", -Q1), ("x", +90.0)],
        "Ninguno",
        "Cara exterior Stealth hacia PEI (textura mate uniforme), ceja centradora hacia arriba",
    ),
    "tapa_j2_der": (
        [("z", -Q1), ("x", -90.0)],
        "Ninguno",
        "Cara exterior Stealth hacia PEI (textura mate uniforme), ceja centradora hacia arriba",
    ),
    "tapa_j3_izq": (
        [("z", -Q1), ("x", +90.0)],
        "Ninguno",
        "Cara exterior Stealth hacia PEI (textura mate uniforme), ceja centradora hacia arriba",
    ),
    "tapa_j3_der": (
        [("z", -Q1), ("x", -90.0)],
        "Ninguno",
        "Cara exterior Stealth hacia PEI (textura mate uniforme), ceja centradora hacia arriba",
    ),
    "tapa_j4_izq": (
        [("z", -Q1), ("x", +90.0)],
        "Ninguno",
        "Cara exterior Stealth hacia PEI (textura mate uniforme), ceja centradora hacia arriba",
    ),
    "tapa_j4_der": (
        [("z", -Q1), ("x", -90.0)],
        "Ninguno",
        "Cara exterior Stealth hacia PEI (textura mate uniforme), ceja centradora hacia arriba",
    ),
}

WHITE_SPECS = {
    "w01_aro_base_blanco": ([], "Ninguno", "Aro plano Ø94.3 mm en PEI (0 soportes, 0% purga AMS)"),
    "w02_collar_muneca_blanco": ([("z", -Q1), ("y", +WRIST_ANG), ("y", 90.0)], "Ninguno", "Collar plano Ø24.8 × 2.0 mm en PEI"),
    "w03_aro_engrane_0": ([("z", -Q1), ("y", +WRIST_ANG)], "Ninguno", "Micro-aro plano 0.6 mm en PEI"),
    "w03_aro_engrane_1": ([("z", -Q1), ("y", +WRIST_ANG)], "Ninguno", "Micro-aro plano 0.6 mm en PEI"),
    "w04_almohadilla_izq": ([("z", -Q1), ("y", +WRIST_ANG), ("x", 90.0)], "Ninguno", "Almohadilla plana 14.4 × 9.6 × 1.6 mm en PEI"),
    "w04_almohadilla_der": ([("z", -Q1), ("y", +WRIST_ANG), ("x", 90.0)], "Ninguno", "Almohadilla plana 14.4 × 9.6 × 1.6 mm en PEI"),
    "w_aro_j2_izq": ([("z", -Q1), ("x", 90.0)], "Ninguno", "Aro decorativo plano Ø32 × 1.8 mm en PEI"),
    "w_aro_j2_der": ([("z", -Q1), ("x", 90.0)], "Ninguno", "Aro decorativo plano Ø32 × 1.8 mm en PEI"),
    "w_aro_j3_izq": ([("z", -Q1), ("x", 90.0)], "Ninguno", "Aro decorativo plano Ø29 × 1.8 mm en PEI"),
    "w_aro_j3_der": ([("z", -Q1), ("x", 90.0)], "Ninguno", "Aro decorativo plano Ø29 × 1.8 mm en PEI"),
    "w_aro_j4_izq": ([("z", -Q1), ("x", 90.0)], "Ninguno", "Aro decorativo plano Ø24 × 1.8 mm en PEI"),
    "w_aro_j4_der": ([("z", -Q1), ("x", 90.0)], "Ninguno", "Aro decorativo plano Ø24 × 1.8 mm en PEI"),
}


# ============================================================================
# EMPAQUETADOR 2D MAXRECTS CENTRADO EN CAMA 256×256 mm + AUDITORÍA CERO TRASLAPE
# ============================================================================
def pack_on_plate(items, bed_w=BED_W, bed_d=BED_D, margin=MARGIN, gap=10.0):
    usable_w = bed_w - 2.0 * margin
    usable_d = bed_d - 2.0 * margin

    ordered = sorted(
        items,
        key=lambda it: (it["ext"][0] * it["ext"][1], max(it["ext"][0], it["ext"][1])),
        reverse=True,
    )

    free_rects = [(0.0, 0.0, usable_w + gap, usable_d + gap)]
    placed = []

    for it in ordered:
        w0, h0 = float(it["ext"][0]), float(it["ext"][1])
        best = None
        for rot_z in (0.0, 90.0):
            pw, ph = (w0, h0) if rot_z == 0.0 else (h0, w0)
            req_w, req_h = pw + gap, ph + gap
            for fr in free_rects:
                fx, fy, fw, fh = fr
                if req_w <= fw + 1e-6 and req_h <= fh + 1e-6:
                    short_side = min(fw - req_w, fh - req_h)
                    area_waste = fw * fh - req_w * req_h
                    score = (short_side, area_waste, fy, fx)
                    if best is None or score < best[0]:
                        best = (score, fx, fy, pw, ph, rot_z)
        if best is None:
            raise RuntimeError(f"No cupo '{it['name']}' ({w0:.1f}x{h0:.1f} mm) con gap={gap} mm!")

        _, px, py, pw, ph, rot_z = best
        ox, oy, ow, oh = px, py, pw + gap, ph + gap

        new_free = []
        for fx, fy, fw, fh in free_rects:
            if ox >= fx + fw - 1e-6 or ox + ow <= fx + 1e-6 or oy >= fy + fh - 1e-6 or oy + oh <= fy + 1e-6:
                new_free.append((fx, fy, fw, fh))
                continue
            if ox > fx + 1e-6:
                new_free.append((fx, fy, ox - fx, fh))
            if ox + ow < fx + fw - 1e-6:
                new_free.append((ox + ow, fy, (fx + fw) - (ox + ow), fh))
            if oy > fy + 1e-6:
                new_free.append((fx, fy, fw, oy - fy))
            if oy + oh < fy + fh - 1e-6:
                new_free.append((fx, oy + oh, fw, (fy + fh) - (oy + oh)))

        pruned = []
        for i, a in enumerate(new_free):
            contained = any(
                i != j
                and a[0] >= b[0] - 1e-6
                and a[1] >= b[1] - 1e-6
                and a[0] + a[2] <= b[0] + b[2] + 1e-6
                and a[1] + a[3] <= b[1] + b[3] + 1e-6
                for j, b in enumerate(new_free)
            )
            if not contained and a[2] > 1.0 and a[3] > 1.0:
                pruned.append(a)
        free_rects = pruned

        m = it["mesh"].copy()
        if abs(rot_z) > 1e-6:
            m.apply_transform(_rot_matrix("z", rot_z))
            bmin, bmax = m.bounds
            m.apply_translation([-0.5 * (bmin[0] + bmax[0]), -0.5 * (bmin[1] + bmax[1]), -bmin[2]])

        placed.append({
            **it,
            "mesh": m,
            "rot_z_pack": rot_z,
            "local_box": (px, py, pw, ph),
            "cx_local": px + pw / 2.0,
            "cy_local": py + ph / 2.0,
        })

    # Centrar en el centro térmico exacto de la cama (128, 128 mm)
    min_x = min(p["local_box"][0] for p in placed)
    max_x = max(p["local_box"][0] + p["local_box"][2] for p in placed)
    min_y = min(p["local_box"][1] for p in placed)
    max_y = max(p["local_box"][1] + p["local_box"][3] for p in placed)
    shift_x = (bed_w - (max_x - min_x)) / 2.0 - min_x
    shift_y = (bed_d - (max_y - min_y)) / 2.0 - min_y

    for p in placed:
        cx = p["cx_local"] + shift_x
        cy = p["cy_local"] + shift_y
        p["mesh"].apply_translation([cx, cy, 0.0])
        bmin, bmax = p["mesh"].bounds
        p["bounds_xy"] = (float(bmin[0]), float(bmin[1]), float(bmax[0]), float(bmax[1]))
        p["z_min"] = float(bmin[2])
        p["z_max"] = float(bmax[2])
        p["bed_cx"] = float(cx)
        p["bed_cy"] = float(cy)

    # Auditoría matemática: 0 traslapes, dentro de [margin, 256-margin], Z_min == 0.000
    min_pair_gap = 1e9
    for i in range(len(placed)):
        ax0, ay0, ax1, ay1 = placed[i]["bounds_xy"]
        assert ax0 >= margin - 0.5 and ax1 <= bed_w - margin + 0.5, f"Fuera de X: {placed[i]['name']}"
        assert ay0 >= margin - 0.5 and ay1 <= bed_d - margin + 0.5, f"Fuera de Y: {placed[i]['name']}"
        assert abs(placed[i]["z_min"]) < 1e-4, f"No apoyado en Z=0: {placed[i]['name']} ({placed[i]['z_min']})"
        for j in range(i + 1, len(placed)):
            bx0, by0, bx1, by1 = placed[j]["bounds_xy"]
            dx = max(0.0, max(bx0 - ax1, ax0 - bx1))
            dy = max(0.0, max(by0 - ay1, ay0 - by1))
            g = math.hypot(dx, dy)
            if dx == 0.0 and dy == 0.0:
                raise AssertionError(f"TRASLAPE entre {placed[i]['name']} y {placed[j]['name']}!")
            min_pair_gap = min(min_pair_gap, g)

    return placed, min_pair_gap


def build_and_export_plate(plate_name, in_dir, ind_out_dir, specs, out_3mf, out_stl, gap=10.0, layer_mm=0.20):
    os.makedirs(ind_out_dir, exist_ok=True)
    items = []
    for name, (rots, support, note) in specs.items():
        src = os.path.join(in_dir, f"{name}.stl")
        if not os.path.exists(src):
            raise FileNotFoundError(f"Falta STL fuente: {src}")
        raw = trimesh.load(src, force="mesh")
        oriented = _orient_mesh(raw, rots)
        assert oriented.is_watertight, f"Pieza no estanca tras orientar: {name}"
        if name in ("05_eslabon_l2_codo", "06_antebrazo_l3_muneca"):
            hz = float(oriented.bounding_box.extents[2])
            assert abs(hz - 48.0) < 0.5, f"{name} Z={hz:.2f} mm != 48.0 mm!"

        oriented.export(os.path.join(ind_out_dir, f"{name}.stl"))
        items.append({
            "name": name,
            "mesh": oriented,
            "ext": [float(v) for v in oriented.bounding_box.extents],
            "grams": round(_est_grams(oriented), 2),
            "contact_mm2": round(_contact_area_mm2(oriented), 1),
            "support": support,
            "note": note,
        })

    placed, min_gap = pack_on_plate(items, gap=gap)

    scene = trimesh.Scene()
    for p in placed:
        scene.add_geometry(p["mesh"], node_name=p["name"], geom_name=p["name"])
    with open(out_3mf, "wb") as f:
        f.write(scene.export(file_type="3mf"))

    combined = trimesh.util.concatenate([p["mesh"] for p in placed])
    combined.export(out_stl)

    total_g = sum(p["grams"] for p in placed)
    max_z = max(p["z_max"] for p in placed)
    n_sup = sum(1 for p in placed if p["support"].startswith("Árbol"))
    print(f"\n=== {plate_name} ({len(placed)} piezas · capa {layer_mm:.2f} mm) ===")
    print(f"  3MF Bambu Studio : {out_3mf}")
    print(f"  Masa estimada    : {total_g:.1f} g | Z máx = {max_z:.1f} mm | Gap mín = {min_gap:.2f} mm")
    print(f"  Sin soporte      : {len(placed) - n_sup} / {len(placed)} (con Árbol solo cama: {n_sup})")
    for idx, p in enumerate(placed, 1):
        ex = p["mesh"].bounding_box.extents
        print(
            f"  [{idx:02d}] {p['name']:32s} | {ex[0]:5.1f}×{ex[1]:5.1f}×{ex[2]:4.1f} mm | "
            f"Z0={p['z_min']:+.3f} | Apoyo={p['contact_mm2']:6.0f} mm² | {p['grams']:4.1f}g | {p['support']}"
        )
    return placed, {
        "layer_mm": layer_mm,
        "count": len(placed),
        "total_g": round(total_g, 1),
        "max_z_mm": round(max_z, 1),
        "min_gap_mm": round(min_gap, 2),
        "n_supports": n_sup,
    }


# ============================================================================
# RENDER VTK 3×2 DE LAS 3 PLACAS SOBRE CAMA BAMBU LAB A1 (256×256 mm)
# ============================================================================
def _trimesh_to_vtk_actor(mesh: trimesh.Trimesh, color, specular=0.18):
    pts = vtk.vtkPoints()
    for v in mesh.vertices:
        pts.InsertNextPoint(float(v[0]), float(v[1]), float(v[2]))
    cells = vtk.vtkCellArray()
    for f in mesh.faces:
        cells.InsertNextCell(3)
        cells.InsertCellPoint(int(f[0]))
        cells.InsertCellPoint(int(f[1]))
        cells.InsertCellPoint(int(f[2]))
    poly = vtk.vtkPolyData()
    poly.SetPoints(pts)
    poly.SetPolys(cells)
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputData(poly)
    nrm.SetFeatureAngle(35.0)
    nrm.SplittingOn()
    nrm.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(nrm.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*color)
    prop.SetDiffuse(0.84)
    prop.SetSpecular(specular)
    prop.SetSpecularPower(22.0)
    prop.SetAmbient(0.18)
    return actor


def _add_bed_plate(ren, is_white_parts=False):
    bed = vtk.vtkCubeSource()
    bed.SetBounds(0.0, BED_W, 0.0, BED_D, -2.5, -0.05)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(bed.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*(0.16, 0.17, 0.21) if is_white_parts else (0.78, 0.80, 0.83))
    a.GetProperty().SetAmbient(0.32)
    a.GetProperty().SetDiffuse(0.75)
    ren.AddActor(a)

    pts = vtk.vtkPoints()
    lines = vtk.vtkCellArray()
    idx = 0
    for v in range(0, 257, 16):
        pts.InsertNextPoint(float(v), 0.0, 0.02)
        pts.InsertNextPoint(float(v), BED_D, 0.02)
        lines.InsertNextCell(2)
        lines.InsertCellPoint(idx)
        lines.InsertCellPoint(idx + 1)
        idx += 2
        pts.InsertNextPoint(0.0, float(v), 0.02)
        pts.InsertNextPoint(BED_W, float(v), 0.02)
        lines.InsertNextCell(2)
        lines.InsertCellPoint(idx)
        lines.InsertCellPoint(idx + 1)
        idx += 2
    gpoly = vtk.vtkPolyData()
    gpoly.SetPoints(pts)
    gpoly.SetLines(lines)
    gm = vtk.vtkPolyDataMapper()
    gm.SetInputData(gpoly)
    ga = vtk.vtkActor()
    ga.SetMapper(gm)
    ga.GetProperty().SetColor(*(0.30, 0.33, 0.38) if is_white_parts else (0.64, 0.67, 0.71))
    ga.GetProperty().SetLineWidth(1.0)
    ren.AddActor(ga)

    # Borde naranja de margen de seguridad (12 mm)
    spts = vtk.vtkPoints()
    slines = vtk.vtkCellArray()
    for x, y in [(MARGIN, MARGIN), (BED_W - MARGIN, MARGIN), (BED_W - MARGIN, BED_D - MARGIN), (MARGIN, BED_D - MARGIN)]:
        spts.InsertNextPoint(x, y, 0.06)
    slines.InsertNextCell(5)
    for k in (0, 1, 2, 3, 0):
        slines.InsertCellPoint(k)
    spoly = vtk.vtkPolyData()
    spoly.SetPoints(spts)
    spoly.SetLines(slines)
    sm = vtk.vtkPolyDataMapper()
    sm.SetInputData(spoly)
    sa = vtk.vtkActor()
    sa.SetMapper(sm)
    sa.GetProperty().SetColor(0.92, 0.42, 0.12)
    sa.GetProperty().SetLineWidth(1.6)
    ren.AddActor(sa)


def _render_plate_view(placed, is_white_parts, mode="top", size=(760, 620)):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.95, 0.96, 0.97)
    _add_bed_plate(ren, is_white_parts=is_white_parts)

    for p in placed:
        if is_white_parts:
            col = (0.96, 0.97, 0.98)
        else:
            col = (0.14, 0.15, 0.17) if not p["support"].startswith("Árbol") else (0.20, 0.24, 0.30)
        ren.AddActor(_trimesh_to_vtk_actor(p["mesh"], col))

    for pos, inten in [((380, -240, 460), 0.95), ((-260, 340, 320), 0.55), ((128, 128, 520), 0.40)]:
        l = vtk.vtkLight()
        l.SetPosition(*pos)
        l.SetFocalPoint(128, 128, 12)
        l.SetIntensity(inten)
        ren.AddLight(l)

    cam = ren.GetActiveCamera()
    if mode == "top":
        cam.ParallelProjectionOn()
        cam.SetFocalPoint(128.0, 128.0, 0.0)
        cam.SetPosition(128.0, 128.0, 480.0)
        cam.SetViewUp(0.0, 1.0, 0.0)
        cam.SetParallelScale(142.0)
    else:
        cam.SetFocalPoint(128.0, 128.0, 16.0)
        cam.SetPosition(365.0, -145.0, 235.0)
        cam.SetViewUp(0.0, 0.0, 1.0)
        cam.SetViewAngle(32.0)
    ren.ResetCameraClippingRange()

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(*size)
    win.SetMultiSamples(4)
    win.Render()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    vimg = w2i.GetOutput()
    dims = vimg.GetDimensions()
    arr = np.frombuffer(vimg.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], -1)
    arr = np.flipud(arr)
    img = Image.fromarray(arr[:, :, :3])

    if mode == "top":
        draw = ImageDraw.Draw(img)
        try:
            f_num = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 13)
        except Exception:
            f_num = ImageFont.load_default()
        coord = vtk.vtkCoordinate()
        coord.SetCoordinateSystemToWorld()
        for idx, p in enumerate(placed, 1):
            coord.SetValue(p["bed_cx"], p["bed_cy"], p["z_max"] + 1.0)
            dx, dy = coord.GetComputedDisplayValue(ren)
            px, py = int(dx), int(size[1] - dy)
            r = 11
            bg = (234, 88, 12) if p["support"].startswith("Árbol") else (15, 23, 42)
            draw.ellipse([px - r, py - r, px + r, py + r], fill=bg, outline=(255, 255, 255), width=2)
            txt = f"{idx}"
            tw = draw.textlength(txt, font=f_num)
            draw.text((px - tw / 2, py - 8.5), txt, fill=(255, 255, 255), font=f_num)

    return img


def compose_board(p1a, s1a, p1b, s1b, p2, s2):
    tile_w, tile_h = 740, 560
    imgs = [
        (_render_plate_view(p1a, False, "top", (tile_w, tile_h)),
         _render_plate_view(p1a, False, "iso", (tile_w, tile_h)),
         f"PLACA 1A — NEGRO MATE ESTRUCTURA (6 PIEZAS · {s1a['total_g']:.1f} g · Capa 0.20 mm · 4 paredes · 25% Gyroid)",
         f"Naranja = 5 pzas con Soporte Árbol solo cama · Negro = 03_tapa SIN soporte · Gap mín: {s1a['min_gap_mm']:.1f} mm · Z máx: {s1a['max_z_mm']:.1f} mm"),
        (_render_plate_view(p1b, False, "top", (tile_w, tile_h)),
         _render_plate_view(p1b, False, "iso", (tile_w, tile_h)),
         f"PLACA 1B — NEGRO MATE PRECISIÓN (17 PIEZAS · {s1b['total_g']:.1f} g · Capa 0.12 mm Fine · 0 / 17 SOPORTES)",
         f"Engranes 22T/14T, dedos 4 barras boca abajo, bielas, bujes 608ZZ y 6 tapas Stealth · Gap mín: {s1b['min_gap_mm']:.1f} mm · Z máx: {s1b['max_z_mm']:.1f} mm"),
        (_render_plate_view(p2, True, "top", (tile_w, tile_h)),
         _render_plate_view(p2, True, "iso", (tile_w, tile_h)),
         f"PLACA 2 — BLANCO MATE DETALLES STEALTH (12 PIEZAS · {s2['total_g']:.1f} g · Capa 0.16 mm · 0 / 12 SOPORTES · 0% PURGA AMS)",
         f"Aro base Ø94 mm, 6 aros J2/J3/J4, collar muñeca, 2 aros engrane y 2 almohadillas · Gap mín: {s2['min_gap_mm']:.1f} mm · Z máx: {s2['max_z_mm']:.1f} mm"),
    ]

    pad = 24
    header_h = 98
    row_cap_h = 58
    W = tile_w * 2 + pad * 3
    H = header_h + len(imgs) * (tile_h + row_cap_h + pad) + pad

    board = Image.new("RGB", (W, H), (244, 246, 249))
    draw = ImageDraw.Draw(board)
    try:
        f_h1 = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 27)
        f_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
        f_t = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 17.5)
        f_s = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 14.5)
    except Exception:
        f_h1 = f_sub = f_t = f_s = ImageFont.load_default()

    draw.rectangle([0, 0, W, header_h], fill=(15, 23, 42))
    draw.text((pad, 18), "ITERACIÓN 3 — 3 PLACAS PLANAS Z=0 PARA BAMBU LAB A1 COMBO (256 × 256 mm)",
              fill=(248, 250, 252), font=f_h1)
    tot_g = s1a["total_g"] + s1b["total_g"] + s2["total_g"]
    draw.text(
        (pad, 58),
        f"35 / 35 piezas estancas · 30 / 35 sin soporte (86%) · 0% Purga AMS · Total estimado: {tot_g:.1f} g PLA "
        f"(Negro {s1a['total_g'] + s1b['total_g']:.1f} g + Blanco {s2['total_g']:.1f} g) · Archivos .3mf listos para Bambu Studio",
        fill=(148, 163, 184), font=f_sub,
    )

    for r_idx, (im_top, im_iso, title, sub) in enumerate(imgs):
        y0 = header_h + pad + r_idx * (tile_h + row_cap_h + pad)
        draw.rounded_rectangle([pad - 2, y0 - 2, W - pad + 2, y0 + tile_h + row_cap_h + 2],
                               radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        board.paste(im_top, (pad, y0))
        board.paste(im_iso, (pad * 2 + tile_w, y0))
        draw.text((pad + 14, y0 + tile_h + 8), title, fill=(15, 23, 42), font=f_t)
        draw.text((pad + 14, y0 + tile_h + 33), sub, fill=(71, 85, 105), font=f_s)

    os.makedirs(os.path.dirname(RENDER_OUT), exist_ok=True)
    board.save(RENDER_OUT)
    print(f"\n[OK] Tablero visual de 3 placas guardado: {RENDER_OUT}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    p1a, s1a = build_and_export_plate(
        "PLACA 1A — NEGRO MATE (ESTRUCTURA)",
        BLK_IN,
        OUT_BLK_IND,
        BLACK_STRUCT_SPECS,
        os.path.join(OUT_DIR, "placa_1a_negro_estructura_020mm.3mf"),
        os.path.join(OUT_DIR, "placa_1a_negro_estructura_020mm.stl"),
        gap=9.0,
        layer_mm=0.20,
    )
    p1b, s1b = build_and_export_plate(
        "PLACA 1B — NEGRO MATE (PRECISIÓN · 0 SOPORTES)",
        BLK_IN,
        OUT_BLK_IND,
        BLACK_PREC_SPECS,
        os.path.join(OUT_DIR, "placa_1b_negro_precision_012mm.3mf"),
        os.path.join(OUT_DIR, "placa_1b_negro_precision_012mm.stl"),
        gap=10.0,
        layer_mm=0.12,
    )
    p2, s2 = build_and_export_plate(
        "PLACA 2 — BLANCO MATE (DETALLES STEALTH · 0% PURGA AMS)",
        WHT_IN,
        OUT_WHT_IND,
        WHITE_SPECS,
        os.path.join(OUT_DIR, "placa_2_blanco_mate_016mm.3mf"),
        os.path.join(OUT_DIR, "placa_2_blanco_mate_016mm.stl"),
        gap=10.0,
        layer_mm=0.16,
    )

    def _ser_parts(placed):
        return [
            {
                "id": i,
                "name": p["name"],
                "ext_mm": [round(float(v), 2) for v in p["mesh"].bounding_box.extents],
                "bed_xy_mm": [round(p["bed_cx"], 1), round(p["bed_cy"], 1)],
                "z_min_mm": round(p["z_min"], 4),
                "contact_area_mm2": p["contact_mm2"],
                "grams_est": p["grams"],
                "support": p["support"],
                "note": p["note"],
            }
            for i, p in enumerate(placed, 1)
        ]

    manifest = {
        "printer": "Bambu Lab A1 Combo",
        "bed_mm": [BED_W, BED_D],
        "margin_mm": MARGIN,
        "placa_1a_negro_estructura": {"stats": s1a, "parts": _ser_parts(p1a)},
        "placa_1b_negro_precision": {"stats": s1b, "parts": _ser_parts(p1b)},
        "placa_2_blanco_mate": {"stats": s2, "parts": _ser_parts(p2)},
    }
    man_path = os.path.join(OUT_DIR, "manifiesto_placas_bambu_a1.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"[OK] Manifiesto guardado: {man_path}")

    compose_board(p1a, s1a, p1b, s1b, p2, s2)
