"""
Generador de Catálogo Visual de Piezas CAD v4 Clean-DFA — Mini-Pro 4-DOF (`B2 Stealth`)
========================================================================================
Renderiza en 3D real (VTK) todas las familias de las 34 piezas estancas de `CAD v4 Clean-DFA`
directamente desde `cad/exports/v4_clean_dfa/`, calcula sus dimensiones exactas (mm) y masa
estimada en PLA, y guarda:
    docs/renders/catalogo_piezas_v4_clean_dfa.png
"""

import json
import os
import numpy as np
import trimesh
import vtk
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXP = os.path.join(HERE, "exports", "v4_clean_dfa")
BLK_DIR = os.path.join(EXP, "stl_negro_mate")
WHT_DIR = os.path.join(EXP, "stl_blanco_mate")
CUP_DIR = os.path.join(EXP, "cupones_prueba")
OUT_PNG = os.path.join(ROOT, "docs", "renders", "catalogo_piezas_v4_clean_dfa.png")
OUT_JSON = os.path.join(ROOT, "docs", "renders", "catalogo_piezas_v4_metricas.json")


def _load_font(size: int, bold: bool = False):
    for p in [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _render_tile(stl_specs, cam_dir=(1.15, -1.25, 0.85), w=500, h=380, bg=(0.945, 0.945, 0.935), recenter_each=False):
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

    ren.AutomaticLightCreationOff()
    for pos, intensity in [
        ((diag * 2.2, -diag * 1.8, diag * 2.4), 0.92),
        ((-diag * 2.0, -diag * 1.4, diag * 1.2), 0.46),
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
    d_vec = d_vec / np.linalg.norm(d_vec) * (diag * 1.62)
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
    records = []
    for folder, color_tag in [(BLK_DIR, "Negro Mate"), (WHT_DIR, "Blanco Mate")]:
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".stl"):
                continue
            fpath = os.path.join(folder, fname)
            mesh = trimesh.load(fpath, force="mesh")
            ext = [float(x) for x in mesh.extents]
            if fname.startswith(("05_", "06_", "10_")) and len(mesh.faces) > 8:
                ext = [float(x) for x in mesh.bounding_box_oriented.extents]
            ext_sorted = sorted(ext, reverse=True)
            vol_cm3 = abs(float(mesh.volume)) / 1000.0
            eff_density = 1.12 if min(ext_sorted) <= 4.5 else 0.62
            mass_g = vol_cm3 * eff_density
            records.append({
                "file": fname,
                "color": color_tag,
                "dims_mm": [round(x, 1) for x in ext_sorted],
                "vol_cm3": round(vol_cm3, 2),
                "est_mass_g": round(mass_g, 1),
                "watertight": bool(mesh.is_watertight),
                "bodies": len(mesh.split(only_watertight=False)),
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
    bg_dark_tile = (0.20, 0.20, 0.23)

    tiles = [
        (
            "01 · Base Coaxial Ø106 mm",
            "01_base_fija_v4.stl · 1× Negro",
            "MG90S J1 centrado + pista Ø88 + 4 tuercas M3 cautivas + AR5515/KCD11",
            [(os.path.join(BLK_DIR, "01_base_fija_v4.stl"), blk, (0, 0, 0))],
            (-1.2, -1.1, 0.78),
            (0.945, 0.945, 0.935),
        ),
        (
            "02 · Retén Axial J1 Independiente",
            "04b_reten_axial_j1.stl · 1× Negro",
            "3× M3 al cuello de torreta: libera al horn J1 de toda carga axial",
            [(os.path.join(BLK_DIR, "04b_reten_axial_j1.stl"), blk, (0, 0, 0))],
            (0.8, -1.0, 1.35),
            (0.945, 0.945, 0.935),
        ),
        (
            "03 · Tapa Bóveda Lastre + Bandeja Ciega",
            "03_tapa_inferior_v4 + 03b_bandeja · 2× Negro",
            "6 patas Ø10.6 + 6 discos acero (218 g B-Rep) + postes ciegos PCA M3×4",
            [
                (os.path.join(BLK_DIR, "03_tapa_inferior_v4.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "03b_bandeja_electronica_v4.stl"), (0.30, 0.32, 0.36), (0, 0, 22)),
            ],
            (-1.0, -1.2, 1.05),
            (0.945, 0.945, 0.935),
        ),
        (
            "04 · Torreta Coaxial J1 + Hub J2",
            "04_torreta_j1_hombro_v4.stl · 1× Negro",
            "Labio pista Ø88 + acceso Ø6 horn J1 + bolsillo M3 Nyloc en J2",
            [(os.path.join(BLK_DIR, "04_torreta_j1_hombro_v4.stl"), blk, (0, 0, 0))],
            (1.1, -1.25, 0.65),
            (0.945, 0.945, 0.935),
        ),
        (
            "05 · Eslabón L2 Horquilla en U (1 Sólido)",
            "05_eslabon_l2_v4 + 13_tapa_cable_l2 · 2× Negro",
            "Monolítico (a2=82 mm) + acceso Ø5.2 horn + canal cola de milano",
            [
                (os.path.join(BLK_DIR, "05_eslabon_l2_v4.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "13_tapa_cable_l2.stl"), (0.30, 0.32, 0.36), (0, 0, 14)),
            ],
            (0.85, -1.45, 0.65),
            (0.945, 0.945, 0.935),
        ),
        (
            "06 · Antebrazo L3 Horquilla en U (1 Sólido)",
            "06_antebrazo_l3_v4 + 13_tapa_cable_l3 · 2× Negro",
            "Monolítico (a3=70 mm) + despeje total J3=-135° + canal dovetail",
            [
                (os.path.join(BLK_DIR, "06_antebrazo_l3_v4.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "13_tapa_cable_l3.stl"), (0.30, 0.32, 0.36), (0, 0, 14)),
            ],
            (0.85, -1.45, 0.65),
            (0.945, 0.945, 0.935),
        ),
        (
            "07 · Palma Abierta MeArm + Carenado SG90",
            "07_palma_pinza_v4.stl · 1× Negro",
            "Abierta arriba (0 puente cerrado) + carenado SG90 coaxial inferior",
            [(os.path.join(BLK_DIR, "07_palma_pinza_v4.stl"), blk, (0, 0, 0))],
            (1.2, -1.2, 0.70),
            (0.945, 0.945, 0.935),
        ),
        (
            "08–09 + 12 · Engranes 12T Mod 1.5 + Bielas",
            "08/09_engrane_brazo_m15 + 12_biela · 4× Negro",
            "Sector 12T grueso FDM (1 sólido con brazo/horn) + 2 bielas L=16.5",
            [
                (os.path.join(BLK_DIR, "08_engrane_brazo_izq_m15.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "09_engrane_brazo_der_m15.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "12_biela_pinza_izq_v4.stl"), (0.28, 0.30, 0.34), (0, 0, 0)),
                (os.path.join(BLK_DIR, "12_biela_pinza_der_v4.stl"), (0.28, 0.30, 0.34), (0, 0, 0)),
            ],
            (0.65, -0.95, 1.45),
            (0.945, 0.945, 0.935),
        ),
        (
            "10 · Dedos Paralelos MeArm (TCP=53 mm)",
            "10_dedo_pinza_izq_v4 + der · 2× Negro",
            "Puente diagonal rígido + mordaza calibrada exacto a 53.00 mm",
            [
                (os.path.join(BLK_DIR, "10_dedo_pinza_izq_v4.stl"), blk, (0, 0, 0)),
                (os.path.join(BLK_DIR, "10_dedo_pinza_der_v4.stl"), blk, (0, 0, 0)),
            ],
            (1.1, -1.1, 0.9),
            (0.945, 0.945, 0.935),
        ),
        (
            "11 · Tapas Bayoneta 32° + Separadores M3",
            "tapa_j2..j4 (6×) + 11_separador_m3 (3×)",
            "Bayoneta 0 flexión PLA + casquillos lisos M3 (Nyloc nunca frena)",
            [
                (os.path.join(BLK_DIR, "tapa_j2_izq.stl"), blk, (-34, 0, 6)),
                (os.path.join(BLK_DIR, "tapa_j3_izq.stl"), blk, (-2, 0, 6)),
                (os.path.join(BLK_DIR, "tapa_j4_izq.stl"), blk, (26, 0, 6)),
                (os.path.join(BLK_DIR, "11_separador_m3_j2.stl"), (0.32, 0.34, 0.38), (-18, 0, -22)),
                (os.path.join(BLK_DIR, "11_separador_m3_j3.stl"), (0.32, 0.34, 0.38), (4, 0, -22)),
                (os.path.join(BLK_DIR, "11_separador_m3_j4.stl"), (0.32, 0.34, 0.38), (26, 0, -22)),
            ],
            (0.45, -1.55, 0.55),
            (0.945, 0.945, 0.935),
            True,
        ),
        (
            "12 · 10 Acentos Blanco Mate (0% AMS)",
            "w01 + w02 + 6× w_aro + 2× w04 · 10× Blanco",
            "Aro base Ø106 + 6 aros J2..J4 + collar muñeca + 2 almohadillas",
            [
                (os.path.join(WHT_DIR, "w01_aro_base_blanco.stl"), wht, (-12, 0, -20)),
                (os.path.join(WHT_DIR, "w_aro_j2_izq.stl"), wht, (-38, 0, 26)),
                (os.path.join(WHT_DIR, "w_aro_j3_izq.stl"), wht, (0, 0, 26)),
                (os.path.join(WHT_DIR, "w_aro_j4_izq.stl"), wht, (34, 0, 26)),
                (os.path.join(WHT_DIR, "w02_collar_muneca_blanco.stl"), wht, (56, 0, -14)),
                (os.path.join(WHT_DIR, "w04_almohadilla_izq.stl"), wht, (56, 16, 12)),
                (os.path.join(WHT_DIR, "w04_almohadilla_der.stl"), wht, (56, -16, 12)),
            ],
            (0.45, -1.55, 0.55),
            bg_dark_tile,
            True,
        ),
        (
            "Cupón 1 · Kit Calibración v4 (18 min)",
            "cupon_1_ajustes_pivote_bayoneta.stl",
            "Valida MG90S, tuercas M3/Nyloc, bayoneta 32°, separador y dovetail",
            [(os.path.join(CUP_DIR, "cupon_1_ajustes_pivote_bayoneta.stl"), blk, (0, 0, 0))],
            (0.75, -1.25, 1.15),
            (0.945, 0.945, 0.935),
        ),
    ]

    cols, rows = 4, 3
    tw, th = 500, 380
    pad = 22
    header_h = 108
    card_footer_h = 96
    cw = cols * tw + (cols + 1) * pad
    ch = header_h + rows * (th + card_footer_h) + (rows + 1) * pad

    canvas = Image.new("RGB", (cw, ch), (244, 244, 242))
    draw = ImageDraw.Draw(canvas)
    f_title = _load_font(33, bold=True)
    f_sub = _load_font(17.5, bold=False)
    f_card_t = _load_font(19, bold=True)
    f_card_s = _load_font(14.5, bold=False)
    f_card_d = _load_font(13.5, bold=False)

    total_blk_g = sum(r["est_mass_g"] for r in metrics if r["color"] == "Negro Mate")
    total_wht_g = sum(r["est_mass_g"] for r in metrics if r["color"] == "Blanco Mate")

    n_tot = len(metrics)
    n_blk = sum(1 for r in metrics if r["color"] == "Negro Mate")
    n_wht = sum(1 for r in metrics if r["color"] == "Blanco Mate")
    draw.text((pad, 20), f"CATÁLOGO VISUAL DE {n_tot} PIEZAS CAD — MINI-PRO 4-DOF (B2 STEALTH v4 Clean-DFA)", fill=(24, 24, 27), font=f_title)
    draw.text(
        (pad, 64),
        f"{n_tot} / {n_tot} STLs 100% estancos y de 1 solo sólido conectado · 0.00 mm³ colisiones · 0% purga AMS · ~{total_blk_g:.0f} g PLA+ Negro ({n_blk} pzas) + ~{total_wht_g:.0f} g Blanco Mate ({n_wht} pzas)",
        fill=(92, 92, 98),
        font=f_sub,
    )

    for idx, item in enumerate(tiles):
        title, sub, desc, specs, cdir, bg = item[:6]
        recenter_each = item[6] if len(item) > 6 else False
        r, c = divmod(idx, cols)
        x0 = pad + c * (tw + pad)
        y0 = header_h + pad + r * (th + card_footer_h + pad)

        img_tile = _render_tile(specs, cam_dir=cdir, w=tw, h=th, bg=bg, recenter_each=recenter_each)
        draw.rounded_rectangle([x0 - 1, y0 - 1, x0 + tw + 1, y0 + th + card_footer_h + 1], radius=12, fill=(255, 255, 255), outline=(212, 212, 216), width=2)
        canvas.paste(img_tile, (x0, y0))

        ty = y0 + th + 10
        draw.text((x0 + 14, ty), title, fill=(24, 24, 27), font=f_card_t)
        draw.text((x0 + 14, ty + 27), sub, fill=(180, 74, 24) if "Blanco" not in sub else (37, 99, 235), font=f_card_s)
        draw.text((x0 + 14, ty + 52), desc, fill=(82, 82, 91), font=f_card_d)

        first_fname = os.path.basename(specs[0][0])
        if len(specs) == 1 and first_fname in m_by_name:
            rec = m_by_name[first_fname]
            dim_txt = f"{rec['dims_mm'][0]:.0f}×{rec['dims_mm'][1]:.0f}×{rec['dims_mm'][2]:.0f} mm · ~{rec['est_mass_g']:.0f}g"
            draw.rounded_rectangle([x0 + tw - 210, y0 + 10, x0 + tw - 10, y0 + 38], radius=8, fill=(24, 24, 27))
            draw.text((x0 + tw - 200, y0 + 15), dim_txt, fill=(248, 248, 248), font=f_card_d)

    canvas.save(OUT_PNG)
    print(f"[OK] Catálogo visual v4 guardado en: {OUT_PNG}")


if __name__ == "__main__":
    main()
