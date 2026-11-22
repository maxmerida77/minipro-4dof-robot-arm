"""
Generador de Catálogo Visual de Piezas CAD — Mini-Pro 4-DOF (`B2 Stealth` v2)
=============================================================================
Renderiza en 3D real (VTK) cada familia de piezas directamente desde los `.STL`
exportados en `cad/exports/`, calcula sus dimensiones exactas (mm), volumen y
peso estimado en PLA, y guarda un tablero visual limpio en:
    docs/renders/catalogo_piezas_b2_stealth.png
"""

import os
import json
import numpy as np
import trimesh
import vtk
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXP = os.path.join(HERE, "exports")
BLK_DIR = os.path.join(EXP, "stl_negro_mate")
WHT_DIR = os.path.join(EXP, "stl_blanco_mate")
OUT_PNG = os.path.join(ROOT, "docs", "renders", "catalogo_piezas_b2_stealth.png")
OUT_JSON = os.path.join(ROOT, "docs", "renders", "catalogo_piezas_metricas.json")


def _load_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _stl_to_vtk_actor(path: str, rgb, metallic=0.05, roughness=0.55):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(path)
    reader.Update()

    # Centrar pieza en el origen para encuadre perfecto en miniatura
    poly = reader.GetOutput()
    bounds = poly.GetBounds()
    cx = 0.5 * (bounds[0] + bounds[1])
    cy = 0.5 * (bounds[2] + bounds[3])
    cz = 0.5 * (bounds[4] + bounds[5])

    tf = vtk.vtkTransform()
    tf.Translate(-cx, -cy, -cz)
    tpf = vtk.vtkTransformPolyDataFilter()
    tpf.SetInputData(poly)
    tpf.SetTransform(tf)
    tpf.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(tpf.GetOutputPort())
    normals.SetFeatureAngle(35.0)
    normals.SplittingOn()
    normals.ConsistencyOn()
    normals.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*rgb)
    prop.SetAmbient(0.24)
    prop.SetDiffuse(0.76)
    prop.SetSpecular(0.18 + metallic)
    prop.SetSpecularPower(22.0)
    return actor, bounds


def _render_tile(stl_specs, cam_dir=(1.15, -1.25, 0.85), w=520, h=420, bg=(0.945, 0.945, 0.935), recenter_each=False):
    """Renderiza una o más piezas STL juntas centradas en un lienzo VTK offscreen."""
    ren = vtk.vtkRenderer()
    ren.SetBackground(*bg)

    all_bounds = []
    polys = []
    for path, rgb, shift in stl_specs:
        r = vtk.vtkSTLReader()
        r.SetFileName(path)
        r.Update()
        p = r.GetOutput()
        b = p.GetBounds()
        if recenter_each:
            # Re-centrar pieza individual en origen y aplicar `shift` de presentación
            px, py, pz = 0.5 * (b[0] + b[1]), 0.5 * (b[2] + b[3]), 0.5 * (b[4] + b[5])
            eff_shift = (shift[0] - px, shift[1] - py, shift[2] - pz)
        else:
            eff_shift = shift
        all_bounds.append((b[0] + eff_shift[0], b[1] + eff_shift[0], b[2] + eff_shift[1], b[3] + eff_shift[1], b[4] + eff_shift[2], b[5] + eff_shift[2]))
        polys.append((p, rgb, eff_shift))

    xmin = min(b[0] for b in all_bounds); xmax = max(b[1] for b in all_bounds)
    ymin = min(b[2] for b in all_bounds); ymax = max(b[3] for b in all_bounds)
    zmin = min(b[4] for b in all_bounds); zmax = max(b[5] for b in all_bounds)
    cx, cy, cz = 0.5 * (xmin + xmax), 0.5 * (ymin + ymax), 0.5 * (zmin + zmax)
    diag = max(12.0, float(np.linalg.norm([xmax - xmin, ymax - ymin, zmax - zmin])))

    for poly, rgb, shift in polys:
        tf = vtk.vtkTransform()
        tf.Translate(shift[0] - cx, shift[1] - cy, shift[2] - cz)
        tpf = vtk.vtkTransformPolyDataFilter()
        tpf.SetInputData(poly)
        tpf.SetTransform(tf)
        tpf.Update()

        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(tpf.GetOutputPort())
        normals.SetFeatureAngle(35.0)
        normals.SplittingOn()
        normals.Update()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*rgb)
        prop.SetAmbient(0.24)
        prop.SetDiffuse(0.78)
        prop.SetSpecular(0.20)
        prop.SetSpecularPower(26.0)
        ren.AddActor(actor)

    # Iluminación de estudio 3 puntos
    ren.AutomaticLightCreationOff()
    for pos, intensity in [
        ((diag * 2.2, -diag * 1.8, diag * 2.4), 0.92),
        ((-diag * 2.0, -diag * 1.4, diag * 1.2), 0.45),
        ((0.0, diag * 2.5, diag * 1.0), 0.35),
    ]:
        lt = vtk.vtkLight()
        lt.SetLightTypeToSceneLight()
        lt.SetPosition(*pos)
        lt.SetFocalPoint(0, 0, 0)
        lt.SetIntensity(intensity)
        ren.AddLight(lt)

    cam = ren.GetActiveCamera()
    d_vec = np.array(cam_dir, dtype=float)
    d_vec = d_vec / np.linalg.norm(d_vec) * (diag * 1.65)
    cam.SetPosition(*d_vec)
    cam.SetFocalPoint(0.0, 0.0, 0.0)
    cam.SetViewUp(0.0, 0.0, 1.0)
    cam.SetViewAngle(30.0)
    ren.ResetCameraClippingRange()

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(w, h)
    win.SetMultiSamples(4)
    win.Render()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    vtk_img = w2i.GetOutput()
    dims = vtk_img.GetDimensions()
    arr = np.frombuffer(vtk_img.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], 3)
    arr = np.flipud(arr)
    win.Finalize()
    return Image.fromarray(arr)


