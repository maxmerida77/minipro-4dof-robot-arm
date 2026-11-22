"""
Renderizador de Validación Final — Iteración 2B (CAD v2 · 100% UNIT Electronics · B2 Stealth)
Genera el tablero 2x2 de inspección mecánica completa:
  1. Corte Transversal Y=0: demuestra encapsulado 100% interno de los 4× MG90S, 1× SG90 y 4× 608ZZ.
  2. Interior de la Base (Planta): distribución sin colisiones de XIAO ESP32-S3, AR5515 USB-C PD,
     KCD11-2P ON/OFF, PCA9685, Capacitor 1000µF, 608ZZ y J1 MG90S + piñón 22T.
  3. Detalle Panel Trasero de la Base: muestra los 3 controles al ras (USB-C XIAO, USB-C PD 5V
     para cargador UGREEN 50W, y botón negro ON/OFF KCD11-2P).
  4. Vista Héroe Exterior B2 Stealth v2: confirma cero plástico azul visible y estética final.
"""

import os
import shutil
import numpy as np
import vtk
from vtk.util import numpy_support
from PIL import Image, ImageDraw, ImageFont

from mini_pro_b2_stealth_v2 import build_cad_v2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS_RENDERS = os.path.join(ROOT, "docs", "renders")
ART_DIR = os.environ.get("ARTIFACT_DIR", "")


def cq_shape_to_vtk_polydata(cq_wp, tol=0.04, ang_tol=0.08):
    shape = cq_wp.val()
    verts, tris = shape.tessellate(tol, ang_tol)
    points = vtk.vtkPoints()
    for v in verts:
        points.InsertNextPoint(v.x, v.y, v.z)
    cells = vtk.vtkCellArray()
    for t in tris:
        cells.InsertNextCell(3)
        cells.InsertCellPoint(t[0])
        cells.InsertCellPoint(t[1])
        cells.InsertCellPoint(t[2])
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.SetFeatureAngle(35.0)
    normals.SplittingOn()
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.Update()
    return normals.GetOutput()


def make_actor(polydata, color_rgb, ambient=0.22, diffuse=0.80, specular=0.22, spec_power=26.0):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*color_rgb)
    prop.SetAmbient(ambient)
    prop.SetDiffuse(diffuse)
    prop.SetSpecular(specular)
    prop.SetSpecularPower(spec_power)
    prop.SetInterpolationToPhong()
    return actor


def add_studio_desk(renderer):
    N = 512
    x_lin = np.linspace(-320.0, 480.0, N)
    y_lin = np.linspace(-400.0, 400.0, N)
    xx, yy = np.meshgrid(x_lin, y_lin)
    grain = 0.018 * np.sin(yy * 0.14 + 1.8 * np.sin(xx * 0.015)) + 0.008 * np.sin(yy * 0.42)
    base_r = np.clip(0.87 + grain, 0.0, 1.0)
    base_g = np.clip(0.80 + grain * 0.9, 0.0, 1.0)
    base_b = np.clip(0.70 + grain * 0.7, 0.0, 1.0)
    r_base = np.hypot(xx - 3.0, yy - 2.0)
    sh_tight = 0.42 * np.exp(-0.5 * (np.maximum(0.0, r_base - 44.0) / 14.0) ** 2)
    sh_soft = 0.18 * np.exp(-0.5 * (r_base / 66.0) ** 2)
    r_arm = np.hypot((xx - 115.0) * 0.72, (yy - 8.0) * 1.15)
    sh_arm = 0.14 * np.exp(-0.5 * (r_arm / 55.0) ** 2)
    shadow = np.clip(1.0 - np.maximum(sh_tight, sh_soft) - sh_arm, 0.40, 1.0)
    rgb = np.stack([base_r * shadow, base_g * shadow, base_b * shadow], axis=-1)
    rgb_u8 = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    vtk_img = vtk.vtkImageData()
    vtk_img.SetDimensions(N, N, 1)
    vtk_arr = numpy_support.numpy_to_vtk(rgb_u8.reshape(-1, 3), deep=True, array_type=vtk.VTK_UNSIGNED_CHAR)
    vtk_img.GetPointData().SetScalars(vtk_arr)
    tex = vtk.vtkTexture()
    tex.SetInputData(vtk_img)
    tex.InterpolateOn()
    plane = vtk.vtkPlaneSource()
    plane.SetOrigin(-320.0, -400.0, -0.15)
    plane.SetPoint1(480.0, -400.0, -0.15)
    plane.SetPoint2(-320.0, 400.0, -0.15)
    plane.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(plane.GetOutputPort())
    act = vtk.vtkActor()
    act.SetMapper(mapper)
    act.SetTexture(tex)
    act.GetProperty().SetAmbient(0.55)
    act.GetProperty().SetDiffuse(0.55)
    act.GetProperty().SetSpecular(0.04)
    renderer.AddActor(act)


