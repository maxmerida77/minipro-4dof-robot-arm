"""
Generador de Video Demo Corto (1440×840 @ 30 FPS, H.264 MP4) — Mini-Pro 4-DOF (`B2 Stealth`)
============================================================================================
Usa directamente el Gemelo Digital 3D Real (`python/gemelo_digital_esp32.py`, CAD v3.1 con
35 STLs + 19 componentes internos) para renderizar un video corto (~25 s) mostrando:
  1. Presentación exterior B2 Stealth (órbita suave)
  2. Vista Rayos-X de todos los componentes internos (4× MG90S, SG90, 4× 608ZZ, XIAO, PCA9685, AR5515)
  3. Barrido individual de cada articulación: J1 Base, J2 Hombro, J3 Codo, J4 Muñeca
  4. Zoom a la Pinza Paralela de 4 Barras (SG90 coaxial + 14T + bielas) abriendo y cerrando

Salida:
  - docs/renders/demo_articulaciones_b2_stealth.mp4  (H.264 yuv420p compatible universal)
"""

import math
import os
import shutil
import subprocess
import sys
import numpy as np
import vtk
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gemelo_digital_esp32 as gd

OUT_MP4 = os.path.join(ROOT, "docs", "renders", "demo_articulaciones_b2_stealth.mp4")
FPS = 30
WIN_W, WIN_H = 1440, 840

# Pose Héroe CAD v3.1 (horizontal φ = 0°)
Q_HERO = np.array([0.0, 68.0, -96.0, 28.0], dtype=float)
G_HERO = 16.0

CAM_HERO_POS = np.array([365.0, -375.0, 270.0])
CAM_HERO_FOC = np.array([58.0, 0.0, 108.0])


def smooth5(u: float) -> float:
    """Interpolador quíntico mínimo-jerk (0 -> 1 con velocidad y aceleración nulas en extremos)."""
    u = max(0.0, min(1.0, float(u)))
    return u * u * u * (10.0 - 15.0 * u + 6.0 * u * u)


def lerp(a, b, u: float):
    s = smooth5(u)
    return a * (1.0 - s) + b * s


def osc(center: float, lo: float, hi: float, u: float) -> float:
    """Va suave: center -> hi -> lo -> center en u ∈ [0, 1]."""
    if u < 0.28:
        return lerp(center, hi, u / 0.28)
    elif u < 0.72:
        return lerp(hi, lo, (u - 0.28) / 0.44)
    else:
        return lerp(lo, center, (u - 0.72) / 0.28)


def orbit_pos(center, radius, az_deg, el_deg):
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    return np.array([
        center[0] + radius * math.cos(el) * math.cos(az),
        center[1] + radius * math.cos(el) * math.sin(az),
        center[2] + radius * math.sin(el),
    ])


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("No se encontró ffmpeg en el sistema.") from exc


def load_fonts():
    try:
        f_title = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 21)
        f_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 14)
        f_tag = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 13)
    except Exception:
        f_title = f_sub = f_tag = ImageFont.load_default()
    return f_title, f_sub, f_tag


def draw_hud_overlay(rgb_arr: np.ndarray, stage_title: str, stage_sub: str,
                     badge: str, progress: float, fonts) -> bytes:
    """Agrega un encabezado minimalista estilo B2 Stealth y barra de progreso en el viewport 3D."""
    img = Image.fromarray(rgb_arr, mode="RGB").convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    f_title, f_sub, f_tag = fonts

    # Tarjeta translúcida superior izquierda (dentro del viewport 3D: x ∈ [0..1020])
    bx0, by0, bx1, by1 = 22, 18, 690, 88
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=12, fill=(15, 23, 42, 220), outline=(51, 65, 85, 235), width=2)

    # Indicador naranja activo + badge
    draw.ellipse([bx0 + 16, by0 + 16, bx0 + 28, by0 + 28], fill=(234, 88, 12, 255))
    draw.text((bx0 + 38, by0 + 10), stage_title, fill=(248, 250, 252, 255), font=f_title)
    draw.text((bx0 + 38, by0 + 42), stage_sub, fill=(148, 163, 184, 255), font=f_sub)

    # Píldora derecha dentro de la tarjeta
    if badge:
        tw = draw.textlength(badge, font=f_tag)
        px0 = bx1 - tw - 28
        draw.rounded_rectangle([px0, by0 + 12, bx1 - 14, by0 + 36], radius=10, fill=(234, 88, 12, 235))
        draw.text((px0 + 7, by0 + 15), badge, fill=(255, 255, 255, 255), font=f_tag)

    # Barra sutil de progreso al fondo del viewport 3D (x = 0 .. 1036)
    bar_w = int(WIN_W * 0.72)
    draw.rectangle([0, WIN_H - 5, bar_w, WIN_H], fill=(30, 41, 59, 170))
    draw.rectangle([0, WIN_H - 5, max(4, int(bar_w * progress)), WIN_H], fill=(234, 88, 12, 245))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    return out.tobytes()


