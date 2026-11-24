"""
Render 4 Paneles de Estudio — CAD v4 Clean-DFA (`B2 Stealth`)
=============================================================
Genera un tablero técnico de 4 vistas VTK en alta resolución (`docs/renders/renders_v4_clean_dfa.png`)
usando directamente los STLs reales verificados de `cad/exports/v4_clean_dfa/`:
  1. Pose Héroe 3/4 `B2 Stealth` (estética monocromática intacta + 10 piezas Blanco Mate)
  2. Corte Rayos-X interno (MG90S J1 coaxial + PCA9685 con Dupont + XIAO + AR5515 + KCD11 + SG90)
  3. Vista Explosionada Clean-DFA (retén axial J1, separadores M3, bayonetas 32°, tapas dovetail)
  4. Macro Pinza Paralela Abierta MeArm Módulo 1.5 (sector 12T + paralelogramo + TCP = 53.00 mm)
"""

import os
import sys
import numpy as np
import vtk
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from visor_cad_interactivo import PART_META, HW_META, BLK_DIR, WHT_DIR, HW_DIR

OUT_PNG = os.path.join(ROOT, "docs", "renders", "renders_v4_clean_dfa.png")


def _load_actor(fpath, rgb, opacity=1.0, offset=(0, 0, 0)):
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
    p.SetAmbient(0.22)
    p.SetDiffuse(0.78)
    p.SetSpecular(0.22)
    p.SetSpecularPower(26.0)
    p.SetOpacity(opacity)
    return a


def _render_scene(cam_pos, cam_focal, view_angle=30.0, xray=False, exploded=False, show_hw=True, size=(760, 560)):
    ren = vtk.vtkRenderer()
    ren.SetBackground(0.95, 0.95, 0.96)
    ren.SetBackground2(0.86, 0.87, 0.90)
    ren.GradientBackgroundOn()

    # Disco escritorio Z=0
    disk = vtk.vtkCylinderSource()
    disk.SetRadius(135.0)
    disk.SetHeight(1.2)
    disk.SetResolution(80)
    tf = vtk.vtkTransform()
    tf.RotateX(90.0)
    tf.Translate(35.0, 0.0, -0.7)
    tpf = vtk.vtkTransformPolyDataFilter()
    tpf.SetInputConnection(disk.GetOutputPort())
    tpf.SetTransform(tf)
    md = vtk.vtkPolyDataMapper()
    md.SetInputConnection(tpf.GetOutputPort())
    ad = vtk.vtkActor()
    ad.SetMapper(md)
    ad.GetProperty().SetColor(0.87, 0.86, 0.84)
    ad.GetProperty().SetOpacity(0.55)
    ren.AddActor(ad)

    op = 0.24 if xray else 1.0
    for folder, rgb in [(BLK_DIR, (0.14, 0.14, 0.17)), (WHT_DIR, (0.97, 0.97, 0.96))]:
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".stl"):
                continue
            off = PART_META.get(fname, (1, "", (0, 0, 0)))[2] if exploded else (0, 0, 0)
            ren.AddActor(_load_actor(os.path.join(folder, fname), rgb, opacity=op, offset=off))

    if show_hw:
        for fname in sorted(os.listdir(HW_DIR)):
            if not fname.endswith(".stl"):
                continue
            meta = HW_META.get(fname, (5, (0.74, 0.76, 0.80), "", (86, 0, 62)))
            off = meta[3] if exploded else (0, 0, 0)
            ren.AddActor(_load_actor(os.path.join(HW_DIR, fname), meta[1], opacity=1.0, offset=off))

    ren.AutomaticLightCreationOff()
    for pos, inten in [((380, -340, 420), 0.94), ((-300, -240, 260), 0.48), ((0, 360, 240), 0.36)]:
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
    arr = np.frombuffer(vimg.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], -1)
    arr = np.flipud(arr)
    return Image.fromarray(arr[:, :, :3])


def main():
    tw, th = 760, 540
    panels = [
        (
            _render_scene((285, -310, 225), (48, 0, 96), 31.0, xray=False, exploded=False, show_hw=True, size=(tw, th)),
            "1 · POSE HÉROE B2 STEALTH v4 (0°, 68°, -96°, 28°, g=15 mm)",
            "Estética monocromática intacta (10 pzas Blancas, 0% AMS) · Base Ø106 mm + 6 patas perimetrales",
        ),
        (
            _render_scene((275, -285, 200), (45, 0, 92), 30.0, xray=True, exploded=False, show_hw=True, size=(tw, th)),
            "2 · RAYOS-X INTERNO (0.0000 mm³ CON HERRAJES, NYLOCS Y LASTRE)",
            "Bóveda lastre 247 g bajo bandeja aislante · Mamparo Nyloc J2/J3/J4 · PCA9685 + Dupont (23 mm) · 4× MG90S + SG90",
        ),
        (
            _render_scene((375, -420, 280), (55, 0, 108), 32.0, xray=False, exploded=True, show_hw=True, size=(tw, th)),
            "3 · EXPLOSIONADO CLEAN-DFA (42/42 SÓLIDOS ÚNICOS CONECTADOS)",
            "Bandeja aislante · Retén axial J1 · Horquillas U monolíticas L2/L3 · 10 Casquillos M3 · Bayonetas 32° · Dovetail",
        ),
        (
            _render_scene((195, -135, 195), (132, 0, 128), 26.0, xray=False, exploded=False, show_hw=True, size=(tw, th)),
            "4 · MACRO PINZA PARALELA ABIERTA MeArm MÓDULO 1.5 (12T + 7 CASQUILLOS)",
            "SG90 a +Y · Avellanado M3×16 · Nylocs sobre pilares palma · Punto agarre w04 = (53.000, +5.800) mm",
        ),
    ]

    pad = 22
    header_h = 92
    cap_h = 54
    W = tw * 2 + pad * 3
    H = header_h + 2 * (th + cap_h + pad) + pad
    board = Image.new("RGB", (W, H), (244, 246, 249))
    draw = ImageDraw.Draw(board)
    try:
        f_h1 = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
        f_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15.5)
        f_t = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 16.5)
        f_s = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 13.5)
    except Exception:
        f_h1 = f_sub = f_t = f_s = ImageFont.load_default()

    draw.rectangle([0, 0, W, header_h], fill=(15, 23, 42))
    draw.text((pad, 16), "MINI-PRO 4-DOF B2 STEALTH — CAD v4 Clean-DFA VERIFICADO (RONDA 2 · GO)", fill=(248, 250, 252), font=f_h1)
    draw.text((pad, 54), "DH 82/82/70/53 mm · 42/42 STLs 1-sólido estancos · 0.0000 mm³ en 8 auditorías B-Rep (tol=0.01 mm³) · Masa móvil ~122 g", fill=(148, 163, 184), font=f_sub)

    for idx, (im, title, sub) in enumerate(panels):
        r, c = divmod(idx, 2)
        x0 = pad + c * (tw + pad)
        y0 = header_h + pad + r * (th + cap_h + pad)
        draw.rounded_rectangle([x0 - 2, y0 - 2, x0 + tw + 2, y0 + th + cap_h + 2], radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        board.paste(im, (x0, y0))
        draw.text((x0 + 12, y0 + th + 6), title, fill=(15, 23, 42), font=f_t)
        draw.text((x0 + 12, y0 + th + 30), sub, fill=(71, 85, 105), font=f_s)

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    board.save(OUT_PNG)
    print(f"[OK] Tablero 4 vistas CAD v4 guardado: {OUT_PNG}")


if __name__ == "__main__":
    main()