def setup_studio_lights(renderer):
    renderer.RemoveAllLights()
    for pos, foc, col, inten in [
        ((-180, -340, 380), (60, 0, 95), (1.0, 0.99, 0.97), 0.95),
        ((360, -240, 210), (60, 0, 95), (0.93, 0.96, 1.0), 0.60),
        ((40, 360, 260), (55, 0, 105), (1.0, 1.0, 1.0), 0.65),
    ]:
        lt = vtk.vtkLight()
        lt.SetLightTypeToSceneLight()
        lt.SetPosition(*pos)
        lt.SetFocalPoint(*foc)
        lt.SetColor(*col)
        lt.SetIntensity(inten)
        renderer.AddLight(lt)


def load_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _add_group(ren, shapes, color_rgb, ambient=0.25, diffuse=0.80, specular=0.22, spec_power=26.0, clip_plane=None):
    for s in shapes:
        pd = cq_shape_to_vtk_polydata(s, tol=0.05, ang_tol=0.10)
        if clip_plane is not None:
            clipper = vtk.vtkClipPolyData()
            clipper.SetInputData(pd)
            clipper.SetClipFunction(clip_plane)
            clipper.Update()
            pd = clipper.GetOutput()
        ren.AddActor(make_actor(pd, color_rgb, ambient=ambient, diffuse=diffuse, specular=specular, spec_power=spec_power))


def render_v1_view(parts, cam_pos, focal_pt, view_up=(0, 0, 1), size=(1300, 960), show_desk=True, clip_plastic_plane=None, hide_upper_z=None):
    ren = vtk.vtkRenderer()
    ren.GradientBackgroundOn()
    ren.SetBackground(0.95, 0.95, 0.94)
    ren.SetBackground2(0.89, 0.90, 0.89)

    def maybe_filter_z(shape_list):
        if hide_upper_z is None:
            return shape_list
        return [s for s in shape_list if s.val().BoundingBox().zmin < hide_upper_z]

    _add_group(ren, maybe_filter_z(parts["black"]), (0.165, 0.168, 0.175), ambient=0.25, diffuse=0.80, specular=0.24, spec_power=28.0, clip_plane=clip_plastic_plane)
    _add_group(ren, maybe_filter_z(parts["white"]), (0.96, 0.96, 0.95), ambient=0.32, diffuse=0.76, specular=0.14, spec_power=20.0, clip_plane=clip_plastic_plane)
    _add_group(ren, maybe_filter_z(parts["servos"]), (0.16, 0.44, 0.74), ambient=0.28, diffuse=0.78, specular=0.30, spec_power=30.0)
    _add_group(ren, maybe_filter_z(parts["elec_pcb"]), (0.12, 0.56, 0.30), ambient=0.30, diffuse=0.75, specular=0.25, spec_power=24.0)
    _add_group(ren, maybe_filter_z(parts["steel"]), (0.70, 0.72, 0.75), ambient=0.26, diffuse=0.65, specular=0.62, spec_power=54.0)

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
    win.SetMultiSamples(8)
    win.SetSize(*size)
    win.AddRenderer(ren)
    win.Render()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.SetInputBufferTypeToRGB()
    w2i.ReadFrontBufferOff()
    w2i.Update()

    vtk_img = w2i.GetOutput()
    w, h, _ = vtk_img.GetDimensions()
    arr = np.frombuffer(vtk_img.GetPointData().GetScalars(), dtype=np.uint8).reshape(h, w, 3)
    img = Image.fromarray(np.flipud(arr))
    win.Finalize()
    return img