def build_timeline():
    """Define las 7 escenas (~25.5 s totales) sin pick-and-place: solo vista, internos y articulaciones."""
    # Cada segmento: (duracion_s, func(u) -> dict)
    segs = []

    # 1. Presentación exterior B2 Stealth (3.5 s)
    def s1_intro(u):
        az = lerp(-46.0, -24.0, u)
        el = lerp(26.0, 22.0, u)
        pos = orbit_pos(CAM_HERO_FOC, 520.0, az, el)
        return dict(
            q=Q_HERO.copy(), grip=G_HERO, opacity=1.0, show_hw=False, show_kin=True,
            active_slider=None, cam_pos=pos, cam_foc=CAM_HERO_FOC,
            title="MINI-PRO 4-DOF · B2 STEALTH",
            sub="Modelo CAD v3.1 (35 piezas estancas · 0.00 mm³ colisiones)",
            badge="4-DOF + PINZA",
        )
    segs.append((3.5, s1_intro))

    # 2. Rayos-X + Componentes Internos Reales (5.5 s)
    def s2_xray(u):
        # Transición suave de opacidad 1.0 -> 0.22 -> 0.22 -> 1.0
        if u < 0.14:
            op = lerp(1.0, 0.22, u / 0.14)
        elif u > 0.88:
            op = lerp(0.22, 1.0, (u - 0.88) / 0.12)
        else:
            op = 0.22

        # Cámara: paneo elegante bajando a la base electrónica (0..0.48) y subiendo hacia servos J2-J4/SG90 (0.48..1.0)
        if u < 0.48:
            t = u / 0.48
            foc = lerp(CAM_HERO_FOC, np.array([10.0, 0.0, 48.0]), t)
            az = lerp(-24.0, -145.0, t)
            el = lerp(22.0, 26.0, t)
            rad = lerp(520.0, 340.0, t)
            sub = "Base: XIAO ESP32-S3 · PCA9685 · AR5515 PD 5V · KCD11 · MG90S J1 + 22T:22T"
        else:
            t = (u - 0.48) / 0.52
            foc = lerp(np.array([10.0, 0.0, 48.0]), CAM_HERO_FOC, t)
            az = lerp(-145.0, -46.0, t)
            el = lerp(26.0, 26.0, t)
            rad = lerp(340.0, 520.0, t)
            sub = "Brazo: 4× MG90S ocultos · 4× rodamientos 608ZZ · SG90 coaxial en pinza"

        return dict(
            q=Q_HERO.copy(), grip=G_HERO, opacity=op, show_hw=True, show_kin=False,
            active_slider=None, cam_pos=orbit_pos(foc, rad, az, el), cam_foc=foc,
            title="COMPONENTES INTERNOS · VISTA RAYOS-X",
            sub=sub,
            badge="19 INTERNOS",
        )
    segs.append((5.5, s2_xray))

    # 3. J1 Base Yaw (3.5 s)
    def s3_j1(u):
        q = Q_HERO.copy()
        q[0] = osc(0.0, -72.0, +72.0, u)
        return dict(
            q=q, grip=G_HERO, opacity=1.0, show_hw=False, show_kin=True,
            active_slider=0, cam_pos=CAM_HERO_POS, cam_foc=CAM_HERO_FOC,
            title="ARTICULACIÓN J1 · BASE YAW",
            sub="Giro ±90° · MG90S + transmisión 22T:22T con chaveta en D + 608ZZ",
            badge="J1 · CH0",
        )
    segs.append((3.5, s3_j1))

    # 4. J2 Hombro Pitch (3.0 s)
    def s4_j2(u):
        q = Q_HERO.copy()
        q[1] = osc(Q_HERO[1], 40.0, 118.0, u)
        return dict(
            q=q, grip=G_HERO, opacity=1.0, show_hw=False, show_kin=True,
            active_slider=1, cam_pos=CAM_HERO_POS, cam_foc=CAM_HERO_FOC,
            title="ARTICULACIÓN J2 · HOMBRO PITCH",
            sub="Rango [+15°, +165°] · MG90S oculto + buje 608ZZ con tornillo M3",
            badge="J2 · CH1",
        )
    segs.append((3.0, s4_j2))

    # 5. J3 Codo Pitch (3.0 s)
    def s5_j3(u):
        q = Q_HERO.copy()
        q[2] = osc(Q_HERO[2], -125.0, -25.0, u)
        return dict(
            q=q, grip=G_HERO, opacity=1.0, show_hw=False, show_kin=True,
            active_slider=2, cam_pos=CAM_HERO_POS, cam_foc=CAM_HERO_FOC,
            title="ARTICULACIÓN J3 · CODO PITCH",
            sub="Rango [-135°, +45°] · Eslabón a₂=82 mm + antebrazo a₃=70 mm",
            badge="J3 · CH2",
        )
    segs.append((3.0, s5_j3))

    # 6. J4 Muñeca Pitch (2.8 s)
    def s6_j4(u):
        q = Q_HERO.copy()
        q[3] = osc(Q_HERO[3], -62.0, +72.0, u)
        return dict(
            q=q, grip=G_HERO, opacity=1.0, show_hw=False, show_kin=True,
            active_slider=3, cam_pos=CAM_HERO_POS, cam_foc=CAM_HERO_FOC,
            title="ARTICULACIÓN J4 · MUÑECA PITCH (4.º EJE)",
            sub="Rango [-90°, +90°] · Controla el ángulo φ del efector final (a₄=53 mm)",
            badge="J4 · CH3",
        )
    segs.append((2.8, s6_j4))

    # 7. Zoom Pinza Paralela de 4 Barras (4.2 s)
    grip_foc = np.array([128.0, 0.0, 128.0])
    grip_pos = np.array([235.0, -175.0, 215.0])

    def s7_grip(u):
        # Zoom in (0..0.20), 2 ciclos apertura/cierre (0.15..0.82), zoom out final a Hero (0.82..1.0)
        if u < 0.20:
            c_pos = lerp(CAM_HERO_POS, grip_pos, u / 0.20)
            c_foc = lerp(CAM_HERO_FOC, grip_foc, u / 0.20)
        elif u > 0.82:
            t = (u - 0.82) / 0.18
            c_pos = lerp(grip_pos, CAM_HERO_POS, t)
            c_foc = lerp(grip_foc, CAM_HERO_FOC, t)
        else:
            # Sutil órbita cenital para apreciar engranes 14T y bielas traseras
            t = (u - 0.20) / 0.62
            az = lerp(-58.0, -28.0, t)
            el = lerp(34.0, 44.0, t)
            c_pos = orbit_pos(grip_foc, 218.0, az, el)
            c_foc = grip_foc

        # Apertura: 16 -> 28 -> 2 -> 28 -> 2 -> 16 mm
        if u < 0.18:
            g = lerp(16.0, 28.0, u / 0.18)
        elif u < 0.40:
            g = lerp(28.0, 2.0, (u - 0.18) / 0.22)
        elif u < 0.62:
            g = lerp(2.0, 28.0, (u - 0.40) / 0.22)
        elif u < 0.82:
            g = lerp(28.0, 2.0, (u - 0.62) / 0.20)
        else:
            g = lerp(2.0, 16.0, (u - 0.82) / 0.18)

        return dict(
            q=Q_HERO.copy(), grip=g, opacity=1.0, show_hw=False, show_kin=False,
            active_slider=4, cam_pos=c_pos, cam_foc=c_foc,
            title="EFECTOR FINAL · PINZA PARALELA 4 BARRAS",
            sub="SG90 coaxial + engranes-brazo 14T + 2 bielas traseras (0–30 mm)",
            badge="PINZA · CH4",
        )
    segs.append((4.2, s7_grip))

    return segs


