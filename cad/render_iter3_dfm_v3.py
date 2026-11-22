"""
Renderizador de Validación DFM — CAD v3 (Revisión A + B + C · Ensamble Real)
Genera el tablero técnico 2×2 en `docs/renders/renders_iter3_dfm_v3.png`:
  1. Revisión A: Detalle Articulación J2/J3 (acceso +Y MG90S, bolsillo horn, buje 608ZZ M3, ducto cables).
  2. Revisión B: Pinza Paralela Real de 4 Barras (SG90 coaxial, engranes-brazo 14T, 2× bielas, doble pivote M3).
  3. Revisión C: Base y Transmisión J1 (eje con corte en D + 22T, postes PCA9685 barrenados, XIAO/AR5515).
  4. Vista Héroe Exterior B2 Stealth v3 Final (estética intacta, cero plástico azul visible).
"""

import os
import shutil
import numpy as np
import vtk
from PIL import Image, ImageDraw

from mini_pro_b2_stealth_v3 import build_cad_v3
from render_iter2b_vtk import cq_shape_to_vtk_polydata, make_actor, add_studio_desk, setup_studio_lights, load_font

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS_RENDERS = os.path.join(ROOT, "docs", "renders")
ART_DIR = os.environ.get("ARTIFACT_DIR", "")


def _render_panel(parts_dict, cam_pos, focal_pt, view_up=(0, 0, 1), size=(1300, 940), show_desk=False, only_keys=None, servo_idxs=None, show_elec=False, steel_idxs=None, clip_y0=False):
    ren = vtk.vtkRenderer()
    ren.GradientBackgroundOn()
    ren.SetBackground(0.95, 0.95, 0.94)
    ren.SetBackground2(0.88, 0.89, 0.90)

    plane = vtk.vtkPlane()
    plane.SetOrigin(0, 0, 0)
    plane.SetNormal(0, 1, 0)

    def add_list(shapes, rgb, amb=0.25, dif=0.80, spec=0.22, sp=26.0, clip=False):
        for s in shapes:
            pd = cq_shape_to_vtk_polydata(s, tol=0.04, ang_tol=0.09)
            if clip:
                cp = vtk.vtkClipPolyData()
                cp.SetInputData(pd)
                cp.SetClipFunction(plane)
                cp.Update()
                pd = cp.GetOutput()
            act = make_actor(pd, rgb, ambient=amb, diffuse=dif, specular=spec, spec_power=sp)
            ren.AddActor(act)

    if only_keys is None:
        add_list(parts_dict["black"], (0.16, 0.165, 0.175), clip=clip_y0)
        add_list(parts_dict["white"], (0.97, 0.97, 0.96), amb=0.34, dif=0.75, spec=0.14, clip=clip_y0)
    else:
        b_sel = [v for k, v in parts_dict["black_named"].items() if any(k.startswith(p) for p in only_keys)]
        w_sel = [v for k, v in parts_dict["white_named"].items() if any(k.startswith(p) for p in only_keys)]
        add_list(b_sel, (0.17, 0.175, 0.185), clip=clip_y0)
        add_list(w_sel, (0.97, 0.97, 0.96), amb=0.34, dif=0.75, spec=0.14, clip=clip_y0)

    if servo_idxs:
        add_list([parts_dict["servos"][i] for i in servo_idxs if i < len(parts_dict["servos"])], (0.14, 0.44, 0.78), amb=0.26, dif=0.78, spec=0.30)
    if show_elec:
        add_list(parts_dict["elec_pcb"], (0.12, 0.56, 0.30), amb=0.26, dif=0.78, spec=0.22)
    if steel_idxs is not None:
        add_list([parts_dict["steel"][i] for i in steel_idxs if i < len(parts_dict["steel"])], (0.72, 0.74, 0.78), amb=0.24, dif=0.68, spec=0.58, sp=55.0)

    if show_desk:
        add_studio_desk(ren)
    setup_studio_lights(ren)

    cam = ren.GetActiveCamera()
    cam.SetPosition(*cam_pos)
    cam.SetFocalPoint(*focal_pt)
    cam.SetViewUp(*view_up)
    cam.SetViewAngle(30.0)
    ren.ResetCameraClippingRange()

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(size[0], size[1])
    win.SetMultiSamples(4)
    win.Render()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    vtk_img = w2i.GetOutput()
    w, h, _ = vtk_img.GetDimensions()
    arr = np.frombuffer(vtk_img.GetPointData().GetScalars(), dtype=np.uint8).reshape(h, w, 3)
    arr = np.flipud(arr)
    win.Finalize()
    return Image.fromarray(arr)