def compute_metrics():
    """Calcula dimensiones exactas, volumen y masa estimada para cada uno de los 29 STLs."""
    records = []
    for folder, color_tag in [(BLK_DIR, "Negro Mate"), (WHT_DIR, "Blanco Mate")]:
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".stl"):
                continue
            fpath = os.path.join(folder, fname)
            mesh = trimesh.load_mesh(fpath)
            ext = [float(x) for x in mesh.extents]
            # Para piezas inclinadas (eslabones L2/L3), usar OBB si reduce volumen caja; para cilíndricas usar AABB exacto
            if fname.startswith(("05_", "06_", "10_")) and len(mesh.faces) > 8:
                ext = [float(x) for x in mesh.bounding_box_oriented.extents]
            ext_sorted = sorted(ext, reverse=True)
            vol_cm3 = abs(float(mesh.volume)) / 1000.0
            eff_density = 1.05 if vol_cm3 < 2.5 else 0.62
            mass_g = vol_cm3 * eff_density
            records.append({
                "file": fname,
                "color": color_tag,
                "dims_mm": [round(x, 1) for x in ext_sorted],
                "vol_cm3": round(vol_cm3, 2),
                "est_mass_g": round(mass_g, 1),
                "watertight": bool(mesh.is_watertight),
            })
    return records


