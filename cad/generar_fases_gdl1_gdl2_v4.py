"""
Generador de Guías Visuales y Placas `.3mf` por Grado de Libertad (GDL 1 y GDL 2)
=================================================================================
Reutiliza al 100% los STLs verificados y aprobados (`GO` Ronda 4) de `CAD v4 Clean-DFA`
sin alterar ninguna geometría ni tolerancia, empaquetando placas `.3mf` dedicadas para
construir y probar el brazo de forma incremental:
  - FASE 1 — GDL 1 (`J1 · Base Yaw Coaxial`): 6 piezas imprimibles + electrónica completa + lastre
  - FASE 2 — GDL 2 (`J2 · Hombro Pitch + Brazo L2`): 7 piezas adicionales imprimibles + MG90S J2

Salidas:
  - `cad/exports/v4_clean_dfa/placas_por_grado/*.3mf` (6 placas listas para Bambu Studio en Z=0)
  - `docs/renders/fase1_gdl1_base_j1.png`  (Tablero 3 paneles: Ensamble + Rayos-X/Explosión + Piezas GDL 1)
  - `docs/renders/fase2_gdl2_hombro_j2.png` (Tablero 3 paneles: GDL 1+2 + Explosión Pivote J2 + Piezas GDL 2)
"""

import json
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

from generar_placas_bambu_a1_v4 import pack_on_plate, _est_grams, _contact_area_mm2, BED_W, BED_D

EXP = os.path.join(HERE, "exports", "v4_clean_dfa")
BLK_DIR = os.path.join(EXP, "stl_negro_mate")
WHT_DIR = os.path.join(EXP, "stl_blanco_mate")
HW_DIR = os.path.join(EXP, "hardware_ref")
ORI_BLK = os.path.join(EXP, "placas_bambu_a1", "stl_orientados_negro")
ORI_WHT = os.path.join(EXP, "placas_bambu_a1", "stl_orientados_blanco")
OUT_3MF_DIR = os.path.join(EXP, "placas_por_grado")
OUT_REND_DIR = os.path.join(ROOT, "docs", "renders")

# Definición exacta de piezas por grado de libertad (sin alterar ningún STL v4)
GDL1_PRINT = [
    # (nombre_base, color, capa, soporte, nota)
    ("01_base_fija_v4", "negro", "0.20 mm", "Árbol (solo cama)", "Carcasa base Ø106, pista Ø88, cuna MG90S J1"),
    ("04_torreta_j1_hombro_v4", "negro", "0.20 mm", "Árbol + Brim 5 mm", "Torreta giratoria J1 + hub J2 (mamparo 1.2 mm)"),
    ("03_tapa_inferior_v4", "negro", "0.12 mm", "Ninguno", "Tapa inferior + bóveda 6 pilas lastre + 6 patas"),
    ("03b_bandeja_electronica_v4", "negro", "0.12 mm", "Ninguno", "Bandeja aislante plana + postes ciegos PCA M3×4"),
    ("04b_reten_axial_j1", "negro", "0.12 mm", "Ninguno", "Retén axial J1 boca abajo (3 avellanados M3×8)"),
    ("w01_aro_base_blanco", "blanco", "0.16 mm", "Ninguno", "Aro estético blanco Ø106 (0% purga AMS)"),
]

GDL2_PRINT = [
    ("05_eslabon_l2_v4", "negro", "0.20 mm", "Árbol (solo cama)", "Brazo L2 horquilla U monolítica (1 sólido, a2=82)"),
    ("11_separador_m3_j2", "negro", "0.12 mm", "Ninguno", "Casquillo liso Ø5.0 (Nyloc nunca frena el giro)"),
    ("13_tapa_cable_l2", "negro", "0.12 mm", "Ninguno", "Tapa trasera cola de milano para cableado"),
    ("tapa_j2_izq", "negro", "0.12 mm", "Ninguno", "Tapa Stealth bayoneta 32° lado pivote pasivo"),
    ("tapa_j2_der", "negro", "0.12 mm", "Ninguno", "Tapa Stealth bayoneta 32° lado acceso horn"),
    ("w_aro_j2_izq", "blanco", "0.16 mm", "Ninguno", "Aro blanco incrustado J2 izquierdo"),
    ("w_aro_j2_der", "blanco", "0.16 mm", "Ninguno", "Aro blanco incrustado J2 derecho"),
]