def main():
    os.makedirs(DOCS_RENDERS, exist_ok=True)
    p_assy = build_cad_v3(explode=0.0)
    p_exp = build_cad_v3(explode=0.85)

    # Panel 1: Revisión A — Detalle explosionado J2 / L2 (acceso +Y MG90S, bolsillo horn, buje 608ZZ M3, ducto cables)
    img_a = _render_panel(
        p_exp,
        cam_pos=(165, 195, 225),
        focal_pt=(35, 0, 148),
        only_keys=("04_torreta", "05_eslabon", "11_buje_608zz_j2", "11_buje_608zz_j3", "tapa_j2", "w_aro_j2"),
        servo_idxs=[1, 2],
        steel_idxs=[6, 7, 8, 9, 10, 11],
    )

    # Panel 2: Revisión B — Pinza Paralela Real de 4 Barras (pila Z sin colisiones: SG90 coaxial + 14T + bielas + puente)
    img_b = _render_panel(
        p_exp,
        cam_pos=(270, -110, 265),
        focal_pt=(198, 0, 184),
        only_keys=("07_palma", "08_engrane", "09_engrane", "10_dedo", "12_biela", "w02_", "w03_", "w04_"),
        servo_idxs=[4],
        steel_idxs=list(range(21, len(p_exp["steel"]))),
    )

    # Panel 3: Revisión C — Corte Base Fija + Eje en D + Engrane 22T + Postes PCA9685 barrenados + Cuna XIAO
    img_c = _render_panel(
        p_exp,
        cam_pos=(155, -210, 92),
        focal_pt=(0, 0, 22),
        only_keys=("01_base", "02_pinon", "03_tapa", "04_torreta", "04b_engrane", "w01_"),
        servo_idxs=[0],
        show_elec=True,
        steel_idxs=[0, 1, 2, 3, 4, 5],
        clip_y0=True,
    )

    # Panel 4: Vista Héroe Exterior B2 Stealth v3 Final (estética intacta, cero plástico azul visible)
    img_hero = _render_panel(
        p_assy,
        cam_pos=(270, -290, 215),
        focal_pt=(58, 0, 96),
        show_desk=True,
    )

    # Composición 2×2
    tw, th = 1220, 880
    pad_x, gap_x, gap_y = 48, 34, 34
    top_h, foot_h = 132, 92
    W = pad_x * 2 + tw * 2 + gap_x
    H = top_h + th * 2 + foot_h * 2 + gap_y + 42

    board = Image.new("RGB", (W, H), (244, 244, 242))
    draw = ImageDraw.Draw(board)
    f_title = load_font(40, bold=True)
    f_sub = load_font(21, bold=False)
    f_card = load_font(23, bold=True)
    f_desc = load_font(16, bold=False)

    draw.text((pad_x, 28), "CAD v3 (DFM / ENSAMBLE REAL) — REVISIONES A + B + C", font=f_title, fill=(24, 24, 27))
    draw.text(
        (pad_x, 82),
        "35 piezas STL 100% estancas · Ejes metálicos M3 + bujes 608ZZ · Bolsillos de horn · Pinza 4 barras coaxial SG90 · Chaveta en D 22T",
        font=f_sub,
        fill=(92, 92, 98),
    )

    cards = [
        (img_a, "1 · Revisión A — Articulaciones J2/J3/J4 Ensamblables", "Acceso trasero +Y para MG90S con orejas, bolsillo horn en disco, buje 608ZZ + M3 y ducto continuo de cables"),
        (img_b, "2 · Revisión B — Pinza Paralela Real de 4 Barras (SG90 Coaxial)", "SG90 coaxial bajo engrane-brazo 14T izquierdo + 2 bielas traseras L=16 mm + dedos con doble pivote M3"),
        (img_c, "3 · Revisión C — Base Fija, Transmisión 22T en D y Electrónica", "Eje con corte plano en D en 04_torreta + 04b_engrane 22T, 4 postes PCA9685 barrenados, retenedor XIAO/AR5515"),
        (img_hero, "4 · Vista Héroe Exterior — B2 Stealth v3 Definitivo", "Silueta minimalista 100% intacta · Cero plástico azul visible · 23 Negro Mate + 12 Blanco Mate (0% purga AMS)"),
    ]

    for idx, (im, title, desc) in enumerate(cards):
        r, c = divmod(idx, 2)
        x0 = pad_x + c * (tw + gap_x)
        y0 = top_h + r * (th + foot_h + gap_y)
        draw.rounded_rectangle((x0, y0, x0 + tw, y0 + th + foot_h), radius=16, fill=(255, 255, 255), outline=(212, 212, 216), width=2)
        board.paste(im.resize((tw - 6, th - 6), Image.Resampling.LANCZOS), (x0 + 3, y0 + 3))
        draw.text((x0 + 20, y0 + th + 12), title, font=f_card, fill=(24, 24, 27))
        draw.text((x0 + 20, y0 + th + 46), desc, font=f_desc, fill=(88, 88, 95))

    out_path = os.path.join(DOCS_RENDERS, "renders_iter3_dfm_v3.png")
    board.save(out_path, "PNG", optimize=True)
    if ART_DIR and os.path.isdir(ART_DIR):
        shutil.copy2(out_path, os.path.join(ART_DIR, "renders_iter3_dfm_v3.png"))
    print("Saved CAD v3 DFM board:", out_path)


if __name__ == "__main__":
    main()
