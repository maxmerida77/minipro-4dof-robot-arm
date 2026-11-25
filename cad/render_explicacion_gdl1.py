"""
Diagrama Didáctico Detallado de GDL 1 (Base Coaxial J1) — 6 Piezas + Corte Transversal
======================================================================================
Genera `docs/renders/explicacion_gdl1_capas.png`:
  - Arriba (2×3 tarjetas grandes): cada una de las 6 piezas imprimibles de GDL 1 por separado,
    en el orden exacto de abajo hacia arriba (como capas), mostrando la cara útil donde entran
    lastre, PCBs, servo, tornillos y el retén.
  - Abajo: Corte real por la mitad (sección Y=0) de GDL 1 armado + vista exterior armada,
    mostrando exactamente cómo encaja cada capa y por qué la torreta gira sin salirse.
"""

import os
import sys
import numpy as np
import vtk
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXP = os.path.join(HERE, "exports", "v4_clean_dfa")
BLK_DIR = os.path.join(EXP, "stl_negro_mate")
WHT_DIR = os.path.join(EXP, "stl_blanco_mate")
HW_DIR = os.path.join(EXP, "hardware_ref")
OUT_PNG = os.path.join(ROOT, "docs", "renders", "explicacion_gdl1_capas.png")


def _load_font(size: int, bold: bool = False):
    for p in [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _render_single_part(stl_path, rgb, cam_dir, bg=(0.945, 0.955, 0.97), w=540, h=360, flip_z=False):
    r = vtk.vtkSTLReader()
    r.SetFileName(stl_path)
    r.Update()
    poly = r.GetOutput()
    b = poly.GetBounds()
    cx, cy, cz = 0.5 * (b[0] + b[1]), 0.5 * (b[2] + b[3]), 0.5 * (b[4] + b[5])
    diag = max(18.0, float(np.linalg.norm([b[1] - b[0], b[3] - b[2], b[5] - b[4]])))

    tf = vtk.vtkTransform()
    if flip_z:
        tf.RotateX(180.0)
    tf.Translate(-cx, -cy, -cz)
    tpf = vtk.vtkTransformPolyDataFilter()
    tpf.SetInputData(poly)
    tpf.SetTransform(tf)
    tpf.Update()

    n = vtk.vtkPolyDataNormals()
    n.SetInputConnection(tpf.GetOutputPort())
    n.SetFeatureAngle(35.0)
    n.SplittingOn()
    n.Update()

    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*rgb)
    p.SetAmbient(0.26)
    p.SetDiffuse(0.76)
    p.SetSpecular(0.22)
    p.SetSpecularPower(26.0)

    ren = vtk.vtkRenderer()
    ren.SetBackground(*bg)
    ren.AddActor(a)
    ren.AutomaticLightCreationOff()
    for pos, inten in [
        ((diag * 2.2, -diag * 2.0, diag * 2.4), 0.96),
        ((-diag * 2.0, -diag * 1.4, diag * 1.3), 0.48),
        ((0.0, diag * 2.4, diag * 1.1), 0.36),
    ]:
        lt = vtk.vtkLight()
        lt.SetLightTypeToSceneLight()
        lt.SetPosition(*pos)
        lt.SetFocalPoint(0, 0, 0)
        lt.SetIntensity(inten)
        ren.AddLight(lt)

    cam = ren.GetActiveCamera()
    dv = np.array(cam_dir, dtype=float)
    dv = dv / np.linalg.norm(dv) * (diag * 1.55)
    cam.SetPosition(*dv)
    cam.SetFocalPoint(0, 0, 0)
    cam.SetViewUp(0, 0, 1)
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
    vimg = w2i.GetOutput()
    dims = vimg.GetDimensions()
    arr = np.frombuffer(vimg.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], 3)
    win.Finalize()
    return Image.fromarray(np.flipud(arr))