# Colores de hardware real en vistas 3D
def _hw_color(fname: str):
    if fname.startswith("hw_servo_"):
        return (0.14, 0.45, 0.80)
    if fname == "hw_elec_04.stl":
        return (0.12, 0.34, 0.58)
    if fname.startswith("hw_elec_"):
        return (0.10, 0.56, 0.28)
    if fname in ("hw_steel_01.stl", "hw_steel_02.stl"):
        return (0.26, 0.26, 0.30)
    if fname == "hw_steel_21.stl":  # Dupont env PCA
        return (0.62, 0.66, 0.74)
    if fname in [f"hw_steel_{i:02d}.stl" for i in range(3, 9)]:  # 6 discos lastre
        return (0.56, 0.58, 0.62)
    return (0.76, 0.78, 0.82)


def _load_font(size: int, bold: bool = False):
    for p in [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _export_phase_3mf(specs, out_name: str, gap: float = 12.0):
    items = []
    for name, color, layer, sup, note in specs:
        src = os.path.join(ORI_BLK if color == "negro" else ORI_WHT, f"{name}.stl")
        m = trimesh.load(src, force="mesh")
        assert m.is_watertight and len(m.split(only_watertight=False)) == 1, f"{name} inválido!"
        bmin, bmax = m.bounds
        m.apply_translation([-0.5 * (bmin[0] + bmax[0]), -0.5 * (bmin[1] + bmax[1]), -bmin[2]])
        ext = m.bounds[1] - m.bounds[0]
        items.append({
            "name": name, "color": color, "layer": layer, "support": sup, "note": note,
            "mesh": m, "ext": ext, "grams": round(_est_grams(m), 1),
            "contact_mm2": round(_contact_area_mm2(m), 0),
        })
    placed, _gap = pack_on_plate(items, gap=gap)
    scene = trimesh.Scene()
    for p in placed:
        zmin = float(p["mesh"].bounds[0][2])
        assert abs(zmin) < 1e-3, f"{p['name']} zmin={zmin}"
        scene.add_geometry(p["mesh"], node_name=p["name"], geom_name=p["name"])
    out_path = os.path.join(OUT_3MF_DIR, out_name)
    scene.export(out_path)
    tot_g = round(sum(p["grams"] for p in placed), 1)
    print(f"  [OK] {out_name:36s} | {len(placed)} pzas | {tot_g:5.1f} g | Z=0.000")
    return placed, tot_g


def _vtk_actor_from_stl(fpath: str, rgb, opacity: float = 1.0, offset=(0, 0, 0)):
    r = vtk.vtkSTLReader()
    r.SetFileName(fpath)
    r.Update()
    n = vtk.vtkPolyDataNormals()
    n.SetInputConnection(r.GetOutputPort())
    n.SetFeatureAngle(35.0)
    n.SplittingOn()
    n.Update()
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.SetPosition(*offset)
    p = a.GetProperty()
    p.SetColor(*rgb)
    p.SetAmbient(0.24)
    p.SetDiffuse(0.76)
    p.SetSpecular(0.22)
    p.SetSpecularPower(26.0)
    p.SetOpacity(opacity)
    return a


def _vtk_actor_from_trimesh(mesh: trimesh.Trimesh, rgb):
    pts = vtk.vtkPoints()
    for v in mesh.vertices:
        pts.InsertNextPoint(float(v[0]), float(v[1]), float(v[2]))
    cells = vtk.vtkCellArray()
    for f in mesh.faces:
        cells.InsertNextCell(3)
        cells.InsertCellPoint(int(f[0]))
        cells.InsertCellPoint(int(f[1]))
        cells.InsertCellPoint(int(f[2]))
    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(cells)
    n = vtk.vtkPolyDataNormals()
    n.SetInputData(pd)
    n.SetFeatureAngle(35.0)
    n.SplittingOn()
    n.Update()
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*rgb)
    p.SetAmbient(0.24)
    p.SetDiffuse(0.76)
    p.SetSpecular(0.22)
    p.SetSpecularPower(24.0)
    return a