def main():
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    metrics = compute_metrics()
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    m_by_name = {r["file"]: r for r in metrics}
    blk = (0.16, 0.16, 0.18)
    wht = (0.97, 0.97, 0.96)
    bg_dark_tile = (0.20, 0.20, 0.23)  # Para contrastar las piezas blancas

    tiles = [
        (
            "01 · Base Fija Hueca",
            "01_base_fija_hueca.stl · 1× Negro",
            "Asiento 608ZZ + MG90S J1 + bahía trasera XIAO/AR5515/KCD11",
            [(os.path.join(BLK_DIR, "01_base_fija_hueca.stl"), blk, (0, 0, 0))],
            (-1.2, -1.1, 0.78),
            (0.945, 0.945, 0.935),
        ),
        (
            "02 · Transmisión Base 22T:22T",
            "02_pinon_base_22t + 04b_engrane_torreta_22t · 2× Negro",
            "Par 1:1 separable: piñón en MG90S J1 + engrane bajo 608ZZ",
            [
                (os.path.join(BLK_DIR, "02_pinon_base_22t.stl"), blk, (-14, 0, 0)),
                (os.path.join(BLK_DIR, "04b_engrane_torreta_22t.stl"), blk, (14, 0, 0)),
            ],
            (0.6, -1.1, 1.35),
            (0.945, 0.945, 0.935),
            True,
        ),
        (
            "03 · Tapa Inferior Electrónica",
            "03_tapa_inferior_electronica.stl · 1× Negro",
            "4 postes PCA9685 + cuna XIAO ESP32-S3 + 4× tornillo M3",
            [(os.path.join(BLK_DIR, "03_tapa_inferior_electronica.stl"), blk, (0, 0, 0))],
            (-1.0, -1.2, 1.05),
            (0.945, 0.945, 0.935),
        ),
        (
            "04 · Torreta J1 + Hombro J2",
            "04_torreta_j1_hombro.stl · 1× Negro",
            "Corona + eje 608ZZ + tambor J2 (MG90S + 608ZZ ocultos)",
            [(os.path.join(BLK_DIR, "04_torreta_j1_hombro.stl"), blk, (0, 0, 0))],
            (1.1, -1.25, 0.65),
            (0.945, 0.945, 0.935),
        ),
        (
            "05 · Eslabón Inferior L2 + Codo J3",
            "05_eslabon_l2_codo.stl · 1× Negro",
            "Viga octagonal hueca (a2=82 mm) + bolsillo MG90S J3",
            [(os.path.join(BLK_DIR, "05_eslabon_l2_codo.stl"), blk, (0, 0, 0))],
            (0.85, -1.45, 0.60),
            (0.945, 0.945, 0.935),
        ),
        (
            "06 · Antebrazo L3 + Muñeca J4",
            "06_antebrazo_l3_muneca.stl · 1× Negro",
            "Viga octagonal hueca (a3=70 mm) + bolsillo MG90S J4",
            [(os.path.join(BLK_DIR, "06_antebrazo_l3_muneca.stl"), blk, (0, 0, 0))],
            (0.85, -1.45, 0.60),
            (0.945, 0.945, 0.935),
        ),
        (
            "07 · Palma Pinza + Carenado SG90",
            "07_palma_pinza_sg90.stl · 1× Negro",
            "Oculta 100% tu SG90 dentro del carenado biselado inferior",
            [(os.path.join(BLK_DIR, "07_palma_pinza_sg90.stl"), blk, (0, 0, 0))],
            (1.2, -1.2, 0.65),
            (0.945, 0.945, 0.935),
        ),
        (
            "08–09 · Engranes 14T de Pinza",
            "08_engrane_pinza_izq + 09_der · 2× Negro",
            "Par sincronizado 14T (módulo 1.0) accionado por el SG90",
            [
                (os.path.join(BLK_DIR, "08_engrane_pinza_izq.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "09_engrane_pinza_der.stl"), blk, (0, 0, 0)),
            ],
            (0.8, -0.9, 1.35),
            (0.945, 0.945, 0.935),
        ),
        (
            "10 · Dedos Paralelos de Pinza",
            "10_dedo_pinza_izq + der · 2× Negro",
            "Mordazas biseladas paralelas (apertura 0–30 mm, TCP a 53 mm)",
            [
                (os.path.join(BLK_DIR, "10_dedo_pinza_izq.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "10_dedo_pinza_der.stl"), blk, (0, 0, 0)),
            ],
            (1.1, -1.1, 0.9),
            (0.945, 0.945, 0.935),
        ),
        (
            "11 · Tapas Laterales J2 / J3 / J4",
            "tapa_j2/j3/j4_(izq/der) · 6× Negro",
            "Tapas cosméticas Stealth que sellan servos y rodamientos",
            [
                (os.path.join(BLK_DIR, "tapa_j2_izq.stl"), blk, (-32, 0, 0)),
                (os.path.join(BLK_DIR, "tapa_j3_izq.stl"), blk, (2, 0, 0)),
                (os.path.join(BLK_DIR, "tapa_j4_izq.stl"), blk, (31, 0, 0)),
            ],
            (0.25, -1.6, 0.45),
            (0.945, 0.945, 0.935),
            True,
        ),
        (
            "12 · Aros e Incrustaciones B2 Stealth",
            "w01..w04 + w_aro_j2..j4 · 12× Blanco",
            "Aro base + 6 aros art. + collar + 2 aros engrane + 2 almohadillas",
            [
                (os.path.join(WHT_DIR, "w01_aro_base_blanco.stl"), wht, (-12, 0, -20)),
                (os.path.join(WHT_DIR, "w_aro_j2_izq.stl"), wht, (-36, 0, 22)),
                (os.path.join(WHT_DIR, "w_aro_j3_izq.stl"), wht, (0, 0, 22)),
                (os.path.join(WHT_DIR, "w_aro_j4_izq.stl"), wht, (32, 0, 22)),
                (os.path.join(WHT_DIR, "w02_collar_muneca_blanco.stl"), wht, (52, 0, -14)),
                (os.path.join(WHT_DIR, "w04_almohadilla_izq.stl"), wht, (52, 16, 12)),
                (os.path.join(WHT_DIR, "w04_almohadilla_der.stl"), wht, (52, -16, 12)),
            ],
            (0.45, -1.55, 0.55),
            bg_dark_tile,
            True,
        ),
        (
            "Kit de Tolerancias (20 min)",
            "tolerance_test_kit_bambu_a1.stl · ~14 g",
            "Prueba real antes de imprimir: 608ZZ, MG90S, SG90, AR2811, KCD11",
            [(os.path.join(EXP, "tolerance_test_kit_bambu_a1.stl"), blk, (0, 0, 0))],
            (0.85, -1.15, 1.15),
            (0.945, 0.945, 0.935),
        ),
    ]

    cols, rows = 4, 3
    tw, th = 500, 390
    pad = 22
    header_h = 110
    card_footer_h = 98
    cw = cols * tw + (cols + 1) * pad
    ch = header_h + rows * (th + card_footer_h) + (rows + 1) * pad

    canvas = Image.new("RGB", (cw, ch), (244, 244, 242))
    draw = ImageDraw.Draw(canvas)
    f_title = _load_font(34, bold=True)
    f_sub = _load_font(18, bold=False)
    f_card_t = _load_font(20, bold=True)
    f_card_s = _load_font(15, bold=False)
    f_card_d = _load_font(14, bold=False)

    total_blk_g = sum(r["est_mass_g"] for r in metrics if r["color"] == "Negro Mate")
    total_wht_g = sum(r["est_mass_g"] for r in metrics if r["color"] == "Blanco Mate")

    draw.text((pad, 22), "CATÁLOGO VISUAL DE PIEZAS CAD — MINI-PRO 4-DOF (B2 STEALTH v2)", fill=(24, 24, 27), font=f_title)
    draw.text(
        (pad, 66),
        f"30 piezas STL estancas (0% purga AMS) · Estimado PLA: ~{total_blk_g:.0f} g Negro Mate (18 pzas) + ~{total_wht_g:.0f} g Blanco Mate (12 pzas)",
        fill=(92, 92, 98),
        font=f_sub,
    )

    for idx, item in enumerate(tiles):
        title, sub, desc, specs, cdir, bg = item[:6]
        recenter_each = item[6] if len(item) > 6 else False
        r = idx // cols
        c = idx % cols
        x0 = pad + c * (tw + pad)
        y0 = header_h + pad + r * (th + card_footer_h + pad)

        # Renderizar miniatura
        img_tile = _render_tile(specs, cam_dir=cdir, w=tw, h=th, bg=bg, recenter_each=recenter_each)

        # Tarjeta limpia con borde sutil
        draw.rounded_rectangle([x0 - 1, y0 - 1, x0 + tw + 1, y0 + th + card_footer_h + 1], radius=12, fill=(255, 255, 255), outline=(212, 212, 216), width=2)
        canvas.paste(img_tile, (x0, y0))

        # Texto de pie de tarjeta
        ty = y0 + th + 10
        draw.text((x0 + 14, ty), title, fill=(24, 24, 27), font=f_card_t)
        draw.text((x0 + 14, ty + 28), sub, fill=(180, 74, 24) if "Blanco" not in sub else (37, 99, 235), font=f_card_s)
        draw.text((x0 + 14, ty + 54), desc, fill=(82, 82, 91), font=f_card_d)

        # Pill con medida exacta si es pieza principal individual
        first_fname = os.path.basename(specs[0][0])
        if len(specs) == 1 and first_fname in m_by_name:
            rec = m_by_name[first_fname]
            dim_txt = f"{rec['dims_mm'][0]:.0f}×{rec['dims_mm'][1]:.0f}×{rec['dims_mm'][2]:.0f} mm · ~{rec['est_mass_g']:.0f}g"
            draw.rounded_rectangle([x0 + tw - 205, y0 + 10, x0 + tw - 10, y0 + 38], radius=8, fill=(24, 24, 27))
            draw.text((x0 + tw - 196, y0 + 15), dim_txt, fill=(248, 248, 248), font=f_card_d)

    canvas.save(OUT_PNG)
    print(f"[OK] Catálogo visual guardado en: {OUT_PNG}")
    print(f"[OK] Total estimado PLA: Negro={total_blk_g:.1f} g | Blanco={total_wht_g:.1f} g | Total={total_blk_g + total_wht_g:.1f} g")
    for r in metrics:
        print(f"  {r['color']:11s} | {r['file']:36s} | {r['dims_mm'][0]:5.1f}x{r['dims_mm'][1]:5.1f}x{r['dims_mm'][2]:5.1f} mm | {r['est_mass_g']:5.1f} g")


if __name__ == "__main__":
    main()