def annotate_base_top_v2(img: Image.Image) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    f = load_font("segoeuib.ttf", 20)
    labels = [
        ((245, 705), "XIAO ESP32-S3 (USB-C)", (20, 115, 58)),
        ((245, 455), "USB-C PD AR5515 (5V UGREEN)", (20, 115, 58)),
        ((245, 255), "Botón ON/OFF KCD11-2P", (30, 30, 36)),
        ((635, 165), "PCA9685 (16-ch I2C)", (20, 115, 58)),
        ((960, 480), "Servo J1 MG90S + Piñón 22T", (24, 88, 165)),
        ((660, 815), "608ZZ Central + Ranura Cables", (75, 78, 84)),
    ]
    for (cx, cy), text, col in labels:
        bbox = draw.textbbox((0, 0), text, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        bw, bh = tw + 18, th + 12
        x0, y0 = cx - bw // 2, cy - bh // 2
        draw.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=8, fill=(255, 255, 255), outline=col, width=2)
        draw.text((x0 + 9 - bbox[0], y0 + 6 - bbox[1]), text, font=f, fill=col)
    return out


def annotate_rear_panel(img: Image.Image) -> Image.Image:
    out = img.copy()
    draw = ImageDraw.Draw(out)
    f = load_font("segoeuib.ttf", 21)
    # Mirando desde -X hacia +X: +Y (KCD11-2P) queda a la IZQUIERDA, AR5515 al CENTRO, -Y (XIAO) a la DERECHA
    labels = [
        ((275, 780), "1 · Botón ON/OFF KCD11-2P", (30, 30, 36)),
        ((650, 865), "2 · USB-C PD 5V AR5515 (1 cable UGREEN 50W)", (20, 115, 58)),
        ((1000, 780), "3 · USB-C XIAO ESP32 (Programación)", (24, 88, 165)),
    ]
    for (cx, cy), text, col in labels:
        bbox = draw.textbbox((0, 0), text, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        bw, bh = tw + 18, th + 12
        x0, y0 = cx - bw // 2, cy - bh // 2
        draw.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=8, fill=(255, 255, 255), outline=col, width=2)
        draw.text((x0 + 9 - bbox[0], y0 + 6 - bbox[1]), text, font=f, fill=col)
    return out