def _render_vtk(actors, cam_pos, cam_focal, view_angle=30.0, size=(680, 560), bg1=(0.955, 0.96, 0.97), bg2=(0.86, 0.88, 0.91), with_desk=True, desk_r=95.0, desk_cx=0.0):
    ren = vtk.vtkRenderer()
    ren.SetBackground(*bg1)
    ren.SetBackground2(*bg2)
    ren.GradientBackgroundOn()

    if with_desk:
        disk = vtk.vtkCylinderSource()
        disk.SetRadius(desk_r)
        disk.SetHeight(1.2)
        disk.SetResolution(80)
        tf = vtk.vtkTransform()
        tf.RotateX(90.0)
        tf.Translate(desk_cx, 0.0, -0.7)
        tpf = vtk.vtkTransformPolyDataFilter()
        tpf.SetInputConnection(disk.GetOutputPort())
        tpf.SetTransform(tf)
        md = vtk.vtkPolyDataMapper()
        md.SetInputConnection(tpf.GetOutputPort())
        ad = vtk.vtkActor()
        ad.SetMapper(md)
        ad.GetProperty().SetColor(0.86, 0.85, 0.83)
        ad.GetProperty().SetOpacity(0.58)
        ren.AddActor(ad)

    for a in actors:
        ren.AddActor(a)

    ren.AutomaticLightCreationOff()
    for pos, inten in [((340, -320, 420), 0.94), ((-280, -240, 240), 0.48), ((0, 340, 260), 0.36)]:
        lt = vtk.vtkLight()
        lt.SetLightTypeToSceneLight()
        lt.SetPosition(*pos)
        lt.SetFocalPoint(*cam_focal)
        lt.SetIntensity(inten)
        ren.AddLight(lt)

    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(*cam_focal)
    cam.SetPosition(*cam_pos)
    cam.SetViewUp(0.0, 0.0, 1.0)
    cam.SetViewAngle(view_angle)
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
    arr = np.frombuffer(vimg.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], 3)
    arr = np.flipud(arr)
    win.Finalize()
    return Image.fromarray(arr)