def main():
    os.makedirs(os.path.dirname(OUT_MP4), exist_ok=True)
    ffmpeg_exe = find_ffmpeg()
    fonts = load_fonts()

    # Inicializar el Gemelo Digital 3D real en modo offscreen
    link = gd.ArmLink()
    app = gd.DigitalTwinApp(link=link, offscreen=True)
    app.win.SetSize(WIN_W, WIN_H)
    app.win.SetMultiSamples(4)

    segs = build_timeline()
    total_s = sum(d for d, _ in segs)
    total_frames = int(round(total_s * FPS))
    print(f"[INFO] Renderizando {total_frames} frames ({total_s:.1f} s @ {FPS} FPS, {WIN_W}x{WIN_H}) -> {OUT_MP4}")

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{WIN_W}x{WIN_H}",
        "-r", str(FPS),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        OUT_MP4,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(app.win)
    w2i.SetInputBufferTypeToRGB()
    w2i.ReadFrontBufferOff()

    cam = app.ren3d.GetActiveCamera()
    cam.SetViewUp(0.0, 0.0, 1.0)
    cam.SetViewAngle(32.0)

    # Precalcular tiempos acumulados
    bounds = []
    t_acc = 0.0
    for dur, fn in segs:
        bounds.append((t_acc, t_acc + dur, dur, fn))
        t_acc += dur

    # También guardar 3 keyframes de inspección rápida (X-Ray base, J2 movimiento, Zoom pinza)
    keyframe_indices = {
        int(total_frames * 0.22): os.path.join(ROOT, "docs", "renders", "_kf_xray.png"),
        int(total_frames * 0.56): os.path.join(ROOT, "docs", "renders", "_kf_joint.png"),
        int(total_frames * 0.90): os.path.join(ROOT, "docs", "renders", "_kf_grip.png"),
    }

    try:
        for f_idx in range(total_frames):
            t_cur = f_idx / float(FPS)
            st = None
            for t0, t1, dur, fn in bounds:
                if t_cur <= t1 or fn is bounds[-1][3]:
                    u = (t_cur - t0) / max(1e-6, dur)
                    st = fn(max(0.0, min(1.0, u)))
                    break

            # Aplicar visibilidad / rayos-X
            op = st["opacity"]
            for act in app.plastic_actors:
                act.GetProperty().SetOpacity(op)
            for act in app.hw_actors:
                act.SetVisibility(bool(st["show_hw"]))
            for act in app.kin_actors:
                act.SetVisibility(bool(st["show_kin"]))

            # Aplicar pose y slider activo
            app.q_deg = st["q"]
            app.grip_mm = float(st["grip"])
            app.active_slider = st["active_slider"]

            cam.SetFocalPoint(*st["cam_foc"])
            cam.SetPosition(*st["cam_pos"])
            app.ren3d.ResetCameraClippingRange()

            app.update_pose(transmit=False)

            w2i.Modified()
            w2i.Update()
            vimg = w2i.GetOutput()
            dims = vimg.GetDimensions()
            arr = np.frombuffer(vimg.GetPointData().GetScalars(), dtype=np.uint8).reshape(dims[1], dims[0], 3)
            arr = np.flipud(arr)

            frame_bytes = draw_hud_overlay(
                arr,
                st["title"],
                st["sub"],
                st["badge"],
                f_idx / max(1, total_frames - 1),
                fonts,
            )
            proc.stdin.write(frame_bytes)

            if f_idx in keyframe_indices:
                Image.frombytes("RGB", (WIN_W, WIN_H), frame_bytes).save(keyframe_indices[f_idx])

            if (f_idx + 1) % 150 == 0 or f_idx == total_frames - 1:
                print(f"  Progreso: {f_idx + 1}/{total_frames} frames ({100.0*(f_idx+1)/total_frames:.0f}%)")
    finally:
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="replace")
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg falló (code {ret}):\n{stderr[-800:]}")

    size_mb = os.path.getsize(OUT_MP4) / (1024 * 1024)
    print(f"[OK] Video generado exitosamente: {OUT_MP4} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