def main():
    os.makedirs(DOCS_RENDERS, exist_ok=True)
    parts = build_cad_v2(explode=0.0)

    # 1. Corte Transversal Y = 0 (carcasas recortadas para ver los 4× MG90S, 1× SG90 y 4× 608ZZ adentro)
    clip_y = vtk.vtkPlane()
    clip_y.SetOrigin(0.0, -1.0, 0.0)
    clip_y.SetNormal(0.0, 1.0, 0.0)
    img_cut = render_v1_view(
        parts,
        cam_pos=(155, -340, 155),
        focal_pt=(52, 0, 86),
        show_desk=False,
        clip_plastic_plane=clip_y,
    )

    # 2. Distribución Interna de la Base (Planta Z < 36.5 mm)
    clip_z = vtk.vtkPlane()
    clip_z.SetOrigin(0.0, 0.0, 36.5)
    clip_z.SetNormal(0.0, 0.0, -1.0)
    img_base_raw = render_v1_view(
        parts,
        cam_pos=(-12, -25, 235),
        focal_pt=(-2, 0, 14),
        view_up=(0, 1, 0),
        show_desk=False,
        clip_plastic_plane=clip_z,
        hide_upper_z=44.5,
    )
    img_base = annotate_base_top_v2(img_base_raw)

    # 3. Acercamiento Panel Trasero de la Base (-X mirando hacia +X)
    img_rear_raw = render_v1_view(
        parts,
        cam_pos=(-235, -38, 86),
        focal_pt=(-20, 0, 42),
        show_desk=True,
    )
    img_rear = annotate_rear_panel(img_rear_raw)

    # 4. Vista Héroe Exterior B2 Stealth v2 (Cero azul visible!)
    img_hero = render_v1_view(
        parts,
        cam_pos=(185, -325, 190),
        focal_pt=(58, 0, 88),
        show_desk=True,
    )

    # Componer tablero 2x2 de validación CAD v2
    f_title = load_font("segoeuib.ttf", 40)
    f_sub = load_font("segoeui.ttf", 22)
    f_card = load_font("segoeuib.ttf", 25)
    f_desc = load_font("segoeui.ttf", 19)

    tw, th = 1160, 856
    pad_x, gap_x, gap_y = 54, 38, 42
    top_h, foot_h, bot_pad = 128, 78, 48
    cw = pad_x * 2 + tw * 2 + gap_x
    ch = top_h + (th + foot_h) * 2 + gap_y + bot_pad

    board = Image.new("RGB", (cw, ch), (246, 246, 244))
    draw = ImageDraw.Draw(board)
    ink = (24, 24, 27)
    muted = (98, 98, 106)

    draw.text((pad_x, 32), "ITERACIÓN 2B — CAD v2 IMPRIMIBLE (100% UNIT ELECTRONICS · B2 STEALTH)", font=f_title, fill=ink)
    draw.text((pad_x, 84), "4× MG90S + 1× SG90 + 4× 608ZZ + XIAO ESP32-S3 + PCA9685 + USB-C PD AR5515 (UGREEN 50W) + Botón KCD11-2P", font=f_sub, fill=muted)

    cards = [
        (img_cut, "1 · Corte Transversal (Encapsulado 100% Interno)", "MG90S alojados a lo largo de cada eslabón + SG90 100% oculto por carenado inferior + 4× rodamientos 608ZZ"),
        (img_base, "2 · Planta Interior de la Base (Ø 94 mm — Cero Colisiones)", "AR5515 elevado sobre zona plana del PCA9685 · XIAO al ras trasero · KCD11-2P · Cap 1000µF · J1 + piñón 22T"),
        (img_rear, "3 · Panel Trasero Integrado (1 Solo Cable + ON/OFF)", "Bahía trasera limpia con USB-C de XIAO, USB-C PD 5V (cargador UGREEN 50W) y botón negro KCD11-2P"),
        (img_hero, "4 · Vista Héroe Exterior — B2 Stealth v2 Final", "Escala compacta ~23 cm (d1=82, a2=82, a3=70, a4=53 mm) · 100% negro mate + aros blancos · cero piezas visibles"),
    ]

    for idx, (im, title, desc) in enumerate(cards):
        r, c = divmod(idx, 2)
        x0 = pad_x + c * (tw + gap_x)
        y0 = top_h + r * (th + foot_h + gap_y)
        draw.rounded_rectangle((x0, y0, x0 + tw, y0 + th + foot_h), radius=18, fill=(255, 255, 255), outline=(215, 215, 220), width=2)
        resized = im.resize((tw - 6, th - 6), Image.Resampling.LANCZOS)
        board.paste(resized, (x0 + 3, y0 + 3))
        draw.text((x0 + 22, y0 + th + 10), title, font=f_card, fill=ink)
        draw.text((x0 + 22, y0 + th + 43), desc, font=f_desc, fill=muted)

    out_docs = os.path.join(DOCS_RENDERS, "renders_iter2b_cad_v2.png")
    board.save(out_docs, "PNG", optimize=True)
    if ART_DIR and os.path.isdir(ART_DIR):
        shutil.copy2(out_docs, os.path.join(ART_DIR, "renders_iter2b_cad_v2.png"))
    print("Saved Iter 2B CAD v2 verification board:", out_docs)


if __name__ == "__main__":
    main()