def _render_cutaway(w=820, h=430):
    """Corte real por la mitad (plano Y = 0, mostrando mitad +Y) de todo GDL 1 con colores didácticos por capa!"""
    plane = vtk.vtkPlane()
    plane.SetOrigin(0.0, 0.0, 0.0)
    plane.SetNormal(0.0, 1.0, 0.0)  # Conserva la mitad Y >= 0 (corte limpio de frente!)

    # Colores didácticos ligeramente diferenciados por capa para distinguir instantáneamente cada pieza!
    part_specs = [
        (os.path.join(BLK_DIR, "03_tapa_inferior_v4.stl"),         (0.22, 0.25, 0.30)),  # Gris pizarra oscuro
        (os.path.join(BLK_DIR, "03b_bandeja_electronica_v4.stl"),  (0.16, 0.52, 0.44)),  # Verde azulado (bandeja aislante)
        (os.path.join(BLK_DIR, "01_base_fija_v4.stl"),             (0.14, 0.15, 0.19)),  # Negro Stealth (base fija)
        (os.path.join(WHT_DIR, "w01_aro_base_blanco.stl"),         (0.98, 0.98, 0.98)),  # Blanco puro (aro w01)
        (os.path.join(BLK_DIR, "04b_reten_axial_j1.stl"),          (0.88, 0.42, 0.14)),  # Naranja (retén axial J1!)
        (os.path.join(BLK_DIR, "04_torreta_j1_hombro_v4.stl"),     (0.26, 0.28, 0.34)),  # Carbón medio (torreta giratoria)
        (os.path.join(HW_DIR,  "hw_servo_00.stl"),                 (0.12, 0.48, 0.88)),  # Azul servo MG90S J1
        (os.path.join(HW_DIR,  "hw_elec_00.stl"),                  (0.10, 0.60, 0.28)),  # AR5515
        (os.path.join(HW_DIR,  "hw_elec_01.stl"),                  (0.08, 0.48, 0.22)),  # Bornera
        (os.path.join(HW_DIR,  "hw_elec_02.stl"),                  (0.10, 0.62, 0.30)),  # PCA9685
        (os.path.join(HW_DIR,  "hw_elec_03.stl"),                  (0.10, 0.52, 0.26)),  # XIAO
        (os.path.join(HW_DIR,  "hw_elec_04.stl"),                  (0.14, 0.34, 0.62)),  # Cap 1000uF
        (os.path.join(HW_DIR,  "hw_steel_21.stl"),                 (0.92, 0.76, 0.24)),  # Duponts 23 mm (dorado guía)
    ]
    for i in range(3, 9):
        part_specs.append((os.path.join(HW_DIR, f"hw_steel_{i:02d}.stl"), (0.58, 0.60, 0.64)))  # 6 discos lastre
    for i in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 23, 24, 25):
        part_specs.append((os.path.join(HW_DIR, f"hw_steel_{i:02d}.stl"), (0.82, 0.84, 0.88)))  # Tornillos/tuercas

    ren = vtk.vtkRenderer()
    ren.SetBackground(0.955, 0.962, 0.975)
    ren.SetBackground2(0.86, 0.88, 0.92)
    ren.GradientBackgroundOn()

    for fpath, rgb in part_specs:
        r = vtk.vtkSTLReader()
        r.SetFileName(fpath)
        r.Update()
        clip = vtk.vtkClipPolyData()
        clip.SetInputConnection(r.GetOutputPort())
        clip.SetClipFunction(plane)
        clip.InsideOutOff()
        clip.Update()
        n = vtk.vtkPolyDataNormals()
        n.SetInputConnection(clip.GetOutputPort())
        n.SetFeatureAngle(35.0)
        n.SplittingOn()
        n.Update()
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(n.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        p = a.GetProperty()
        p.SetColor(*rgb)
        p.SetAmbient(0.28)
        p.SetDiffuse(0.74)
        p.SetSpecular(0.18)
        p.SetSpecularPower(22.0)
        # Caras traseras visibles del corte en tono más claro para lectura de sección
        bp = vtk.vtkProperty()
        bp.SetColor(min(1.0, rgb[0] * 1.15 + 0.08), min(1.0, rgb[1] * 1.15 + 0.08), min(1.0, rgb[2] * 1.15 + 0.08))
        bp.SetAmbient(0.35)
        bp.SetDiffuse(0.65)
        a.SetBackfaceProperty(bp)
        ren.AddActor(a)

    ren.AutomaticLightCreationOff()
    for pos, inten in [((120, -280, 140), 0.95), ((-180, -220, 180), 0.55), ((0, -200, -80), 0.30)]:
        lt = vtk.vtkLight()
        lt.SetLightTypeToSceneLight()
        lt.SetPosition(*pos)
        lt.SetFocalPoint(0, 0, 44)
        lt.SetIntensity(inten)
        ren.AddLight(lt)

    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(0.0, 0.0, 46.0)
    cam.SetPosition(12.0, -235.0, 62.0)
    cam.SetViewUp(0.0, 0.0, 1.0)
    cam.SetViewAngle(30.0)
    ren.ResetCameraClippingRange()

    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(w, h)
    win.SetMultiSamples(4)
    win.Render()

    # Proyectar puntos clave para poner flechas con texto limpio
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    callouts = [
        ((0, 0, 82),   "6. TORRETA J1 (gira ±85°)", (-265, -22), (30, 41, 59)),
        ((44, 0, 45.5),"5. ARO BLANCO w01 + PISTA Ø88", (185, -18), (37, 99, 235)),
        ((16, 0, 38.8),"4. RETÉN AXIAL (naranja) + 3×M3×8", (170, 22), (217, 95, 14)),
        ((0, 4, 23),   "MG90S J1 (motor centrado)", (-265, 22), (18, 92, 184)),
        ((24, 0, 32.0),"DUPONTS + PCA9685 (+0.65 mm libre!)", (165, 62), (180, 120, 12)),
        ((32, 0, 11.2),"2. BANDEJA AISLANTE (verde) + 4×M3×4", (155, 112), (15, 118, 110)),
        ((-26, 0, 5.5),"1. TAPA + BÓVEDA LASTRE (≥215 g)", (-275, 120), (51, 65, 85)),
    ]
    pts_2d = []
    for world_pt, lbl, off_xy, col in callouts:
        coord.SetValue(*world_pt)
        dx, dy = coord.GetComputedDisplayValue(ren)
        pts_2d.append((int(dx), int(h - dy), lbl, off_xy, col))

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(win)
    w2i.Update()
    vimg = w2i.GetOutput()
    dims = vimg.GetDimensions()
    arr = np.frombuffer(vimg.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], 3)
    img = Image.fromarray(np.flipud(arr))
    win.Finalize()

    draw = ImageDraw.Draw(img)
    f_lbl = _load_font(14.5, bold=True)
    for px, py, lbl, (ox, oy), col in pts_2d:
        tx = max(12, min(w - 295, px + ox))
        ty = max(12, min(h - 32, py + oy))
        draw.line([(px, py), (tx + (240 if ox < 0 else 0), ty + 10)], fill=col, width=2)
        draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=col, outline=(255, 255, 255), width=1)
        tw = draw.textlength(lbl, font=f_lbl)
        bx0 = tx - 6
        bx1 = tx + tw + 8
        if bx1 > w - 8:
            shift = bx1 - (w - 8)
            bx0 -= shift; bx1 -= shift; tx -= shift
        draw.rounded_rectangle([bx0, ty - 2, bx1, ty + 23], radius=6, fill=(255, 255, 255), outline=col, width=2)
        draw.text((tx, ty + 1), lbl, fill=col, font=f_lbl)
    return img


