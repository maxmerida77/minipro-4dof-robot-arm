"""
Gemelo Digital 3D Real — Mini-Pro 4-DOF (`B2 Stealth`) · Peter Corke Python + VTK
=================================================================================
Controla en vivo las 35 piezas 3D reales del CAD (`B2 Stealth` v3.1 DFM, 0.00 mm³ colisiones)
con cinemática exacta de Peter Corke (`roboticstoolbox-python`) y sincronización directa
hacia tu XIAO ESP32-S3 por Wi-Fi UDP o USB Serial:

    python python/gemelo_digital_esp32.py                      # Simulación 3D (DRY_RUN)
    python python/gemelo_digital_esp32.py --wifi 192.168.4.1   # Vivo por Wi-Fi UDP (1 solo cable)
    python python/gemelo_digital_esp32.py --port COM5          # Vivo por USB Serial (115200 baud)

Arquitectura cinemática real (100% idéntica al CAD v3.1):
    - 4 Grados de Libertad (4× MG90S): J1 Base Yaw · J2 Hombro · J3 Codo · J4 Muñeca
    - 1 Efector Final (1× SG90):       Pinza paralela 4 barras (0–30 mm) con engranes 14T y bielas L=16 mm
"""

import argparse
import ctypes
import math
import os
import socket
import sys
import time
import numpy as np
import vtk
import roboticstoolbox as rtb
from spatialmath import SE3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from robot_minipro_rtb import (
    MiniPro4DOF,
    D1_MM,
    A2_MM,
    A3_MM,
    A4_MM,
    BASE_DIA_MM,
    QLIM_DEG,
    Q_HERO_RAD,
    Q_HOME_RAD,
)
sys.path.insert(0, os.path.join(ROOT, "cad"))
from params import GRIP_V4, HERO_POSE_DEG, gripper_kinematics_v4

try:
    import serial
except ImportError:
    serial = None


# ============================================================================
# Puente de comunicación hacia XIAO ESP32-S3 (DRY_RUN / Wi-Fi UDP / USB Serial)
# ============================================================================
class ArmLink:
    """Puente unificado hacia la XIAO ESP32-S3/C3: DRY_RUN, USB Serial o Wi-Fi UDP."""

    def __init__(self, port: str = "", baud: int = 115200, wifi_ip: str = "", udp_port: int = 4210):
        self.ser = None
        self.sock = None
        self.udp_addr = None
        self.mode_label = "SIMULACIÓN"
        self._last_tx = 0.0

        if port and wifi_ip:
            raise ValueError("Usa solo --port O --wifi a la vez, no ambos simultáneamente.")

        if port:
            if serial is None:
                raise RuntimeError("Falta pyserial (`pip install pyserial`).")
            self.ser = serial.Serial(port, baud, timeout=0.1)
            time.sleep(1.5)
            self.mode_label = f"USB {port}"
            print(f"[LIVE-USB] Conectado a XIAO ESP32 en {port} @ {baud} baud")
        elif wifi_ip:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(0.6)
            self.udp_addr = (wifi_ip, udp_port)
            self.mode_label = f"Wi-Fi {wifi_ip}:{udp_port}"
            print(f"[LIVE-WiFi] Enviando comandos UDP a {wifi_ip}:{udp_port} (1 solo cable de potencia)")
            self._probe_wifi()
        else:
            print("[DRY_RUN] Gemelo digital 3D en modo simulación (usa --wifi <IP> o --port COMx para hardware real).")

    def _probe_wifi(self):
        try:
            self.sock.sendto(b"STATUS\n", self.udp_addr)
            data, _ = self.sock.recvfrom(256)
            print(f"[LIVE-WiFi] XIAO respondió: {data.decode('utf-8', errors='ignore').strip()}")
        except OSError:
            print("[LIVE-WiFi] Sin respuesta inmediata a STATUS (normal si la XIAO aún no está encendida o en la misma red).")

    def send_raw(self, line: str, throttle_s: float = 0.0):
        now = time.monotonic()
        if throttle_s > 0.0 and (now - self._last_tx) < throttle_s:
            return
        payload = (line.strip() + "\n").encode("ascii")
        if self.ser is not None:
            self.ser.write(payload)
            self._last_tx = now
        elif self.sock is not None:
            self.sock.sendto(payload, self.udp_addr)
            self._last_tx = now

    def send_pose(self, q_deg, grip_mm: float, throttle_s: float = 0.0):
        cmd = f"G {q_deg[0]:.2f} {q_deg[1]:.2f} {q_deg[2]:.2f} {q_deg[3]:.2f} {grip_mm:.1f}"
        self.send_raw(cmd, throttle_s=throttle_s)

    def close(self):
        if self.ser is not None:
            self.ser.close()
        if self.sock is not None:
            self.sock.close()


# ============================================================================
# Carga y rigging cinemático de las 34 piezas STL v4 Clean-DFA + 22 mallas internas
# ============================================================================
EXP_DIR = os.path.join(ROOT, "cad", "exports", "v4_clean_dfa")
BLK_DIR = os.path.join(EXP_DIR, "stl_negro_mate")
WHT_DIR = os.path.join(EXP_DIR, "stl_blanco_mate")
HW_DIR  = os.path.join(EXP_DIR, "hardware_ref")

# Pose Héroe exacta usada al exportar los STL en `cad/mini_pro_b2_stealth_v4.py`
HERO_Q2 = float(HERO_POSE_DEG["q2"])
HERO_Q3 = float(HERO_POSE_DEG["q3"])
HERO_Q4 = float(HERO_POSE_DEG["q4"])
HERO_GRIP = float(HERO_POSE_DEG["gripper_open_mm"])
P3_HERO = (A2_MM * math.cos(math.radians(HERO_Q2)), 0.0, D1_MM + A2_MM * math.sin(math.radians(HERO_Q2)))
P4_HERO = (
    P3_HERO[0] + A3_MM * math.cos(math.radians(HERO_Q2 + HERO_Q3)),
    0.0,
    P3_HERO[2] + A3_MM * math.sin(math.radians(HERO_Q2 + HERO_Q3)),
)
GEAR_LOCAL_X = float(GRIP_V4["gear_x"])
GEAR_LOCAL_Y = float(GRIP_V4["gear_y"])
IDLER_LOCAL_X = float(GRIP_V4["idler_x"])
IDLER_LOCAL_Y = float(GRIP_V4["idler_y"])
GRIP_LINK_L = float(GRIP_V4["link_l"])
HERO_GRIP_TH_DEG = gripper_kinematics_v4(HERO_GRIP)[0]