def _render_parts_plate(specs, size=(680, 520), board_w=375.0, board_d=255.0):
    """Renderiza una vista isométrica limpia de todas las piezas a imprimir de una fase sobre un tapete de corte."""
    items = []
    for name, color, layer, sup, note in specs:
        src = os.path.join(ORI_BLK if color == "negro" else ORI_WHT, f"{name}.stl")
        m = trimesh.load(src, force="mesh")
        bmin, bmax = m.bounds
        m.apply_translation([-0.5 * (bmin[0] + bmax[0]), -0.5 * (bmin[1] + bmax[1]), -bmin[2]])
        ext = m.bounds[1] - m.bounds[0]
        items.append({
            "name": name, "color": color, "layer": layer, "support": sup, "note": note,
            "mesh": m, "ext": ext, "grams": round(_est_grams(m), 1),
        })
    placed, _gap = pack_on_plate(items, bed_w=board_w, bed_d=board_d, margin=10.0, gap=10.0)

    ren = vtk.vtkRenderer()
    ren.SetBackground(0.955, 0.96, 0.97)
    ren.SetBackground2(0.87, 0.89, 0.92)
    ren.GradientBackgroundOn()

    # Tapete / Cama PEI
    bed = vtk.vtkCubeSource()
    bed.SetXLength(board_w); bed.SetYLength(board_d); bed.SetZLength(1.4)
    bed.SetCenter(board_w / 2.0, board_d / 2.0, -0.75)
    mb = vtk.vtkPolyDataMapper(); mb.SetInputConnection(bed.GetOutputPort())
    ab = vtk.vtkActor(); ab.SetMapper(mb)
    ab.GetProperty().SetColor(0.24, 0.26, 0.30)
    ren.AddActor(ab)

    # Cuadrícula 30 mm
    pts = vtk.vtkPoints(); lines = vtk.vtkCellArray(); idx = 0
    for k in range(0, int(board_w) + 1, 30):
        pts.InsertNextPoint(k, 0, 0.05); pts.InsertNextPoint(k, board_d, 0.05)
        lines.InsertNextCell(2); lines.InsertCellPoint(idx); lines.InsertCellPoint(idx + 1); idx += 2
    for k in range(0, int(board_d) + 1, 30):
        pts.InsertNextPoint(0, k, 0.05); pts.InsertNextPoint(board_w, k, 0.05)
        lines.InsertNextCell(2); lines.InsertCellPoint(idx); lines.InsertCellPoint(idx + 1); idx += 2
    gpd = vtk.vtkPolyData(); gpd.SetPoints(pts); gpd.SetLines(lines)
    gm = vtk.vtkPolyDataMapper(); gm.SetInputData(gpd)
    ga = vtk.vtkActor(); ga.SetMapper(gm)
    ga.GetProperty().SetColor(0.38, 0.42, 0.48); ga.GetProperty().SetLineWidth(1.0)
    ren.AddActor(ga)

    for p in placed:
        rgb = (0.14, 0.15, 0.18) if p["color"] == "negro" else (0.97, 0.97, 0.96)
        ren.AddActor(_vtk_actor_from_trimesh(p["mesh"], rgb))

    cx0, cy0 = board_w / 2.0, board_d / 2.0
    ren.AutomaticLightCreationOff()
    for pos, inten in [((cx0 + 280, cy0 - 260, 440), 0.95), ((cx0 - 260, cy0 - 200, 260), 0.48), ((cx0, cy0 + 340, 260), 0.38)]:
        lt = vtk.vtkLight(); lt.SetLightTypeToSceneLight()
        lt.SetPosition(*pos); lt.SetFocalPoint(cx0, cy0, 10); lt.SetIntensity(inten)
        ren.AddLight(lt)

    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(cx0, cy0, 12.0)
    scale = board_w / 256.0
    cam.SetPosition(cx0 + 165.0 * scale, cy0 - 265.0 * scale, 265.0 * scale)
    cam.SetViewUp(0.0, 0.0, 1.0)
    cam.SetViewAngle(33.0)
    ren.ResetCameraClippingRange()

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(*size)
    win.SetMultiSamples(4)
    win.Render()

    # Proyectar etiquetas numeradas sobre cada pieza
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    markers = []
    for num, p in enumerate(placed, 1):
        bmin, bmax = p["mesh"].bounds
        cx, cy, cz = 0.5 * (bmin[0] + bmax[0]), 0.5 * (bmin[1] + bmax[1]), float(bmax[2]) + 2.0
        coord.SetValue(cx, cy, cz)
        dx, dy = coord.GetComputedDisplayValue(ren)
        markers.append((num, int(dx), int(size[1] - dy), p))

    w2i = vtk.vtkWindowToImageFilter(); w2i.SetInput(win); w2i.Update()
    vimg = w2i.GetOutput(); dims = vimg.GetDimensions()
    arr = np.frombuffer(vimg.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], 3)
    img = Image.fromarray(np.flipud(arr))
    win.Finalize()

    draw = ImageDraw.Draw(img)
    f_num = _load_font(15, bold=True)
    for num, px, py, p in markers:
        r = 12
        bg = (234, 88, 12) if p["support"].startswith("Árbol") else ((37, 99, 235) if p["color"] == "blanco" else (16, 185, 129))
        draw.ellipse([px - r, py - r, px + r, py + r], fill=bg, outline=(255, 255, 255), width=2)
        t = str(num)
        tw = draw.textlength(t, font=f_num)
        draw.text((px - tw / 2, py - 9.5), t, fill=(255, 255, 255), font=f_num)

    return img, placed