def main():
    blk = (0.24, 0.27, 0.32)
    wht = (0.97, 0.97, 0.96)
    bg_light = (0.945, 0.952, 0.968)
    bg_dark = (0.19, 0.21, 0.26)

    cards = [
        (
            "CAPA 1 · 03_tapa_inferior_v4",
            "El PISO y la CAJA DEL LASTRE (12.2 g · 0 soportes)",
            "Aquí metes las rondanas/monedas (≥215 g) para que no se voltee.",
            "Por abajo lleva pegadas las 6 gomitas antideslizantes Ø10 mm.",
            _render_single_part(os.path.join(BLK_DIR, "03_tapa_inferior_v4.stl"), blk, (0.8, -1.1, 1.35), bg_light),
            (16, 185, 129),
        ),
        (
            "CAPA 2 · 03b_bandeja_electronica_v4",
            "El PISO AISLANTE de la Electrónica (9.8 g · 0 soportes)",
            "Va ENCIMA del lastre para que el metal jamás toque los circuitos.",
            "Aquí se atornilla el PCA9685 (4×M3×4), la XIAO y el capacitor.",
            _render_single_part(os.path.join(BLK_DIR, "03b_bandeja_electronica_v4.stl"), (0.16, 0.48, 0.42), (0.8, -1.1, 1.35), bg_light),
            (15, 118, 110),
        ),
        (
            "CAPA 3 · 01_base_fija_v4 (vista interior boca arriba)",
            "La CARCASA FIJA que sostiene al motor J1 (43.4 g)",
            "Tiene la cuna central del MG90S J1, 4 tuercas M3, y ranuras atrás",
            "para USB-C (AR5515), botón ON/OFF (KCD11) y puerto XIAO.",
            _render_single_part(os.path.join(BLK_DIR, "01_base_fija_v4.stl"), blk, (0.85, -1.15, 1.15), bg_light, flip_z=True),
            (234, 88, 12),
        ),
        (
            "CAPA 4 · 04b_reten_axial_j1",
            "La ARANDELA DE SEGURIDAD que sujeta la torreta (2.8 g)",
            "Se atornilla POR DENTRO al cuello de la torreta con 3× M3×8.",
            "Evita que la torreta se levante al girar sin cargar al horn del servo!",
            _render_single_part(os.path.join(BLK_DIR, "04b_reten_axial_j1.stl"), (0.88, 0.42, 0.14), (0.7, -1.0, 1.45), bg_light, flip_z=True),
            (217, 95, 14),
        ),
        (
            "CAPA 5 · w01_aro_base_blanco",
            "El ARO ESTÉTICO BLANCO (3.7 g · 0% purga AMS)",
            "Solo se sienta en el borde superior de la base fija (sin tornillos).",
            "Da la línea blanca limpia estilo B2 Stealth entre base y torreta.",
            _render_single_part(os.path.join(WHT_DIR, "w01_aro_base_blanco.stl"), wht, (0.7, -1.1, 1.25), bg_dark),
            (37, 99, 235),
        ),
        (
            "CAPA 6 · 04_torreta_j1_hombro_v4",
            "La TORRETA GIRATORIA ±85° (92.6 g · parte móvil)",
            "Se apoya y gira sobre la pista Ø88 mm; su cuello entra en la base.",
            "Arriba ya trae listo el alojamiento donde luego montaremos el GDL 2!",
            _render_single_part(os.path.join(BLK_DIR, "04_torreta_j1_hombro_v4.stl"), blk, (1.1, -1.25, 0.75), bg_light),
            (234, 88, 12),
        ),
    ]

    cut_img = _render_cutaway(w=1040, h=460)

    tw, th = 540, 340
    cap_h = 98
    pad = 22
    header_h = 92
    W = tw * 3 + pad * 4
    bot_h = 460 + 54
    H = header_h + pad + 2 * (th + cap_h + pad) + bot_h + pad

    canvas = Image.new("RGB", (W, H), (244, 246, 249))
    draw = ImageDraw.Draw(canvas)
    f_h1 = _load_font(27, bold=True)
    f_sub = _load_font(15.5, bold=False)
    f_ct = _load_font(17.5, bold=True)
    f_cs = _load_font(14.5, bold=True)
    f_cd = _load_font(13.5, bold=False)

    draw.rectangle([0, 0, W, header_h], fill=(15, 23, 42))
    draw.text((pad, 16), "¿CÓMO FUNCIONA EL PRIMER GRADO (GDL 1)? — LAS 6 PIEZAS CAPA POR CAPA", fill=(248, 250, 252), font=f_h1)
    draw.text((pad, 54), "Capas 1–3 y 5 son FIJAS · Capas 4 y 6 GIRAN juntas · Nota: al imprimir, Capas 1–4 y 6 son PLA+ Negro y solo Capa 5 es Blanco (aquí usamos colores guía).", fill=(148, 163, 184), font=f_sub)

    for idx, (title, sub, d1, d2, im, col) in enumerate(cards):
        r, c = divmod(idx, 3)
        x0 = pad + c * (tw + pad)
        y0 = header_h + pad + r * (th + cap_h + pad)
        draw.rounded_rectangle([x0 - 2, y0 - 2, x0 + tw + 2, y0 + th + cap_h + 2], radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        im_rs = im.resize((tw, th), Image.Resampling.LANCZOS)
        canvas.paste(im_rs, (x0, y0))
        # Badge de número
        draw.rounded_rectangle([x0 + 10, y0 + 10, x0 + 96, y0 + 38], radius=8, fill=col)
        draw.text((x0 + 20, y0 + 14), f"CAPA {idx+1}", fill=(255, 255, 255), font=f_cs)

        ty = y0 + th + 8
        draw.text((x0 + 14, ty), title, fill=(15, 23, 42), font=f_ct)
        draw.text((x0 + 14, ty + 26), sub, fill=col, font=f_cs)
        draw.text((x0 + 14, ty + 50), d1, fill=(51, 65, 85), font=f_cd)
        draw.text((x0 + 14, ty + 70), d2, fill=(51, 65, 85), font=f_cd)

    # Sección inferior: Corte real por la mitad + resumen visual de qué gira y qué queda fijo
    by0 = header_h + pad + 2 * (th + cap_h + pad)
    draw.rounded_rectangle([pad - 2, by0 - 2, W - pad + 2, by0 + bot_h], radius=12, fill=(255, 255, 255), outline=(203, 213, 225), width=2)
    canvas.paste(cut_img, (pad + 10, by0 + 10))

    # Caja explicativa a la derecha del corte transversal
    rx = pad + 10 + 1040 + 24
    rw = (W - pad - 16) - rx
    draw.rounded_rectangle([rx, by0 + 14, rx + rw, by0 + bot_h - 14], radius=10, fill=(248, 250, 252), outline=(203, 213, 225), width=2)
    draw.text((rx + 18, by0 + 28), "RESUMEN EN 10 SEGUNDOS", fill=(15, 23, 42), font=_load_font(20, bold=True))

    bullets = [
        ("¿QUÉ SE QUEDA QUIETO?", (30, 41, 59), [
            "• Capa 1 (Tapa + Lastre ≥215 g)",
            "• Capa 2 (Bandeja verde + PCA + XIAO)",
            "• Capa 3 (Base fija + MG90S J1 + botones)",
            "• Capa 5 (Aro blanco w01 decorativo)",
            "→ Todo se cierra unido con 4× M3×16!",
        ]),
        ("¿QUÉ GIRA (±85°)?", (217, 95, 14), [
            "• Capa 6 (Torreta) apoya sobre la pista Ø88",
            "• Su cuello pasa por el techo de la base",
            "• Capa 4 (Retén naranja) se atornilla por",
            "  abajo al cuello con 3× M3×8 -> hace",
            "  'sándwich' con el techo para no salirse!",
            "• El horn del MG90S solo da el giro, SIN",
            "  cargar el peso del brazo!",
        ]),
        ("CERO CORTOS NI CHOQUES", (15, 118, 110), [
            "• Retén y M3×8: +0.65 mm sobre Duponts",
            "• PCA M3×4: 1.05 mm PLA+ sobre lastre",
            "• 0.0000 mm³ colisión en todo el giro!",
        ]),
    ]
    cy = by0 + 68
    for hdr, col, lines in bullets:
        draw.text((rx + 18, cy), hdr, fill=col, font=_load_font(16, bold=True))
        cy += 24
        for ln in lines:
            draw.text((rx + 18, cy), ln, fill=(51, 65, 85), font=_load_font(14, bold=False))
            cy += 21
        cy += 12

    draw.text((pad + 18, by0 + 476), "CORTE REAL POR LA MITAD DE GDL 1 (Guía: Verde = Bandeja 03b · Naranja = Retén 04b · Dorado = Duponts · Azul = MG90S J1 · Gris = Lastre 218 g)", fill=(71, 85, 105), font=f_cd)

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    canvas.save(OUT_PNG)
    print(f"[OK] Diagrama didáctico GDL 1 guardado: {OUT_PNG}")


if __name__ == "__main__":
    main()