# Mapeo de cada STL a su grupo cinemático rígido (CAD v4 Clean-DFA — 34 STLs + 22 hardware)
GROUP_MAP = {
    # Base fija coaxial Ø106 mm (Mundo)
    "01_base_fija_v4.stl": "base",
    "03_tapa_inferior_v4.stl": "base",
    "w01_aro_base_blanco.stl": "base",
    "hw_servo_00.stl": "base",
    "hw_elec_00.stl": "base",
    "hw_elec_01.stl": "base",
    "hw_elec_02.stl": "base",
    "hw_elec_03.stl": "base",
    "hw_elec_04.stl": "base",
    "hw_steel_00.stl": "base",
    "hw_steel_01.stl": "base",
    "hw_steel_02.stl": "base",
    "hw_steel_03.stl": "base",
    "hw_steel_04.stl": "base",
    # Eslabón 1: Torreta Coaxial J1 + Retén Axial Independiente + Hub Hombro J2 (gira q1 en Z)
    "04_torreta_j1_hombro_v4.stl": "j1",
    "04b_reten_axial_j1.stl": "j1",
    "hw_servo_01.stl": "j1",
    # Eslabón 2: Brazo L2 Horquilla en U + Tapas Bayoneta J2 + Separador M3 J2 + Canal Dovetail (q1, q2)
    "05_eslabon_l2_v4.stl": "j2",
    "13_tapa_cable_l2.stl": "j2",
    "11_separador_m3_j2.stl": "j2",
    "tapa_j2_izq.stl": "j2",
    "tapa_j2_der.stl": "j2",
    "w_aro_j2_izq.stl": "j2",
    "w_aro_j2_der.stl": "j2",
    "hw_servo_02.stl": "j2",
    # Eslabón 3: Antebrazo L3 Horquilla en U + Tapas Bayoneta J3 + Separador M3 J3 + Canal Dovetail (q1, q2, q3)
    "06_antebrazo_l3_v4.stl": "j3",
    "13_tapa_cable_l3.stl": "j3",
    "11_separador_m3_j3.stl": "j3",
    "tapa_j3_izq.stl": "j3",
    "tapa_j3_der.stl": "j3",
    "w_aro_j3_izq.stl": "j3",
    "w_aro_j3_der.stl": "j3",
    "hw_servo_03.stl": "j3",
    # Eslabón 4: Palma abierta MeArm Mod 1.5 + Tapas Bayoneta J4 + Separador M3 J4 + SG90 coaxial (q1, q2, q3, q4)
    "07_palma_pinza_v4.stl": "j4",
    "11_separador_m3_j4.stl": "j4",
    "tapa_j4_izq.stl": "j4",
    "tapa_j4_der.stl": "j4",
    "w_aro_j4_izq.stl": "j4",
    "w_aro_j4_der.stl": "j4",
    "w02_collar_muneca_blanco.stl": "j4",
    "hw_servo_04.stl": "j4",
    "hw_steel_09.stl": "j4",
    "hw_steel_10.stl": "j4",
    "hw_steel_11.stl": "j4",
    # Efector final — Paralelogramo de 4 barras exacto MeArm Mod 1.5 (12T)
    "08_engrane_brazo_izq_m15.stl": "gear_l",
    "09_engrane_brazo_der_m15.stl": "gear_r",
    "12_biela_pinza_izq_v4.stl": "link_l",
    "12_biela_pinza_der_v4.stl": "link_r",
    "10_dedo_pinza_izq_v4.stl": "finger_l",
    "w04_almohadilla_izq.stl": "finger_l",
    "hw_steel_05.stl": "finger_l",
    "hw_steel_06.stl": "finger_l",
    "10_dedo_pinza_der_v4.stl": "finger_r",
    "w04_almohadilla_der.stl": "finger_r",
    "hw_steel_07.stl": "finger_r",
    "hw_steel_08.stl": "finger_r",
}

HW_COLORS = {
    "hw_servo_04": (0.18, 0.56, 0.88),
    "hw_servo": (0.14, 0.44, 0.78),
    "hw_elec_04": (0.14, 0.34, 0.54),
    "hw_elec": (0.12, 0.56, 0.30),
    "hw_steel_01": (0.26, 0.26, 0.30),
    "hw_steel_02": (0.22, 0.22, 0.25),
    "hw_steel": (0.72, 0.74, 0.78),
}


def _bake_transform_for_group(group: str) -> vtk.vtkTransform:
    """Devuelve la inversa de la Pose Héroe para dejar cada STL en su marco local exacto."""
    tf = vtk.vtkTransform()
    tf.PostMultiply()
    if group in ("base", "j1"):
        return tf
    if group == "j2":
        tf.Translate(0.0, 0.0, -D1_MM)
        tf.RotateY(HERO_Q2)
        return tf
    if group == "j3":
        tf.Translate(-P3_HERO[0], 0.0, -P3_HERO[2])
        tf.RotateY(HERO_Q2 + HERO_Q3)
        return tf
    if group in ("j4", "finger_l", "finger_r"):
        tf.Translate(-P4_HERO[0], 0.0, -P4_HERO[2])
        tf.RotateY(HERO_Q2 + HERO_Q3 + HERO_Q4)
        return tf
    if group == "gear_l":
        tf.Translate(-P4_HERO[0] - GEAR_LOCAL_X, -GEAR_LOCAL_Y, -P4_HERO[2])
        return tf
    if group == "gear_r":
        tf.Translate(-P4_HERO[0] - GEAR_LOCAL_X, +GEAR_LOCAL_Y, -P4_HERO[2])
        return tf
    if group == "link_l":
        tf.Translate(-P4_HERO[0] - IDLER_LOCAL_X, -IDLER_LOCAL_Y, -P4_HERO[2])
        return tf
    if group == "link_r":
        tf.Translate(-P4_HERO[0] - IDLER_LOCAL_X, +IDLER_LOCAL_Y, -P4_HERO[2])
        return tf
    return tf


def _load_baked_actor(fpath: str, group: str, rgb, is_hw: bool = False):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(fpath)
    reader.Update()

    bake = _bake_transform_for_group(group)
    tpf = vtk.vtkTransformPolyDataFilter()
    tpf.SetInputConnection(reader.GetOutputPort())
    tpf.SetTransform(bake)
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
    prop.SetDiffuse(0.76)
    prop.SetSpecular(0.22 if not is_hw else 0.30)
    prop.SetSpecularPower(26.0)
    return actor


def _add_2d_rect(ren, x0, y0, x1, y1, rgb, opacity=1.0, edge_rgb=None):
    pts = vtk.vtkPoints()
    pts.InsertNextPoint(x0, y0, 0)
    pts.InsertNextPoint(x1, y0, 0)
    pts.InsertNextPoint(x1, y1, 0)
    pts.InsertNextPoint(x0, y1, 0)
    poly = vtk.vtkPolyData()
    poly.SetPoints(pts)
    quad = vtk.vtkCellArray()
    quad.InsertNextCell(4)
    for i in range(4):
        quad.InsertCellPoint(i)
    poly.SetPolys(quad)

    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToNormalizedViewport()
    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(poly)
    mapper.SetTransformCoordinate(coord)

    act = vtk.vtkActor2D()
    act.SetMapper(mapper)
    act.GetProperty().SetColor(*rgb)
    act.GetProperty().SetOpacity(opacity)
    ren.AddActor2D(act)

    if edge_rgb is not None:
        lines = vtk.vtkCellArray()
        for a, b in [(0, 1), (1, 2), (2, 3), (3, 0)]:
            lines.InsertNextCell(2)
            lines.InsertCellPoint(a)
            lines.InsertCellPoint(b)
        epoly = vtk.vtkPolyData()
        epoly.SetPoints(pts)
        epoly.SetLines(lines)
        emap = vtk.vtkPolyDataMapper2D()
        emap.SetInputData(epoly)
        emap.SetTransformCoordinate(coord)
        eact = vtk.vtkActor2D()
        eact.SetMapper(emap)
        eact.GetProperty().SetColor(*edge_rgb)
        eact.GetProperty().SetLineWidth(1.2)
        ren.AddActor2D(eact)
    return act


def _add_2d_text(ren, text, x_norm, y_norm, size, rgb, bold=False, center=False):
    ta = vtk.vtkTextActor()
    ta.SetInput(text)
    tp = ta.GetTextProperty()
    tp.SetFontFamilyToArial()
    tp.SetFontSize(size)
    tp.SetBold(bold)
    tp.SetColor(*rgb)
    if center:
        tp.SetJustificationToCentered()
        tp.SetVerticalJustificationToCentered()
    coord = ta.GetPositionCoordinate()
    coord.SetCoordinateSystemToNormalizedViewport()
    coord.SetValue(x_norm, y_norm)
    ren.AddActor2D(ta)
    return ta