def _compose_phase_board(title, subtitle, panels, placed_parts, out_png, legend_note):
    tw, th = 680, 520
    pad = 22
    header_h = 92
    cap_h = 54
    table_h = 44 + len(placed_parts) * 28 + 26
    W = tw * 3 + pad * 4
    H = header_h + pad + th + cap_h + pad + table_h + pad

    board = Image.new("RGB", (W, H), (244, 246, 249))
    draw = ImageDraw.Draw(board)
    f_h1 = _load_font(27, bold=True)
    f_sub = _load_font(15.5, bold=False)
    f_t = _load_font(17, bold=True)
    f_s = _load_font(13.5, bold=False)
    f_th = _load_font(14.5, bold=True)
    f_td = _load_font(14, bold=False)

    draw.rectangle([0, 0, W, header_h], fill=(15, 23, 42))
    draw.text((pad, 16), title, fill=(248, 250, 252), font=f_h1)
    draw.text((pad, 54), subtitle, fill=(148, 163, 184), font=f_sub)

    y0 = header_h + pad
    for idx, (im, pt, ps) in enumerate(panels):
        x0 = pad + idx * (tw + pad)
        draw.rounded_rectangle([x0 - 2, y0 - 2, x0 + tw + 2, y0 + th + cap_h + 2], radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        board.paste(im, (x0, y0))
        draw.text((x0 + 14, y0 + th + 6), pt, fill=(15, 23, 42), font=f_t)
        draw.text((x0 + 14, y0 + th + 30), ps, fill=(71, 85, 105), font=f_s)

    # Tabla inferior con el listado numerado exacto de piezas a imprimir
    ty = y0 + th + cap_h + pad
    draw.rounded_rectangle([pad - 2, ty - 2, W - pad + 2, ty + table_h], radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
    draw.rectangle([pad, ty, W - pad, ty + 36], fill=(241, 245, 249))
    cols_x = [pad + 18, pad + 70, pad + 370, pad + 495, pad + 605, pad + 795, pad + 895]
    headers = ["#", "Archivo STL / Pieza", "Filamento", "Capa", "Soportes", "Masa", "Función mecánica en esta fase"]
    for cx, htxt in zip(cols_x, headers):
        draw.text((cx, ty + 9), htxt, fill=(30, 41, 59), font=f_th)

    ry = ty + 42
    for num, p in enumerate(placed_parts, 1):
        bg_dot = (234, 88, 12) if p["support"].startswith("Árbol") else ((37, 99, 235) if p["color"] == "blanco" else (16, 185, 129))
        draw.ellipse([cols_x[0], ry + 1, cols_x[0] + 20, ry + 21], fill=bg_dot)
        tw_n = draw.textlength(str(num), font=f_td)
        draw.text((cols_x[0] + 10 - tw_n / 2, ry + 1), str(num), fill=(255, 255, 255), font=f_td)
        fil_lbl = "PLA+ Negro" if p["color"] == "negro" else "Blanco Mate"
        vals = [p["name"], fil_lbl, p["layer"], p["support"], f"{p['grams']:.1f} g", p["note"]]
        for cx, vtxt in zip(cols_x[1:], vals):
            draw.text((cx, ry + 2), vtxt, fill=(15, 23, 42), font=f_td)
        ry += 28

    draw.text((pad + 18, ty + table_h - 24), legend_note, fill=(71, 85, 105), font=f_s)
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    board.save(out_png)
    print(f"[OK] Tablero visual guardado: {out_png}")


def main():
    os.makedirs(OUT_3MF_DIR, exist_ok=True)
    os.makedirs(OUT_REND_DIR, exist_ok=True)

    print("=== EXPORTANDO PLACAS .3MF POR GRADO DE LIBERTAD (GDL 1 Y GDL 2 · Z=0) ===")
    _export_phase_3mf([s for s in GDL1_PRINT if s[1] == "negro" and s[2] == "0.20 mm"], "gdl1_placa_a_estructura_020mm.3mf")
    _export_phase_3mf([s for s in GDL1_PRINT if s[1] == "negro" and s[2] == "0.12 mm"], "gdl1_placa_b_precision_012mm.3mf")
    _export_phase_3mf([s for s in GDL1_PRINT if s[1] == "blanco"], "gdl1_placa_c_blanco_016mm.3mf")

    _export_phase_3mf([s for s in GDL2_PRINT if s[1] == "negro" and s[2] == "0.20 mm"], "gdl2_placa_a_estructura_020mm.3mf")
    _export_phase_3mf([s for s in GDL2_PRINT if s[1] == "negro" and s[2] == "0.12 mm"], "gdl2_placa_b_precision_012mm.3mf")
    _export_phase_3mf([s for s in GDL2_PRINT if s[1] == "blanco"], "gdl2_placa_c_blanco_016mm.3mf")

    # ------------------------------------------------------------------
    # IMAGEN 1 — FASE 1: GDL 1 (BASE COAXIAL Ø106 + TORRETA J1 + ELECTRÓNICA)
    # ------------------------------------------------------------------
    gdl1_blk = ["01_base_fija_v4.stl", "03_tapa_inferior_v4.stl", "03b_bandeja_electronica_v4.stl", "04b_reten_axial_j1.stl", "04_torreta_j1_hombro_v4.stl"]
    gdl1_wht = ["w01_aro_base_blanco.stl"]
    gdl1_hw = ["hw_servo_00.stl"] + [f"hw_elec_{i:02d}.stl" for i in range(5)] + [f"hw_steel_{i:02d}.stl" for i in range(26)]

    gdl1_solid_actors = (
        [_vtk_actor_from_stl(os.path.join(BLK_DIR, f), (0.14, 0.15, 0.18), 1.0) for f in gdl1_blk]
        + [_vtk_actor_from_stl(os.path.join(WHT_DIR, f), (0.97, 0.97, 0.96), 1.0) for f in gdl1_wht]
        + [_vtk_actor_from_stl(os.path.join(HW_DIR, f), _hw_color(f), 1.0) for f in gdl1_hw]
    )

    # Explosión vertical limpia + Rayos-X de GDL 1 para ver lastre, bandeja ciega, PCA, XIAO, MG90S J1 y retén 04b!
    exp1 = {
        "03_tapa_inferior_v4.stl": (0, 0, -48),
        "03b_bandeja_electronica_v4.stl": (0, 0, -24),
        "01_base_fija_v4.stl": (0, 0, 0),
        "w01_aro_base_blanco.stl": (0, 0, 18),
        "04b_reten_axial_j1.stl": (0, 0, 12),
        "04_torreta_j1_hombro_v4.stl": (0, 0, 34),
    }
    def _exp1_hw(f):
        if f in [f"hw_steel_{i:02d}.stl" for i in range(3, 9)]:  # 6 discos lastre
            return (0, 0, -42)
        if f in ("hw_steel_09.stl", "hw_steel_11.stl", "hw_steel_13.stl", "hw_steel_15.stl"):  # 4 tornillos base
            return (0, 0, -54)
        if f in ("hw_elec_02.stl", "hw_elec_03.stl", "hw_elec_04.stl", "hw_steel_21.stl", "hw_steel_22.stl") or f in [f"hw_steel_{i:02d}.stl" for i in range(17, 21)]:
            return (0, 0, -24)  # PCA + XIAO + Cap + 4×M3×4 sobre bandeja
        if f in ("hw_steel_23.stl", "hw_steel_24.stl", "hw_steel_25.stl"):  # 3× M3×8 retén
            return (0, 0, 12)
        return (0, 0, 0)

    gdl1_exp_actors = (
        [_vtk_actor_from_stl(os.path.join(BLK_DIR, f), (0.14, 0.15, 0.18), 0.34 if f == "01_base_fija_v4.stl" else 0.88, exp1[f]) for f in gdl1_blk]
        + [_vtk_actor_from_stl(os.path.join(WHT_DIR, f), (0.97, 0.97, 0.96), 1.0, exp1[f]) for f in gdl1_wht]
        + [_vtk_actor_from_stl(os.path.join(HW_DIR, f), _hw_color(f), 1.0, _exp1_hw(f)) for f in gdl1_hw]
    )

    im1_a = _render_vtk(gdl1_solid_actors, (175, -185, 130), (0, 0, 48), 32.0, (680, 520), desk_r=82.0)
    im1_b = _render_vtk(gdl1_exp_actors, (265, -285, 165), (0, 0, 38), 34.0, (680, 520), with_desk=False)
    im1_c, placed1 = _render_parts_plate(GDL1_PRINT, (680, 520))

    tot1_g = sum(p["grams"] for p in placed1)
    _compose_phase_board(
        "FASE 1 — PRIMER GRADO DE LIBERTAD (GDL 1 · BASE COAXIAL J1 YAW ±85°)",
        f"6 piezas imprimibles (~{tot1_g:.1f} g PLA · 0% purga AMS) · Toda la electrónica de potencia (1 cable USB-C) + Lastre 218 g + MG90S J1",
        [
            (im1_a, "1 · GDL 1 ENSAMBLADO (B2 STEALTH)", "Base Ø106 mm + aro blanco w01 + torreta coaxial sobre pista Ø88 mm"),
            (im1_b, "2 · EXPLOSIONADO INTERNO (0.0000 mm³)", "Lastre 6 pilas → Bandeja ciega PCA (4×M3×4) → MG90S J1 → Retén 04b (3×M3×8)"),
            (im1_c, "3 · PIEZAS A IMPRIMIR SOLO PARA GDL 1", "Naranja: Árbol solo cama (0.20) · Verde: 0 soportes (0.12) · Azul: Blanco (0.16)"),
        ],
        placed1,
        os.path.join(OUT_REND_DIR, "fase1_gdl1_base_j1.png"),
        "Tornillería GDL 1: 4× M3×4 (PCA ciego) · 3× M3×8 (retén J1) · 4× M3×16 + 4× Hex M3 (base) · 2× M2×6 + horn (MG90S J1) · 6× gomitas Ø10 · Lastre ≥ 215 g",
    )

    # ------------------------------------------------------------------
    # IMAGEN 2 — FASE 2: GDL 1 + GDL 2 (HOMBRO PITCH J2 + BRAZO L2 MONOLÍTICO)
    # ------------------------------------------------------------------
    gdl2_blk = gdl1_blk + ["05_eslabon_l2_v4.stl", "11_separador_m3_j2.stl", "13_tapa_cable_l2.stl", "tapa_j2_izq.stl", "tapa_j2_der.stl"]
    gdl2_wht = gdl1_wht + ["w_aro_j2_izq.stl", "w_aro_j2_der.stl"]
    gdl2_hw = gdl1_hw + ["hw_servo_01.stl", "hw_steel_26.stl", "hw_steel_27.stl"]

    gdl2_solid_actors = (
        [_vtk_actor_from_stl(os.path.join(BLK_DIR, f), (0.14, 0.15, 0.18), 1.0) for f in gdl2_blk]
        + [_vtk_actor_from_stl(os.path.join(WHT_DIR, f), (0.97, 0.97, 0.96), 1.0) for f in gdl2_wht]
        + [_vtk_actor_from_stl(os.path.join(HW_DIR, f), _hw_color(f), 1.0) for f in gdl2_hw]
    )

    # Zoom Explosionado + Rayos-X de la articulación J2 (lado pivote pasivo + lado horn MG90S J2!)
    exp2 = {
        "04_torreta_j1_hombro_v4.stl": (0, 0, 0),
        "05_eslabon_l2_v4.stl": (12, 0, 26),
        "13_tapa_cable_l2.stl": (4, 0, 44),
        "11_separador_m3_j2.stl": (0, -20, 0),
        "tapa_j2_izq.stl": (0, -34, 0),
        "w_aro_j2_izq.stl": (0, -40, 0),
        "tapa_j2_der.stl": (0, +30, 0),
        "w_aro_j2_der.stl": (0, +36, 0),
    }
    gdl2_zoom_actors = [
        _vtk_actor_from_stl(os.path.join(BLK_DIR, "04_torreta_j1_hombro_v4.stl"), (0.16, 0.17, 0.20), 0.36, (0, 0, 0)),
        _vtk_actor_from_stl(os.path.join(BLK_DIR, "05_eslabon_l2_v4.stl"), (0.14, 0.15, 0.18), 0.92, exp2["05_eslabon_l2_v4.stl"]),
        _vtk_actor_from_stl(os.path.join(BLK_DIR, "13_tapa_cable_l2.stl"), (0.30, 0.32, 0.36), 1.0, exp2["13_tapa_cable_l2.stl"]),
        _vtk_actor_from_stl(os.path.join(BLK_DIR, "11_separador_m3_j2.stl"), (0.28, 0.30, 0.35), 1.0, exp2["11_separador_m3_j2.stl"]),
        _vtk_actor_from_stl(os.path.join(BLK_DIR, "tapa_j2_izq.stl"), (0.14, 0.15, 0.18), 1.0, exp2["tapa_j2_izq.stl"]),
        _vtk_actor_from_stl(os.path.join(BLK_DIR, "tapa_j2_der.stl"), (0.14, 0.15, 0.18), 1.0, exp2["tapa_j2_der.stl"]),
        _vtk_actor_from_stl(os.path.join(WHT_DIR, "w_aro_j2_izq.stl"), (0.97, 0.97, 0.96), 1.0, exp2["w_aro_j2_izq.stl"]),
        _vtk_actor_from_stl(os.path.join(WHT_DIR, "w_aro_j2_der.stl"), (0.97, 0.97, 0.96), 1.0, exp2["w_aro_j2_der.stl"]),
        _vtk_actor_from_stl(os.path.join(HW_DIR, "hw_servo_01.stl"), (0.14, 0.45, 0.80), 1.0, (0, +10, 0)),
        _vtk_actor_from_stl(os.path.join(HW_DIR, "hw_steel_26.stl"), (0.78, 0.80, 0.84), 1.0, (0, -28, 0)),  # M3×12 J2
        _vtk_actor_from_stl(os.path.join(HW_DIR, "hw_steel_27.stl"), (0.78, 0.80, 0.84), 1.0, (0, -8, 0)),   # M3 Nyloc J2
    ]

    im2_a = _render_vtk(gdl2_solid_actors, (240, -255, 185), (14, 0, 92), 32.0, (680, 520), desk_r=92.0)
    im2_b = _render_vtk(gdl2_zoom_actors, (230, -245, 195), (16, 0, 122), 33.0, (680, 520), with_desk=False)
    im2_c, placed2 = _render_parts_plate(GDL2_PRINT, (680, 520), board_w=200.0, board_d=140.0)

    tot2_g = sum(p["grams"] for p in placed2)
    _compose_phase_board(
        "FASE 2 — SEGUNDO GRADO DE LIBERTAD (GDL 1 + GDL 2 · HOMBRO J2 [+22°..+145°] + BRAZO L2)",
        f"7 piezas adicionales (~{tot2_g:.1f} g PLA · 0% purga AMS) · Mamparo Nyloc 1.20 mm · Casquillo liso M3 · Acceso horn Ø5.2 mm · Bayonetas 32°",
        [
            (im2_a, "1 · GDL 1 + GDL 2 ENSAMBLADOS (J2 = 68°)", "Subensamble activo 2-DOF listo para pruebas de par, corriente y temperatura en banco"),
            (im2_b, "2 · EXPLOSIONADO ARTICULACIÓN J2 (RAYOS-X)", "MG90S J2 (+Y) | Mamparo 1.2 mm | Nyloc + M3×12 (-Y) | Casquillo liso | Bayonetas 32°"),
            (im2_c, "3 · PIEZAS ADICIONALES A IMPRIMIR PARA GDL 2", "Naranja: Árbol solo cama (0.20) · Verde: 0 soportes (0.12) · Azul: Blanco (0.16)"),
        ],
        placed2,
        os.path.join(OUT_REND_DIR, "fase2_gdl2_hombro_j2.png"),
        "Tornillería adicional GDL 2: 1× M3×12 cabeza botón + 1× tuerca M3 Nyloc (pivote pasivo) · 2× M2×6 + tornillo horn (incluidos con MG90S J2)",
    )


if __name__ == "__main__":
    main()