# ============================================================================
# Aplicación Principal del Gemelo Digital 3D Real
# ============================================================================
class DigitalTwinApp:
    def __init__(self, link: ArmLink, offscreen: bool = False):
        self.robot = MiniPro4DOF()
        self.link = link
        self.offscreen = offscreen

        self.q_deg = np.rad2deg(Q_HERO_RAD).astype(float)
        self.grip_mm = float(HERO_GRIP)
        self.xray = False
        self.show_hw = False
        self.show_kin = True
        self.relaxed = False
        self.active_slider = None
        self.orbiting = False
        self._dirty_render = False
        self._timer_tick = 0

        # Cola de animación no bloqueante (lista de tuplas (q_deg[4], grip_mm, cube_pos_or_None))
        self.anim_queue = []
        self.trail_pts = []
        self.cube_pos = np.array([135.0, -65.0, 12.0])
        self.cube_held = False

        # Renderizadores (Izquierda = Escena 3D, Derecha = Panel B2 Stealth)
        self.ren3d = vtk.vtkRenderer()
        self.ren3d.SetViewport(0.0, 0.0, 0.72, 1.0)
        self.ren3d.SetBackground(0.94, 0.94, 0.93)
        self.ren3d.SetBackground2(0.85, 0.86, 0.87)
        self.ren3d.GradientBackgroundOn()

        self.ren_ui = vtk.vtkRenderer()
        self.ren_ui.SetViewport(0.72, 0.0, 1.0, 1.0)
        self.ren_ui.SetBackground(0.075, 0.075, 0.09)
        self.ren_ui.InteractiveOff()

        self.win = vtk.vtkRenderWindow()
        if offscreen:
            self.win.SetOffScreenRendering(1)
        self.win.AddRenderer(self.ren3d)
        self.win.AddRenderer(self.ren_ui)
        self.win.SetSize(1380, 820)
        self.win.SetWindowName("Gemelo Digital 3D — Mini-Pro 4-DOF B2 Stealth (Peter Corke)")
        self.win.SetMultiSamples(4)

        self.iren = vtk.vtkRenderWindowInteractor()
        self.iren.SetRenderWindow(self.win)
        self.style = vtk.vtkInteractorStyleTrackballCamera()
        self.iren.SetInteractorStyle(self.style)
        # Enrutamiento limpio de eventos: quitar los observadores por defecto de TrackballCamera para
        # que el panel derecho de sliders NUNCA compita ni se quede pegado con la captura del mouse 3D.
        for evt in (
            "CharEvent",
            "LeftButtonPressEvent",
            "MouseMoveEvent",
            "LeftButtonReleaseEvent",
            "MouseWheelForwardEvent",
            "MouseWheelBackwardEvent",
        ):
            self.iren.RemoveObservers(evt)

        # Transformaciones dinámicas compartidas por grupo cinemático (incluye paralelogramo 4 barras!)
        self.tfs = {
            k: vtk.vtkTransform()
            for k in ("base", "j1", "j2", "j3", "j4", "gear_l", "gear_r", "link_l", "link_r", "finger_l", "finger_r")
        }
        self.plastic_actors = []
        self.hw_actors = []

        self._build_scene_desk()
        self._load_all_cad_meshes()
        self._build_kinematic_overlay()
        self._build_demo_cube()
        self._setup_lights()
        self._build_ui_panel()
        self._build_sliders()

        # Enlazar nuestro despachador único de ratón, rueda, teclado y reloj
        self.iren.AddObserver("KeyPressEvent", self._on_key)
        self.iren.AddObserver("LeftButtonPressEvent", self._on_left_press)
        self.iren.AddObserver("MouseMoveEvent", self._on_mouse_move)
        self.iren.AddObserver("LeftButtonReleaseEvent", self._on_left_release)
        self.iren.AddObserver("MouseWheelForwardEvent", self._on_wheel_fwd)
        self.iren.AddObserver("MouseWheelBackwardEvent", self._on_wheel_bwd)
        self.iren.AddObserver("LeaveEvent", self._on_leave)
        self.iren.AddObserver("TimerEvent", self._on_timer)

        self._apply_visual_toggles()
        self._reset_camera()
        self.update_pose(transmit=False)

    # ------------------------------------------------------------------
    # Escena 3D: Escritorio, Anillos de Alcance, Mallas STL y Overlay DH
    # ------------------------------------------------------------------
    def _build_scene_desk(self):
        # Superficie de escritorio limpia (Z = 0)
        disk = vtk.vtkCylinderSource()
        disk.SetRadius(235.0)
        disk.SetHeight(1.2)
        disk.SetResolution(96)
        tf = vtk.vtkTransform()
        tf.RotateX(90.0)
        tf.Translate(35.0, 0.0, -0.7)
        tpf = vtk.vtkTransformPolyDataFilter()
        tpf.SetInputConnection(disk.GetOutputPort())
        tpf.SetTransform(tf)
        m = vtk.vtkPolyDataMapper()
        m.SetInputConnection(tpf.GetOutputPort())
        a = vtk.vtkActor()
        a.SetMapper(m)
        a.GetProperty().SetColor(0.89, 0.87, 0.83)
        a.GetProperty().SetOpacity(0.85)
        self.ren3d.AddActor(a)

        # Anillos de referencia (Base Ø94 mm, R=135 mm, Alcance máximo R=205 mm)
        for radius, col, lw in [(BASE_DIA_MM / 2.0, (0.15, 0.15, 0.18), 2.0), (135.0, (0.68, 0.68, 0.70), 1.0), (205.0, (0.83, 0.36, 0.14), 1.4)]:
            pts = vtk.vtkPoints()
            lines = vtk.vtkCellArray()
            n = 96
            for i in range(n):
                ang = 2.0 * math.pi * i / n
                pts.InsertNextPoint(radius * math.cos(ang), radius * math.sin(ang), 0.15)
            lines.InsertNextCell(n + 1)
            for i in range(n + 1):
                lines.InsertCellPoint(i % n)
            pd = vtk.vtkPolyData()
            pd.SetPoints(pts)
            pd.SetLines(lines)
            mp = vtk.vtkPolyDataMapper()
            mp.SetInputData(pd)
            ac = vtk.vtkActor()
            ac.SetMapper(mp)
            ac.GetProperty().SetColor(*col)
            ac.GetProperty().SetLineWidth(lw)
            self.ren3d.AddActor(ac)

        # Ejes de mundo X (rojo) y Y (verde) sobre el escritorio
        for end, col in [((225, 0, 0.2), (0.82, 0.22, 0.18)), ((0, 180, 0.2), (0.14, 0.60, 0.30))]:
            ls = vtk.vtkLineSource()
            ls.SetPoint1(0, 0, 0.2)
            ls.SetPoint2(*end)
            mp = vtk.vtkPolyDataMapper()
            mp.SetInputConnection(ls.GetOutputPort())
            ac = vtk.vtkActor()
            ac.SetMapper(mp)
            ac.GetProperty().SetColor(*col)
            ac.GetProperty().SetLineWidth(1.6)
            self.ren3d.AddActor(ac)

    def _load_all_cad_meshes(self):
        # 1. 30 piezas imprimibles (Negro Mate y Blanco Mate)
        for folder, rgb in [(BLK_DIR, (0.16, 0.16, 0.18)), (WHT_DIR, (0.97, 0.97, 0.96))]:
            if not os.path.isdir(folder):
                continue
            for fname in sorted(os.listdir(folder)):
                if not fname.endswith(".stl"):
                    continue
                grp = GROUP_MAP.get(fname, "base")
                act = _load_baked_actor(os.path.join(folder, fname), grp, rgb, is_hw=False)
                act.SetUserTransform(self.tfs[grp])
                self.ren3d.AddActor(act)
                self.plastic_actors.append(act)

        # 2. 19 componentes internos reales (servos MG90S/SG90, 608ZZ, PCBs)
        if os.path.isdir(HW_DIR):
            for fname in sorted(os.listdir(HW_DIR)):
                if not fname.endswith(".stl"):
                    continue
                grp = GROUP_MAP.get(fname, "base")
                rgb = (0.72, 0.74, 0.78)
                for key, col in HW_COLORS.items():
                    if key in fname:
                        rgb = col
                        break
                act = _load_baked_actor(os.path.join(HW_DIR, fname), grp, rgb, is_hw=True)
                act.SetUserTransform(self.tfs[grp])
                self.ren3d.AddActor(act)
                self.hw_actors.append(act)

    def _build_kinematic_overlay(self):
        """Ejes de rotación visibles + etiquetas flotantes J1, J2, J3, J4 y TCP + proyección XY."""
        self.kin_actors = []

        # Cilindros de eje de rotación para J1 (vertical Z) y J2, J3, J4 (horizontales Y)
        def _axis_cyl(length, radius, color, is_z=False):
            cyl = vtk.vtkCylinderSource()
            cyl.SetRadius(radius)
            cyl.SetHeight(length)
            cyl.SetResolution(24)
            tf = vtk.vtkTransform()
            if is_z:
                tf.RotateX(90.0)
            tpf = vtk.vtkTransformPolyDataFilter()
            tpf.SetInputConnection(cyl.GetOutputPort())
            tpf.SetTransform(tf)
            mp = vtk.vtkPolyDataMapper()
            mp.SetInputConnection(tpf.GetOutputPort())
            ac = vtk.vtkActor()
            ac.SetMapper(mp)
            ac.GetProperty().SetColor(*color)
            self.ren3d.AddActor(ac)
            self.kin_actors.append(ac)
            return ac

        # Eje J1 (vertical por el centro de la base)
        ax_j1 = _axis_cyl(72.0, 1.3, (0.15, 0.45, 0.92), is_z=True)
        ax_j1.SetPosition(0.0, 0.0, 36.0)

        # Ejes J2, J3, J4 (sobresalen ligeramente de los tambores para mostrar los 3 ejes pitch)
        ax_j2 = _axis_cyl(64.0, 1.3, (0.88, 0.34, 0.10), is_z=False)
        tf_j2_ax = vtk.vtkTransform()
        tf_j2_ax.Concatenate(self.tfs["j1"])
        tf_j2_ax.Translate(0.0, 0.0, D1_MM)
        ax_j2.SetUserTransform(tf_j2_ax)

        ax_j3 = _axis_cyl(60.0, 1.2, (0.88, 0.34, 0.10), is_z=False)
        tf_j3_ax = vtk.vtkTransform()
        tf_j3_ax.Concatenate(self.tfs["j2"])
        tf_j3_ax.Translate(A2_MM, 0.0, 0.0)
        ax_j3.SetUserTransform(tf_j3_ax)

        ax_j4 = _axis_cyl(56.0, 1.1, (0.88, 0.34, 0.10), is_z=False)
        tf_j4_ax = vtk.vtkTransform()
        tf_j4_ax.Concatenate(self.tfs["j3"])
        tf_j4_ax.Translate(A3_MM, 0.0, 0.0)
        ax_j4.SetUserTransform(tf_j4_ax)

        # Esfera naranja en el punto TCP exacto de Peter Corke
        sph = vtk.vtkSphereSource()
        sph.SetRadius(3.8)
        sph.SetThetaResolution(20)
        sph.SetPhiResolution(20)
        mp_tcp = vtk.vtkPolyDataMapper()
        mp_tcp.SetInputConnection(sph.GetOutputPort())
        self.tcp_dot = vtk.vtkActor()
        self.tcp_dot.SetMapper(mp_tcp)
        self.tcp_dot.GetProperty().SetColor(0.90, 0.33, 0.08)
        self.ren3d.AddActor(self.tcp_dot)
        self.kin_actors.append(self.tcp_dot)

        # Línea vertical de proyección TCP -> plano XY del escritorio
        self.proj_line_src = vtk.vtkLineSource()
        mp_pl = vtk.vtkPolyDataMapper()
        mp_pl.SetInputConnection(self.proj_line_src.GetOutputPort())
        self.proj_line = vtk.vtkActor()
        self.proj_line.SetMapper(mp_pl)
        self.proj_line.GetProperty().SetColor(0.16, 0.44, 0.90)
        self.proj_line.GetProperty().SetLineWidth(1.8)
        self.ren3d.AddActor(self.proj_line)
        self.kin_actors.append(self.proj_line)

        sph_xy = vtk.vtkSphereSource()
        sph_xy.SetRadius(2.8)
        mp_xy = vtk.vtkPolyDataMapper()
        mp_xy.SetInputConnection(sph_xy.GetOutputPort())
        self.proj_dot = vtk.vtkActor()
        self.proj_dot.SetMapper(mp_xy)
        self.proj_dot.GetProperty().SetColor(0.16, 0.44, 0.90)
        self.ren3d.AddActor(self.proj_dot)
        self.kin_actors.append(self.proj_dot)

        # Rastro 3D de trayectoria (para Demo jtraj y Rectángulo ctraj)
        self.trail_poly = vtk.vtkPolyData()
        mp_tr = vtk.vtkPolyDataMapper()
        mp_tr.SetInputData(self.trail_poly)
        self.trail_actor = vtk.vtkActor()
        self.trail_actor.SetMapper(mp_tr)
        self.trail_actor.GetProperty().SetColor(0.88, 0.34, 0.10)
        self.trail_actor.GetProperty().SetLineWidth(3.0)
        self.ren3d.AddActor(self.trail_actor)

        # Etiquetas 3D flotantes claras: J1, J2, J3, J4 y TCP Pinza
        self.joint_labels = {}
        for key, txt, col in [
            ("J1", "J1 Base (Yaw)", (0.12, 0.38, 0.85)),
            ("J2", "J2 Hombro", (0.12, 0.12, 0.15)),
            ("J3", "J3 Codo", (0.12, 0.12, 0.15)),
            ("J4", "J4 Muñeca", (0.12, 0.12, 0.15)),
            ("TCP", "Pinza (TCP)", (0.84, 0.30, 0.08)),
        ]:
            lbl = vtk.vtkBillboardTextActor3D()
            lbl.SetInput(txt)
            tp = lbl.GetTextProperty()
            tp.SetFontFamilyToArial()
            tp.SetFontSize(13)
            tp.SetBold(True)
            tp.SetColor(*col)
            tp.SetBackgroundColor(1.0, 1.0, 1.0)
            tp.SetBackgroundOpacity(0.78)
            tp.SetFrame(True)
            tp.SetFrameColor(0.82, 0.82, 0.85)
            self.ren3d.AddActor(lbl)
            self.joint_labels[key] = lbl
            self.kin_actors.append(lbl)

    def _build_demo_cube(self):
        """Cubo objetivo de 16 mm sobre el escritorio para la animación Pick & Place."""
        cube = vtk.vtkCubeSource()
        cube.SetXLength(16.0)
        cube.SetYLength(16.0)
        cube.SetZLength(16.0)
        mp = vtk.vtkPolyDataMapper()
        mp.SetInputConnection(cube.GetOutputPort())
        self.demo_cube = vtk.vtkActor()
        self.demo_cube.SetMapper(mp)
        self.demo_cube.GetProperty().SetColor(0.88, 0.35, 0.10)
        self.demo_cube.GetProperty().SetSpecular(0.25)
        self.demo_cube.SetPosition(*self.cube_pos)
        self.demo_cube.SetVisibility(False)
        self.ren3d.AddActor(self.demo_cube)

    def _setup_lights(self):
        self.ren3d.AutomaticLightCreationOff()
        for pos, inten in [((380, -340, 440), 0.94), ((-300, -240, 260), 0.48), ((0, 360, 240), 0.38)]:
            lt = vtk.vtkLight()
            lt.SetLightTypeToSceneLight()
            lt.SetPosition(*pos)
            lt.SetFocalPoint(60, 0, 100)
            lt.SetIntensity(inten)
            self.ren3d.AddLight(lt)

    # ------------------------------------------------------------------
    # Panel Derecho Minimalista B2 Stealth (Telemetría + Sliders + Botones)
    # ------------------------------------------------------------------
    def _build_ui_panel(self):
        # Encabezado
        _add_2d_text(self.ren_ui, "MINI-PRO 4-DOF · B2 STEALTH", 0.06, 0.955, 16, (0.98, 0.98, 0.99), bold=True)
        self.txt_mode = _add_2d_text(self.ren_ui, f"MODO: {self.link.mode_label}", 0.06, 0.925, 12, (0.64, 0.64, 0.70))

        # Tarjeta de telemetría cinemática Peter Corke
        _add_2d_rect(self.ren_ui, 0.05, 0.805, 0.95, 0.905, (0.11, 0.11, 0.135), edge_rgb=(0.22, 0.22, 0.26))
        _add_2d_text(self.ren_ui, "CINEMÁTICA DIRECTA (Peter Corke fkine)", 0.08, 0.882, 11, (0.62, 0.62, 0.68), bold=True)
        self.txt_tcp = _add_2d_text(self.ren_ui, "TCP: (145.5, 0.0, 125.2) mm", 0.08, 0.850, 13, (0.98, 0.98, 0.99), bold=True)
        self.txt_phi = _add_2d_text(self.ren_ui, "φ = 0.0°  |  Pinza = 16 mm  |  w = 0.000", 0.08, 0.820, 12, (0.92, 0.45, 0.22))

        # Encabezado Sección 1: 4 DOF
        _add_2d_text(self.ren_ui, "ARTICULACIONES DEL BRAZO (4 DOF · 4× MG90S)", 0.06, 0.768, 11, (0.78, 0.78, 0.84), bold=True)

        # Divisor + Encabezado Sección 2: Efector Final
        _add_2d_rect(self.ren_ui, 0.06, 0.378, 0.94, 0.381, (0.24, 0.24, 0.28))
        _add_2d_text(self.ren_ui, "EFECTOR FINAL (PINZA PARALELA · 1× SG90)", 0.06, 0.348, 11, (0.94, 0.48, 0.22), bold=True)

        # Botones clickeables en la parte inferior del panel derecho (coordenadas normalizadas del viewport derecho)
        _add_2d_rect(self.ren_ui, 0.06, 0.238, 0.94, 0.241, (0.24, 0.24, 0.28))
        self.buttons = []
        btn_defs = [
            ("hero",  "Pose Héroe [1]",      0.05, 0.175, 0.48, 0.225, (0.96, 0.96, 0.97), (0.08, 0.08, 0.10)),
            ("home",  "Home Vertical [2]",   0.52, 0.175, 0.95, 0.225, (0.16, 0.16, 0.20), (0.95, 0.95, 0.97)),
            ("jtraj", "Pick & Place [3]",    0.05, 0.115, 0.48, 0.165, (0.84, 0.32, 0.09), (1.00, 1.00, 1.00)),
            ("ctraj", "Rectángulo ctraj [4]",0.52, 0.115, 0.95, 0.165, (0.16, 0.36, 0.78), (1.00, 1.00, 1.00)),
            ("xray",  "Rayos-X [X]",         0.05, 0.058, 0.33, 0.104, (0.14, 0.14, 0.17), (0.92, 0.92, 0.95)),
            ("kin",   "Ejes DH [K]",         0.36, 0.058, 0.64, 0.104, (0.14, 0.14, 0.17), (0.92, 0.92, 0.95)),
            ("relax", "Relajar [Esp]",       0.67, 0.058, 0.95, 0.104, (0.26, 0.14, 0.14), (0.98, 0.84, 0.84)),
        ]
        for bid, label, x0, y0, x1, y1, bg, fg in btn_defs:
            _add_2d_rect(self.ren_ui, x0, y0, x1, y1, bg, edge_rgb=(0.32, 0.32, 0.38))
            _add_2d_text(self.ren_ui, label, 0.5 * (x0 + x1), 0.5 * (y0 + y1), 12, fg, bold=True, center=True)
            self.buttons.append((bid, x0, y0, x1, y1))

        _add_2d_text(self.ren_ui, "Mouse Izq: rotar · Rueda: zoom · [R] centrar · [Esc] salir", 0.50, 0.025, 11, (0.52, 0.52, 0.58), center=True)

        # Pie informativo sutil en la esquina inferior izquierda de la escena 3D
        _add_2d_text(
            self.ren3d,
            "Modelo 3D CAD v4 Clean-DFA real (34 STLs 1 sólido + 22 internos · pinza MeArm Mod 1.5) · Peter Corke (82/82/70/53 mm)",
            0.02, 0.022, 12, (0.28, 0.28, 0.32),
        )

    def _build_sliders(self):
        """Sliders vectoriales minimalistas B2 Stealth en el panel derecho (100% nativos, cero glitch)."""
        self.slider_defs = [
            ("J1 · Base Yaw",       QLIM_DEG[0, 0], QLIM_DEG[0, 1], 0.718, (0.96, 0.96, 0.98), "deg"),
            ("J2 · Hombro Pitch",   QLIM_DEG[1, 0], QLIM_DEG[1, 1], 0.632, (0.96, 0.96, 0.98), "deg"),
            ("J3 · Codo Pitch",     QLIM_DEG[2, 0], QLIM_DEG[2, 1], 0.546, (0.96, 0.96, 0.98), "deg"),
            ("J4 · Muñeca Pitch",   QLIM_DEG[3, 0], QLIM_DEG[3, 1], 0.460, (0.96, 0.96, 0.98), "deg"),
            ("Pinza Paralela SG90", 0.0,            30.0,           0.296, (0.94, 0.42, 0.14), "mm"),
        ]
        self.slider_x0 = 0.07
        self.slider_x1 = 0.93
        self.slider_ui = []

        for idx, (title, vmin, vmax, y_track, accent, unit) in enumerate(self.slider_defs):
            # Título izquierdo + valor numérico derecho
            _add_2d_text(self.ren_ui, title, self.slider_x0, y_track + 0.022, 12, (0.90, 0.90, 0.94), bold=True)
            val_txt = _add_2d_text(self.ren_ui, "", self.slider_x1, y_track + 0.022, 12, accent, bold=True)
            val_txt.GetTextProperty().SetJustificationToRight()

            # Pista de fondo oscura
            _add_2d_rect(self.ren_ui, self.slider_x0, y_track - 0.004, self.slider_x1, y_track + 0.004, (0.22, 0.22, 0.27))

            # Barra de progreso dinámica (puntos actualizables)
            fill_pts = vtk.vtkPoints()
            for p in [(self.slider_x0, y_track - 0.0045, 0), (self.slider_x0, y_track - 0.0045, 0),
                      (self.slider_x0, y_track + 0.0045, 0), (self.slider_x0, y_track + 0.0045, 0)]:
                fill_pts.InsertNextPoint(*p)
            fill_poly = vtk.vtkPolyData()
            fill_poly.SetPoints(fill_pts)
            fq = vtk.vtkCellArray()
            fq.InsertNextCell(4)
            for k in range(4):
                fq.InsertCellPoint(k)
            fill_poly.SetPolys(fq)
            coord = vtk.vtkCoordinate()
            coord.SetCoordinateSystemToNormalizedViewport()
            fmap = vtk.vtkPolyDataMapper2D()
            fmap.SetInputData(fill_poly)
            fmap.SetTransformCoordinate(coord)
            fact = vtk.vtkActor2D()
            fact.SetMapper(fmap)
            fact.GetProperty().SetColor(*accent)
            self.ren_ui.AddActor2D(fact)

            # Perilla (thumb) dinámica
            knob_pts = vtk.vtkPoints()
            for _ in range(4):
                knob_pts.InsertNextPoint(0, 0, 0)
            knob_poly = vtk.vtkPolyData()
            knob_poly.SetPoints(knob_pts)
            kq = vtk.vtkCellArray()
            kq.InsertNextCell(4)
            for k in range(4):
                kq.InsertCellPoint(k)
            knob_poly.SetPolys(kq)
            kmap = vtk.vtkPolyDataMapper2D()
            kmap.SetInputData(knob_poly)
            kmap.SetTransformCoordinate(coord)
            kact = vtk.vtkActor2D()
            kact.SetMapper(kmap)
            kact.GetProperty().SetColor(1.0, 1.0, 1.0)
            self.ren_ui.AddActor2D(kact)

            # Etiquetas min / max sutiles bajo la pista
            lo_s = f"{vmin:+.0f}°" if unit == "deg" else "0 mm"
            hi_s = f"{vmax:+.0f}°" if unit == "deg" else "30 mm"
            _add_2d_text(self.ren_ui, lo_s, self.slider_x0, y_track - 0.024, 10, (0.48, 0.48, 0.55))
            hi_t = _add_2d_text(self.ren_ui, hi_s, self.slider_x1, y_track - 0.024, 10, (0.48, 0.48, 0.55))
            hi_t.GetTextProperty().SetJustificationToRight()

            self.slider_ui.append({
                "vmin": float(vmin),
                "vmax": float(vmax),
                "y": y_track,
                "unit": unit,
                "val_txt": val_txt,
                "fill_pts": fill_pts,
                "fill_poly": fill_poly,
                "knob_pts": knob_pts,
                "knob_poly": knob_poly,
                "knob_actor": kact,
            })

    # ------------------------------------------------------------------
    # Actualización cinemática exacta de los 35 STLs + Peter Corke fkine
    # ------------------------------------------------------------------
    def _sync_sliders(self):
        vals = [self.q_deg[0], self.q_deg[1], self.q_deg[2], self.q_deg[3], self.grip_mm]
        kw, kh = 0.014, 0.011
        for idx, (ui, v) in enumerate(zip(self.slider_ui, vals)):
            t = (float(v) - ui["vmin"]) / max(1e-6, ui["vmax"] - ui["vmin"])
            t = max(0.0, min(1.0, t))
            x = self.slider_x0 + t * (self.slider_x1 - self.slider_x0)
            y = ui["y"]

            ui["fill_pts"].SetPoint(1, x, y - 0.0045, 0)
            ui["fill_pts"].SetPoint(2, x, y + 0.0045, 0)
            ui["fill_pts"].Modified()
            ui["fill_poly"].Modified()

            ui["knob_pts"].SetPoint(0, x - kw, y - kh, 0)
            ui["knob_pts"].SetPoint(1, x + kw, y - kh, 0)
            ui["knob_pts"].SetPoint(2, x + kw, y + kh, 0)
            ui["knob_pts"].SetPoint(3, x - kw, y + kh, 0)
            ui["knob_pts"].Modified()
            ui["knob_poly"].Modified()
            if self.active_slider == idx:
                ui["knob_actor"].GetProperty().SetColor(0.98, 0.45, 0.14)
            else:
                ui["knob_actor"].GetProperty().SetColor(1.0, 1.0, 1.0)

            if ui["unit"] == "deg":
                vv = 0.0 if abs(v) < 0.05 else v
                ui["val_txt"].SetInput(f"{vv:+.1f}°")
            else:
                ui["val_txt"].SetInput(f"{v:.0f} mm")

    def _update_trail_poly(self):
        pts = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        if len(self.trail_pts) >= 2:
            for p in self.trail_pts:
                pts.InsertNextPoint(*p)
            lines.InsertNextCell(len(self.trail_pts))
            for i in range(len(self.trail_pts)):
                lines.InsertCellPoint(i)
        self.trail_poly.SetPoints(pts)
        self.trail_poly.SetLines(lines)
        self.trail_poly.Modified()

    def update_pose(self, transmit: bool = True, throttle_s: float = 0.0, record_trail: bool = False):
        q1, q2, q3, q4 = [float(x) for x in self.q_deg]
        g = float(np.clip(self.grip_mm, 0.0, 30.0))

        # 1. Transformaciones rígidas encadenadas (idénticas a `cad/mini_pro_b2_stealth_v4.py`!)
        self.tfs["base"].Identity()

        self.tfs["j1"].Identity()
        self.tfs["j1"].RotateZ(q1)

        self.tfs["j2"].Identity()
        self.tfs["j2"].RotateZ(q1)
        self.tfs["j2"].Translate(0.0, 0.0, D1_MM)
        self.tfs["j2"].RotateY(-q2)

        self.tfs["j3"].Identity()
        self.tfs["j3"].Concatenate(self.tfs["j2"])
        self.tfs["j3"].Translate(A2_MM, 0.0, 0.0)
        self.tfs["j3"].RotateY(-q3)

        self.tfs["j4"].Identity()
        self.tfs["j4"].Concatenate(self.tfs["j3"])
        self.tfs["j4"].Translate(A3_MM, 0.0, 0.0)
        self.tfs["j4"].RotateY(-q4)

        # 2. Efector final: Cinemática trigonométrica EXACTA MeArm Mod 1.5 (compartida con firmware!)
        th_deg, tcp_x_real, dx, _servo_deg = gripper_kinematics_v4(g)
        dth = th_deg - HERO_GRIP_TH_DEG
        dy = GRIP_LINK_L * (math.sin(math.radians(th_deg)) - math.sin(math.radians(HERO_GRIP_TH_DEG)))

        self.tfs["gear_l"].Identity()
        self.tfs["gear_l"].Concatenate(self.tfs["j4"])
        self.tfs["gear_l"].Translate(GEAR_LOCAL_X, +GEAR_LOCAL_Y, 0.0)
        self.tfs["gear_l"].RotateZ(+dth)

        self.tfs["gear_r"].Identity()
        self.tfs["gear_r"].Concatenate(self.tfs["j4"])
        self.tfs["gear_r"].Translate(GEAR_LOCAL_X, -GEAR_LOCAL_Y, 0.0)
        self.tfs["gear_r"].RotateZ(-dth)

        self.tfs["link_l"].Identity()
        self.tfs["link_l"].Concatenate(self.tfs["j4"])
        self.tfs["link_l"].Translate(IDLER_LOCAL_X, +IDLER_LOCAL_Y, 0.0)
        self.tfs["link_l"].RotateZ(+dth)

        self.tfs["link_r"].Identity()
        self.tfs["link_r"].Concatenate(self.tfs["j4"])
        self.tfs["link_r"].Translate(IDLER_LOCAL_X, -IDLER_LOCAL_Y, 0.0)
        self.tfs["link_r"].RotateZ(-dth)

        self.tfs["finger_l"].Identity()
        self.tfs["finger_l"].Concatenate(self.tfs["j4"])
        self.tfs["finger_l"].Translate(dx, +dy, 0.0)

        self.tfs["finger_r"].Identity()
        self.tfs["finger_r"].Concatenate(self.tfs["j4"])
        self.tfs["finger_r"].Translate(dx, -dy, 0.0)

        # 3. Cinemática oficial Peter Corke (`fkine_all` + `jacob0` manipulabilidad + guarda anti-mesa)
        q_rad = np.deg2rad(self.q_deg)
        pts = self.robot.joint_positions_mm(q_rad)  # [Base, J2, J3, J4, TCP]
        tcp = pts[-1]
        safe_z, _zj3, _zj4, z_tcp_eff, _gmsg = self.robot.check_table_guard(q_rad, g)
        phi = q2 + q3 + q4
        Jv = self.robot.jacob0(q_rad)[:3, :]
        manip = math.sqrt(max(0.0, float(np.linalg.det(Jv @ Jv.T))))

        # Actualizar indicadores 3D (TCP, proyección XY y etiquetas J1..J4 + TCP)
        self.tcp_dot.SetPosition(*tcp)
        self.proj_dot.SetPosition(tcp[0], tcp[1], 0.5)
        self.proj_line_src.SetPoint1(tcp[0], tcp[1], 0.5)
        self.proj_line_src.SetPoint2(*tcp)
        self.proj_line_src.Modified()

        # Posicionar etiquetas limpiamente fuera del sólido para cero recortes
        rad1 = math.radians(q1)
        off_y = np.array([math.sin(rad1), -math.cos(rad1), 0.0])  # vector lateral derecho del brazo
        self.joint_labels["J1"].SetPosition(14.0, -76.0, 24.0)
        self.joint_labels["J2"].SetPosition(*(pts[1] + off_y * 48.0 + np.array([0.0, 0.0, 6.0])))
        self.joint_labels["J3"].SetPosition(*(pts[2] + off_y * 42.0 + np.array([0.0, 0.0, 22.0])))
        self.joint_labels["J4"].SetPosition(*(pts[3] + off_y * 36.0 + np.array([0.0, 0.0, 22.0])))
        self.joint_labels["TCP"].SetPosition(*(tcp + np.array([12.0, 0.0, 20.0])))

        if self.cube_held:
            self.cube_pos = tcp.copy()
            self.demo_cube.SetPosition(*self.cube_pos)

        if record_trail:
            self.trail_pts.append(tcp.copy())
            if len(self.trail_pts) > 300:
                self.trail_pts = self.trail_pts[-300:]
            self._update_trail_poly()

        # Sincronizar sliders y telemetría en panel derecho
        self._sync_sliders()
        phi_clean = 0.0 if abs(phi) < 0.05 else phi
        self.txt_tcp.SetInput(f"TCP: ({tcp[0]:5.1f}, {tcp[1]:5.1f}, {tcp[2]:5.1f}) mm")
        if self.relaxed:
            self.txt_phi.SetInput("SERVOS RELAJADOS (FULL_OFF 4096)")
        elif not safe_z:
            self.txt_phi.SetInput(f"[!] GUARDA MESA: Z_eff={z_tcp_eff:.1f} mm (< 8 mm)")
        else:
            self.txt_phi.SetInput(f"φ={phi_clean:+.1f}° | g={g:.0f}mm (Δx={dx:+.1f}) | w={manip:.3f}")

        # Transmisión en vivo hacia XIAO ESP32-S3 (solo si pasa guarda anti-mesa!)
        if transmit and not self.relaxed and safe_z:
            self.link.send_pose(self.q_deg, g, throttle_s=throttle_s)

        self.win.Render()

    # ------------------------------------------------------------------
    # Modos visuales, Demos Peter Corke y Eventos
    # ------------------------------------------------------------------
    def _apply_visual_toggles(self):
        op = 0.28 if self.xray else 1.0
        for act in self.plastic_actors:
            act.GetProperty().SetOpacity(op)
        for act in self.hw_actors:
            act.SetVisibility(self.show_hw or self.xray)
        for act in self.kin_actors:
            act.SetVisibility(self.show_kin)
        self.win.Render()

    def _reset_camera(self):
        cam = self.ren3d.GetActiveCamera()
        cam.SetFocalPoint(58.0, 0.0, 108.0)
        cam.SetPosition(365.0, -375.0, 270.0)
        cam.SetViewUp(0.0, 0.0, 1.0)
        cam.SetViewAngle(32.0)
        self.ren3d.ResetCameraClippingRange()
        self.win.Render()

    def _queue_move(self, target_q_deg, target_grip, steps=24):
        self.anim_queue.clear()
        self.demo_cube.SetVisibility(False)
        self.cube_held = False
        self.trail_pts.clear()
        self._update_trail_poly()
        self.relaxed = False
        tr = rtb.jtraj(np.deg2rad(self.q_deg), np.deg2rad(target_q_deg), steps)
        gs = np.linspace(self.grip_mm, target_grip, steps)
        for qi, gi in zip(tr.q, gs):
            self.anim_queue.append((np.rad2deg(qi), float(gi), None, False))

    def _start_demo_jtraj(self):
        self.anim_queue.clear()
        self.trail_pts.clear()
        self._update_trail_poly()
        self.relaxed = False
        self.cube_held = False
        self.cube_pos = np.array([135.0, -65.0, 68.0])
        self.demo_cube.SetPosition(*self.cube_pos)
        self.demo_cube.SetVisibility(True)

        # Secuencia Pick & Place exacta con Peter Corke `rtb.jtraj` (idéntica al firmware!)
        wps = [
            ((135, -65, 108, 0), 26.0, "open"),
            ((135, -65,  68, 0), 26.0, "open"),
            ((135, -65,  68, 0),  8.0, "grab"),
            ((135, -65, 108, 0),  8.0, "hold"),
            ((145,   0, 130, 0),  8.0, "hold"),
            ((135,  65, 108, 0),  8.0, "hold"),
            ((135,  65,  68, 0),  8.0, "hold"),
            ((135,  65,  68, 0), 26.0, "drop"),
            ((135,  65, 108, 0), 26.0, "open"),
            ((145.52, 0, 125.17, 0), 16.0, "open"),
        ]
        qs = [(self.robot.ikine_analytic_mm(*w)[0], g, st) for w, g, st in wps]
        q_prev = np.deg2rad(self.q_deg)
        g_prev = self.grip_mm
        for q_next, g_next, st in qs:
            steps = 12 if np.allclose(q_prev, q_next) else 22
            tr = rtb.jtraj(q_prev, q_next, steps)
            gs = np.linspace(g_prev, g_next, steps)
            for k_step, (qi, gi) in enumerate(zip(tr.q, gs)):
                cube_evt = st if k_step == steps - 1 else None
                self.anim_queue.append((np.rad2deg(qi), float(gi), cube_evt, True))
            q_prev, g_prev = q_next, g_next

    def _start_demo_ctraj(self):
        self.anim_queue.clear()
        self.trail_pts.clear()
        self._update_trail_poly()
        self.demo_cube.SetVisibility(False)
        self.cube_held = False
        self.relaxed = False

        # Rectángulo cartesiano exacto 40×90 mm @ Z=60 mm, φ=-60° usando `rtb.ctraj`
        corners = [
            (100.0, -45.0, 60.0),
            (140.0, -45.0, 60.0),
            (140.0,  45.0, 60.0),
            (100.0,  45.0, 60.0),
            (100.0, -45.0, 60.0),
        ]
        # Acercamiento suave al primer vértice
        q0, ok, _ = self.robot.ikine_analytic_mm(*corners[0], phi_deg=-60.0)
        if not ok:
            return
        tr_in = rtb.jtraj(np.deg2rad(self.q_deg), q0, 18)
        for qi in tr_in.q:
            self.anim_queue.append((np.rad2deg(qi), 10.0, None, False))

        # 4 lados rectilíneos exactos vía `rtb.ctraj` + `spatialmath.SE3`
        for k in range(len(corners) - 1):
            T0 = SE3(corners[k][0] / 1000.0, corners[k][1] / 1000.0, corners[k][2] / 1000.0)
            T1 = SE3(corners[k + 1][0] / 1000.0, corners[k + 1][1] / 1000.0, corners[k + 1][2] / 1000.0)
            Ts = rtb.ctraj(T0, T1, 28)
            for T in Ts:
                p = T.t * 1000.0
                qk, okk, _ = self.robot.ikine_analytic_mm(p[0], p[1], p[2], phi_deg=-60.0)
                if okk:
                    self.anim_queue.append((np.rad2deg(qk), 10.0, None, True))

    def _trigger_action(self, bid: str):
        if bid == "hero":
            self._queue_move(np.rad2deg(Q_HERO_RAD), HERO_GRIP)
        elif bid == "home":
            self._queue_move(np.rad2deg(Q_HOME_RAD), 18.0)
        elif bid == "jtraj":
            self._start_demo_jtraj()
        elif bid == "ctraj":
            self._start_demo_ctraj()
        elif bid == "xray":
            self.xray = not self.xray
            self._apply_visual_toggles()
        elif bid == "kin":
            self.show_kin = not self.show_kin
            self._apply_visual_toggles()
        elif bid == "relax":
            self.anim_queue.clear()
            self.relaxed = True
            self.link.send_raw("RELAX")
            self.update_pose(transmit=False)

    def _is_physical_lbutton_down(self) -> bool:
        """Verifica en Windows el estado físico real del botón izquierdo del ratón (evita sliders pegados)."""
        if self.offscreen or os.name != "nt":
            return True
        try:
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        except Exception:
            return True

    def _hit_slider(self, xn_ui: float, yn_global: float):
        if not ((self.slider_x0 - 0.05) <= xn_ui <= (self.slider_x1 + 0.05)):
            return None
        for idx, ui in enumerate(self.slider_ui):
            if abs(yn_global - ui["y"]) <= 0.036:
                return idx
        return None

    def _set_slider_from_x(self, idx: int, xn_ui: float, render_now: bool = True):
        ui = self.slider_ui[idx]
        t = (xn_ui - self.slider_x0) / max(1e-6, self.slider_x1 - self.slider_x0)
        t = max(0.0, min(1.0, t))
        val = ui["vmin"] + t * (ui["vmax"] - ui["vmin"])
        self.anim_queue.clear()
        self.demo_cube.SetVisibility(False)
        self.cube_held = False
        self.relaxed = False
        if idx < 4:
            self.q_deg[idx] = val
        else:
            self.grip_mm = val
        if render_now:
            self._dirty_render = False
            self.update_pose(transmit=True, throttle_s=0.025)
        else:
            self._dirty_render = True

    def _release_slider(self):
        if self.active_slider is not None:
            self.active_slider = None
            self._dirty_render = False
            self.update_pose(transmit=True, throttle_s=0.0)

    def _on_left_press(self, obj, _evt):
        x, y = obj.GetEventPosition()
        w, h = self.win.GetSize()
        if w <= 0 or h <= 0:
            return
        xn_global = x / float(w)
        yn_global = y / float(h)

        # Soltar siempre cualquier estado anterior antes de procesar el nuevo clic
        if self.active_slider is not None:
            self._release_slider()

        if xn_global >= 0.72:
            # Clic dentro del panel derecho -> NUNCA invocar TrackballCamera
            xn_ui = (xn_global - 0.72) / 0.28
            s_idx = self._hit_slider(xn_ui, yn_global)
            if s_idx is not None:
                self.active_slider = s_idx
                self._set_slider_from_x(s_idx, xn_ui, render_now=True)
                return
            for bid, x0, y0, x1, y1 in self.buttons:
                if x0 <= xn_ui <= x1 and y0 <= yn_global <= y1:
                    self._trigger_action(bid)
                    return
        else:
            # Clic dentro de la escena 3D -> órbita normal de cámara
            self.orbiting = True
            self.style.OnLeftButtonDown()

    def _on_mouse_move(self, obj, _evt):
        if self.active_slider is not None:
            if not self._is_physical_lbutton_down():
                self._release_slider()
                return
            x, _y = obj.GetEventPosition()
            w, _h = self.win.GetSize()
            if w <= 0:
                return
            xn_ui = ((x / float(w)) - 0.72) / 0.28
            # Actualizar valor sin bloquear la cola de mensajes de Windows (renderiza el reloj a 60 Hz)
            self._set_slider_from_x(self.active_slider, xn_ui, render_now=self.offscreen)
            return

        if self.orbiting:
            if not self._is_physical_lbutton_down():
                self.orbiting = False
                self.style.OnLeftButtonUp()
                return
            self.style.OnMouseMove()

    def _on_left_release(self, _obj, _evt):
        if self.active_slider is not None:
            self._release_slider()
        if self.orbiting:
            self.orbiting = False
            self.style.OnLeftButtonUp()

    def _on_leave(self, _obj, _evt):
        if self.active_slider is not None and not self._is_physical_lbutton_down():
            self._release_slider()
        if self.orbiting and not self._is_physical_lbutton_down():
            self.orbiting = False
            self.style.OnLeftButtonUp()

    def _handle_wheel(self, obj, direction: int):
        x, y = obj.GetEventPosition()
        w, h = self.win.GetSize()
        if w <= 0 or h <= 0:
            return
        xn_global = x / float(w)
        yn_global = y / float(h)
        if xn_global >= 0.72:
            # Rueda sobre un slider -> ajuste fino (±2° o ±1 mm)
            xn_ui = (xn_global - 0.72) / 0.28
            s_idx = self._hit_slider(xn_ui, yn_global)
            if s_idx is not None:
                ui = self.slider_ui[s_idx]
                step = 2.0 if s_idx < 4 else 1.0
                self.anim_queue.clear()
                self.relaxed = False
                if s_idx < 4:
                    self.q_deg[s_idx] = float(np.clip(self.q_deg[s_idx] + direction * step, ui["vmin"], ui["vmax"]))
                else:
                    self.grip_mm = float(np.clip(self.grip_mm + direction * step, ui["vmin"], ui["vmax"]))
                self.update_pose(transmit=True, throttle_s=0.0)
            return
        if direction > 0:
            self.style.OnMouseWheelForward()
        else:
            self.style.OnMouseWheelBackward()

    def _on_wheel_fwd(self, obj, _evt):
        self._handle_wheel(obj, +1)

    def _on_wheel_bwd(self, obj, _evt):
        self._handle_wheel(obj, -1)

    def _on_key(self, obj, _evt):
        key = (obj.GetKeySym() or "").lower()
        if key == "escape":
            self.iren.TerminateApp()
        elif key == "1":
            self._trigger_action("hero")
        elif key == "2":
            self._trigger_action("home")
        elif key == "3":
            self._trigger_action("jtraj")
        elif key == "4":
            self._trigger_action("ctraj")
        elif key == "x":
            self._trigger_action("xray")
        elif key == "h":
            self.show_hw = not self.show_hw
            self._apply_visual_toggles()
        elif key == "k":
            self._trigger_action("kin")
        elif key == "space":
            self._trigger_action("relax")
        elif key == "r":
            self._reset_camera()

    def _on_timer(self, _obj, _evt):
        self._timer_tick += 1

        # Red de seguridad 60 Hz: si el botón físico ya se soltó, liberar slider inmediatamente
        if self.active_slider is not None and not self._is_physical_lbutton_down():
            self._release_slider()
            return

        if self._dirty_render:
            self._dirty_render = False
            self.update_pose(transmit=True, throttle_s=0.025)
            return

        if self.anim_queue and (self._timer_tick % 2 == 0):
            qd, g, cube_evt, rec = self.anim_queue.pop(0)
            self.q_deg = np.array(qd, dtype=float)
            self.grip_mm = float(g)
            if cube_evt == "grab":
                self.cube_held = True
            elif cube_evt == "drop":
                self.cube_held = False
            self.update_pose(transmit=True, throttle_s=0.0, record_trail=rec)

    def run(self):
        self.win.Render()
        self.iren.Initialize()
        self.iren.CreateRepeatingTimer(16)  # ~60 Hz para sliders ultra-fluidos (~30 Hz animaciones)
        try:
            self.iren.Start()
        finally:
            self.link.close()


def main():
    parser = argparse.ArgumentParser(description="Gemelo Digital 3D Real — Mini-Pro 4-DOF B2 Stealth (Peter Corke)")
    parser.add_argument("--port", type=str, default="", help="Puerto COM USB Serial (ej. COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="Baudrate serial (default 115200)")
    parser.add_argument("--wifi", type=str, default="", help="IP Wi-Fi de la XIAO ESP32 (ej. 192.168.4.1)")
    parser.add_argument("--udp-port", type=int, default=4210, help="Puerto UDP del firmware (default 4210)")
    args = parser.parse_args()

    link = ArmLink(port=args.port, baud=args.baud, wifi_ip=args.wifi, udp_port=args.udp_port)
    app = DigitalTwinApp(link=link, offscreen=False)
    app.run()


if __name__ == "__main__":
    main()
