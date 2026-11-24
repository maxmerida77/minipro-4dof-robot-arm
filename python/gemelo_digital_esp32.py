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
from params import GRIP_V4, HERO_POSE_DEG, gripper_kinematics_v4, check_physical_guard_v4

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

# Sincronizado 100% con el Single Source of Truth (`cad/params.py` -> `robot_minipro_rtb.py`)
SIM_QLIM_DEG = QLIM_DEG
check_physical_guard_sim = check_physical_guard_v4

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
        self.control_mode = "FK"  # "FK" (J1..J4) | "IK" (X, Y, Z, phi)
        tcp0 = self.robot.fkine_mm(Q_HERO_RAD)
        self.ik_target = np.array([tcp0[0], tcp0[1], tcp0[2], float(self.q_deg[1] + self.q_deg[2] + self.q_deg[3])], dtype=float)
        self.ik_status_msg = ""
        self.xray = False
        self.show_hw = False
        self.show_kin = True
        self.relaxed = False
        self.active_slider = None
        self.orbiting = False
        self._dirty_render = False
        self._dialog_open = False
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

        # Marcador 3D objetivo cian para "Ir a Posición Exacta [G]"
        tgt_sph = vtk.vtkSphereSource()
        tgt_sph.SetRadius(6.0)
        tgt_sph.SetThetaResolution(20)
        tgt_sph.SetPhiResolution(20)
        mp_tgt = vtk.vtkPolyDataMapper()
        mp_tgt.SetInputConnection(tgt_sph.GetOutputPort())
        self.target_marker = vtk.vtkActor()
        self.target_marker.SetMapper(mp_tgt)
        self.target_marker.GetProperty().SetColor(0.14, 0.72, 0.98)
        self.target_marker.GetProperty().SetOpacity(0.72)
        self.target_marker.GetProperty().SetSpecular(0.35)
        self.target_marker.SetVisibility(False)
        self.ren3d.AddActor(self.target_marker)

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

        # Tarjeta de telemetría cinemática Peter Corke (FK + IK en vivo)
        _add_2d_rect(self.ren_ui, 0.05, 0.812, 0.95, 0.910, (0.11, 0.11, 0.135), edge_rgb=(0.22, 0.22, 0.26))
        self.txt_tel_hdr = _add_2d_text(self.ren_ui, "CINEMÁTICA DIRECTA · FK (Peter Corke fkine)", 0.08, 0.888, 11, (0.62, 0.62, 0.68), bold=True)
        self.txt_tcp = _add_2d_text(self.ren_ui, "TCP: (145.5, 0.0, 125.2) mm", 0.08, 0.856, 13, (0.98, 0.98, 0.99), bold=True)
        self.txt_phi = _add_2d_text(self.ren_ui, "φ = 0.0°  |  Pinza = 15 mm  |  w = 0.000", 0.08, 0.826, 11, (0.92, 0.45, 0.22))

        # Selector de Modo FK (Articular) <-> IK (Cartesiano X, Y, Z, φ)
        self.buttons = []
        self.tab_fk_bg = _add_2d_rect(self.ren_ui, 0.05, 0.758, 0.49, 0.800, (0.96, 0.96, 0.97), edge_rgb=(0.35, 0.35, 0.40))
        self.tab_fk_tx = _add_2d_text(self.ren_ui, "Directa · FK [F]", 0.27, 0.779, 12, (0.08, 0.08, 0.10), bold=True, center=True)
        self.tab_ik_bg = _add_2d_rect(self.ren_ui, 0.51, 0.758, 0.95, 0.800, (0.14, 0.14, 0.18), edge_rgb=(0.30, 0.30, 0.36))
        self.tab_ik_tx = _add_2d_text(self.ren_ui, "Inversa · IK [I]", 0.73, 0.779, 12, (0.86, 0.86, 0.92), bold=True, center=True)
        self.buttons.append(("mode_fk", 0.05, 0.758, 0.49, 0.800))
        self.buttons.append(("mode_ik", 0.51, 0.758, 0.95, 0.800))

        # Divisor + Encabezado Sección 2: Efector Final
        _add_2d_rect(self.ren_ui, 0.06, 0.382, 0.94, 0.385, (0.24, 0.24, 0.28))
        _add_2d_text(self.ren_ui, "EFECTOR FINAL (PINZA PARALELA · 1× SG90)", 0.06, 0.354, 11, (0.94, 0.48, 0.22), bold=True)

        # Divisor + Botón destacado "Ir a Posición Exacta [G]" + Botones de acción
        _add_2d_rect(self.ren_ui, 0.06, 0.258, 0.94, 0.261, (0.24, 0.24, 0.28))
        btn_defs = [
            ("goto",  "Ir a Posición Exacta (X,Y,Z,Phi) [G]", 0.05, 0.201, 0.95, 0.247, (0.14, 0.56, 0.88), (1.00, 1.00, 1.00)),
            ("hero",  "Pose Héroe [1]",      0.05, 0.148, 0.48, 0.192, (0.96, 0.96, 0.97), (0.08, 0.08, 0.10)),
            ("home",  "Home Vertical [2]",   0.52, 0.148, 0.95, 0.192, (0.16, 0.16, 0.20), (0.95, 0.95, 0.97)),
            ("jtraj", "Pick & Place [3]",    0.05, 0.095, 0.48, 0.139, (0.84, 0.32, 0.09), (1.00, 1.00, 1.00)),
            ("ctraj", "Rectángulo ctraj [4]",0.52, 0.095, 0.95, 0.139, (0.16, 0.36, 0.78), (1.00, 1.00, 1.00)),
            ("xray",  "Rayos-X [X]",         0.05, 0.044, 0.33, 0.086, (0.14, 0.14, 0.17), (0.92, 0.92, 0.95)),
            ("kin",   "Ejes DH [K]",         0.36, 0.044, 0.64, 0.086, (0.14, 0.14, 0.17), (0.92, 0.92, 0.95)),
            ("relax", "Relajar [Esp]",       0.67, 0.044, 0.95, 0.086, (0.26, 0.14, 0.14), (0.98, 0.84, 0.84)),
        ]
        for bid, label, x0, y0, x1, y1, bg, fg in btn_defs:
            _add_2d_rect(self.ren_ui, x0, y0, x1, y1, bg, edge_rgb=(0.32, 0.32, 0.38))
            _add_2d_text(self.ren_ui, label, 0.5 * (x0 + x1), 0.5 * (y0 + y1), 12, fg, bold=True, center=True)
            self.buttons.append((bid, x0, y0, x1, y1))

        _add_2d_text(self.ren_ui, "[F] FK · [I] IK · [G] Ir a Pos · [R] centrar · [Esc]", 0.50, 0.018, 11, (0.52, 0.52, 0.58), center=True)

        # Pie informativo sutil en la esquina inferior izquierda de la escena 3D
        _add_2d_text(
            self.ren3d,
            "Modelo 3D CAD v4 Clean-DFA real · Límites seguros v4: J1[-85,85] J2[22,145] J3[-125,20] J4[-80,80] · Guarda 3D activa",
            0.02, 0.022, 12, (0.28, 0.28, 0.32),
        )

    def _build_sliders(self):
        """Sliders vectoriales minimalistas B2 Stealth (modo dual FK articular / IK cartesiano!)."""
        self.fk_slider_specs = [
            ("J1 · Base Yaw",       SIM_QLIM_DEG[0, 0], SIM_QLIM_DEG[0, 1], (0.96, 0.96, 0.98), "deg"),
            ("J2 · Hombro Pitch",   SIM_QLIM_DEG[1, 0], SIM_QLIM_DEG[1, 1], (0.96, 0.96, 0.98), "deg"),
            ("J3 · Codo Pitch",     SIM_QLIM_DEG[2, 0], SIM_QLIM_DEG[2, 1], (0.96, 0.96, 0.98), "deg"),
            ("J4 · Muñeca Pitch",   SIM_QLIM_DEG[3, 0], SIM_QLIM_DEG[3, 1], (0.96, 0.96, 0.98), "deg"),
        ]
        self.ik_slider_specs = [
            ("X · Alcance Frontal",   35.0, 199.0, (0.24, 0.68, 0.98), "mm"),
            ("Y · Lateral Izq/Der", -170.0, 170.0, (0.24, 0.68, 0.98), "mm"),
            ("Z · Altura Escritorio", 12.0, 260.0, (0.24, 0.68, 0.98), "mm"),
            ("Phi · Inclinación Pinza", -90.0,  90.0, (0.24, 0.68, 0.98), "deg"),
        ]
        self.slider_defs = [
            ("J1 · Base Yaw",       SIM_QLIM_DEG[0, 0], SIM_QLIM_DEG[0, 1], 0.708, (0.96, 0.96, 0.98), "deg"),
            ("J2 · Hombro Pitch",   SIM_QLIM_DEG[1, 0], SIM_QLIM_DEG[1, 1], 0.625, (0.96, 0.96, 0.98), "deg"),
            ("J3 · Codo Pitch",     SIM_QLIM_DEG[2, 0], SIM_QLIM_DEG[2, 1], 0.542, (0.96, 0.96, 0.98), "deg"),
            ("J4 · Muñeca Pitch",   SIM_QLIM_DEG[3, 0], SIM_QLIM_DEG[3, 1], 0.459, (0.96, 0.96, 0.98), "deg"),
            ("Pinza Paralela SG90", 0.0,                30.0,               0.304, (0.94, 0.42, 0.14), "mm"),
        ]
        self.slider_x0 = 0.07
        self.slider_x1 = 0.93
        self.slider_ui = []

        for idx, (title, vmin, vmax, y_track, accent, unit) in enumerate(self.slider_defs):
            title_txt = _add_2d_text(self.ren_ui, title, self.slider_x0, y_track + 0.022, 12, (0.90, 0.90, 0.94), bold=True)
            val_txt = _add_2d_text(self.ren_ui, "", self.slider_x1, y_track + 0.022, 12, accent, bold=True)
            val_txt.GetTextProperty().SetJustificationToRight()

            _add_2d_rect(self.ren_ui, self.slider_x0, y_track - 0.004, self.slider_x1, y_track + 0.004, (0.22, 0.22, 0.27))

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

            lo_s = f"{vmin:+.0f}°" if unit == "deg" else f"{vmin:.0f} mm"
            hi_s = f"{vmax:+.0f}°" if unit == "deg" else f"{vmax:.0f} mm"
            lo_t = _add_2d_text(self.ren_ui, lo_s, self.slider_x0, y_track - 0.024, 10, (0.48, 0.48, 0.55))
            hi_t = _add_2d_text(self.ren_ui, hi_s, self.slider_x1, y_track - 0.024, 10, (0.48, 0.48, 0.55))
            hi_t.GetTextProperty().SetJustificationToRight()

            self.slider_ui.append({
                "vmin": float(vmin),
                "vmax": float(vmax),
                "y": y_track,
                "unit": unit,
                "title_txt": title_txt,
                "val_txt": val_txt,
                "lo_txt": lo_t,
                "hi_txt": hi_t,
                "fill_actor": fact,
                "fill_pts": fill_pts,
                "fill_poly": fill_poly,
                "knob_pts": knob_pts,
                "knob_poly": knob_poly,
                "knob_actor": kact,
            })

    def _set_control_mode(self, mode: str):
        mode = "IK" if mode.upper() == "IK" else "FK"
        self.control_mode = mode
        self.ik_status_msg = ""
        is_ik = (mode == "IK")
        # Actualizar estilo de pestañas FK / IK
        self.tab_fk_bg.GetProperty().SetColor(*(0.14, 0.14, 0.18) if is_ik else (0.96, 0.96, 0.97))
        self.tab_fk_tx.GetTextProperty().SetColor(*(0.86, 0.86, 0.92) if is_ik else (0.08, 0.08, 0.10))
        self.tab_ik_bg.GetProperty().SetColor(*(0.20, 0.58, 0.92) if is_ik else (0.14, 0.14, 0.18))
        self.tab_ik_tx.GetTextProperty().SetColor(*(1.00, 1.00, 1.00) if is_ik else (0.86, 0.86, 0.92))
        self.txt_tel_hdr.SetInput(
            "CINEMÁTICA INVERSA · IK (X,Y,Z,Phi -> J1..J4)" if is_ik else "CINEMÁTICA DIRECTA · FK (Peter Corke fkine)"
        )
        # Sincronizar objetivo IK actual al entrar en modo IK (cero saltos!)
        if is_ik:
            tcp = self.robot.fkine_mm(np.deg2rad(self.q_deg))
            phi = float(self.q_deg[1] + self.q_deg[2] + self.q_deg[3])
            self.ik_target = np.array([tcp[0], tcp[1], tcp[2], phi], dtype=float)
        specs = self.ik_slider_specs if is_ik else self.fk_slider_specs
        for i in range(4):
            title, vmin, vmax, accent, unit = specs[i]
            ui = self.slider_ui[i]
            ui["vmin"] = float(vmin)
            ui["vmax"] = float(vmax)
            ui["unit"] = unit
            ui["title_txt"].SetInput(title)
            ui["val_txt"].GetTextProperty().SetColor(*accent)
            ui["fill_actor"].GetProperty().SetColor(*accent)
            ui["lo_txt"].SetInput(f"{vmin:+.0f}°" if unit == "deg" else f"{vmin:.0f} mm")
            ui["hi_txt"].SetInput(f"{vmax:+.0f}°" if unit == "deg" else f"{vmax:.0f} mm")
        self.update_pose(transmit=False)

    # ------------------------------------------------------------------
    # Actualización cinemática exacta de los 34 STLs + Peter Corke fkine/ikine
    # ------------------------------------------------------------------
    def _sync_sliders(self):
        if self.control_mode == "IK":
            vals = [self.ik_target[0], self.ik_target[1], self.ik_target[2], self.ik_target[3], self.grip_mm]
        else:
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
                ui["val_txt"].SetInput(f"{v:.1f} mm" if idx < 4 else f"{v:.0f} mm")

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

        # 3. Cinemática oficial Peter Corke (`fkine_all` + `jacob0` manipulabilidad + guarda 3D real)
        q_rad = np.deg2rad(self.q_deg)
        pts = self.robot.joint_positions_mm(q_rad)  # [Base, J2, J3, J4, TCP]
        tcp = pts[-1]
        safe_sim, gmsg_sim = check_physical_guard_sim(self.q_deg, g)
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
        if self.control_mode == "IK":
            self.txt_tcp.SetInput(f"q: ({q1:+.0f}°, {q2:.0f}°, {q3:+.0f}°, {q4:+.0f}°) · TCP({tcp[0]:.0f},{tcp[1]:.0f},{tcp[2]:.0f})")
        else:
            self.txt_tcp.SetInput(f"TCP: ({tcp[0]:5.1f}, {tcp[1]:5.1f}, {tcp[2]:5.1f}) mm")
        if self.relaxed:
            self.txt_phi.SetInput("SERVOS RELAJADOS (FULL_OFF 4096)")
        elif self.ik_status_msg:
            msg_short = self.ik_status_msg if len(self.ik_status_msg) <= 44 else self.ik_status_msg[:43] + "…"
            self.txt_phi.SetInput(f"[!] {msg_short}")
        elif not safe_sim:
            msg_short = gmsg_sim if len(gmsg_sim) <= 44 else gmsg_sim[:43] + "…"
            self.txt_phi.SetInput(f"[!] {msg_short}")
        else:
            self.txt_phi.SetInput(f"φ={phi_clean:+.1f}° | g={g:.0f}mm (Δx={dx:+.1f}) | w={manip:.3f}")

        # Transmisión en vivo hacia XIAO ESP32-S3 (solo si pasa guarda física 3D!)
        if transmit and not self.relaxed and safe_sim:
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
        self.target_marker.SetVisibility(False)
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
        self.target_marker.SetVisibility(False)
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
        self.target_marker.SetVisibility(False)
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

    def _apply_fk_target(self, new_q, slide_clamp: bool = True):
        """Aplica pose FK respetando límites seguros y guarda 3D real (con tope suave en slider)."""
        cand = np.array(new_q, dtype=float)
        ok, msg = check_physical_guard_sim(cand, self.grip_mm)
        if ok:
            self.q_deg = cand
            tcp = self.robot.fkine_mm(np.deg2rad(self.q_deg))
            self.ik_target = np.array([tcp[0], tcp[1], tcp[2], float(cand[1] + cand[2] + cand[3])], dtype=float)
            self.ik_status_msg = ""
            return True
        if slide_clamp:
            # Búsqueda binaria de 7 pasos para deslizar hasta el tope seguro exacto sin quedarse lejos
            lo = self.q_deg.copy()
            hi = cand.copy()
            best = None
            for _ in range(7):
                mid = 0.5 * (lo + hi)
                ok_m, _ = check_physical_guard_sim(mid, self.grip_mm)
                if ok_m:
                    best = mid
                    lo = mid
                else:
                    hi = mid
            if best is not None:
                self.q_deg = best
                tcp = self.robot.fkine_mm(np.deg2rad(self.q_deg))
                self.ik_target = np.array([tcp[0], tcp[1], tcp[2], float(best[1] + best[2] + best[3])], dtype=float)
        self.ik_status_msg = msg
        return False

    def _solve_ik_safe(self, x: float, y: float, z: float, phi: float, grip_mm: float):
        """Resuelve IK analítica + verifica límites seguros SIM_QLIM_DEG + guarda 3D física real."""
        q_rad, ok, msg = self.robot.ikine_analytic_mm(x, y, z, phi, elbow_up=True)
        if not ok:
            return None, False, msg
        qd = np.rad2deg(q_rad)
        safe, gmsg = check_physical_guard_sim(qd, grip_mm)
        if not safe:
            return None, False, gmsg
        return qd, True, "OK"

    def _apply_ik_target(self, new_ik, slide_clamp: bool = True):
        """Resuelve Cinemática Inversa analítica + guarda física 3D real y actualiza `q_deg`."""
        cand = np.array(new_ik, dtype=float)
        qd, ok, msg = self._solve_ik_safe(cand[0], cand[1], cand[2], cand[3], self.grip_mm)
        if ok:
            self.ik_target = cand
            self.q_deg = qd
            self.ik_status_msg = ""
            return True
        if slide_clamp:
            lo = self.ik_target.copy()
            hi = cand.copy()
            best_ik, best_q = None, None
            for _ in range(7):
                mid = 0.5 * (lo + hi)
                qm, ok_m, _ = self._solve_ik_safe(mid[0], mid[1], mid[2], mid[3], self.grip_mm)
                if ok_m:
                    best_ik, best_q = mid, qm
                    lo = mid
                else:
                    hi = mid
            if best_q is not None:
                self.ik_target = best_ik
                self.q_deg = best_q
        self.ik_status_msg = msg
        return False

    def go_to_ik(self, x: float, y: float, z: float, phi: float, grip_mm: float = None, linear: bool = False, steps: int = 34):
        """
        Lleva el brazo suavemente hasta la posición cartesiana exacta (X, Y, Z, Phi) por IK!
        Valida tanto el destino como la trayectoria completa contra piso, base y auto-colisión.
        """
        g_tgt = float(np.clip(self.grip_mm if grip_mm is None else grip_mm, 0.0, 30.0))
        q_tgt, ok, msg = self._solve_ik_safe(x, y, z, phi, g_tgt)
        if not ok:
            self.ik_status_msg = msg
            self.update_pose(transmit=False)
            return False, msg

        frames = []
        if linear:
            # Trayectoria rectilínea cartesiana exacta vía Peter Corke `rtb.ctraj`
            p0 = self.robot.fkine_mm(np.deg2rad(self.q_deg))
            phi0 = float(self.q_deg[1] + self.q_deg[2] + self.q_deg[3])
            T0 = SE3(p0[0] / 1000.0, p0[1] / 1000.0, p0[2] / 1000.0)
            T1 = SE3(x / 1000.0, y / 1000.0, z / 1000.0)
            Ts = rtb.ctraj(T0, T1, steps)
            phis = np.linspace(phi0, phi, steps)
            gs = np.linspace(self.grip_mm, g_tgt, steps)
            for T, ph_i, g_i in zip(Ts, phis, gs):
                p = T.t * 1000.0
                qi, oki, msgi = self._solve_ik_safe(float(p[0]), float(p[1]), float(p[2]), float(ph_i), float(g_i))
                if not oki:
                    err = f"Línea recta bloqueada en el camino ({msgi}). Usa trayectoria articular suave (jtraj)."
                    self.ik_status_msg = err
                    return False, err
                frames.append((qi, float(g_i), None, True))
        else:
            # Trayectoria articular quíntica suave `rtb.jtraj` con validación paso a paso
            tr = rtb.jtraj(np.deg2rad(self.q_deg), np.deg2rad(q_tgt), steps)
            gs = np.linspace(self.grip_mm, g_tgt, steps)
            direct_ok = True
            for qi, g_i in zip(tr.q, gs):
                qd_i = np.rad2deg(qi)
                s_ok, _ = check_physical_guard_sim(qd_i, float(g_i))
                if not s_ok:
                    direct_ok = False
                    break
                frames.append((qd_i, float(g_i), None, True))

            # Si el camino directo rosa piso/base, inserta automáticamente un punto intermedio elevado seguro!
            if not direct_ok:
                frames.clear()
                q_mid = 0.5 * (self.q_deg + q_tgt)
                q_mid[1] = float(np.clip(max(self.q_deg[1], q_tgt[1], 72.0), SIM_QLIM_DEG[1, 0], SIM_QLIM_DEG[1, 1]))
                q_mid[2] = float(np.clip(-85.0, SIM_QLIM_DEG[2, 0], SIM_QLIM_DEG[2, 1]))
                q_mid[3] = float(np.clip(0.0, SIM_QLIM_DEG[3, 0], SIM_QLIM_DEG[3, 1]))
                half = max(14, steps // 2)
                tr1 = rtb.jtraj(np.deg2rad(self.q_deg), np.deg2rad(q_mid), half)
                tr2 = rtb.jtraj(np.deg2rad(q_mid), np.deg2rad(q_tgt), half)
                g_mid = 0.5 * (self.grip_mm + g_tgt)
                for seg_q, seg_g in ((tr1.q, np.linspace(self.grip_mm, g_mid, half)),
                                     (tr2.q, np.linspace(g_mid, g_tgt, half))):
                    for qi, g_i in zip(seg_q, seg_g):
                        qd_i = np.rad2deg(qi)
                        s_ok, s_msg = check_physical_guard_sim(qd_i, float(g_i))
                        if not s_ok:
                            return False, f"Trayectoria bloqueada: {s_msg}"
                        frames.append((qd_i, float(g_i), None, True))

        self.anim_queue = frames
        self.demo_cube.SetVisibility(False)
        self.target_marker.SetVisibility(False)
        self.cube_held = False
        self.relaxed = False
        self.ik_status_msg = ""
        self.trail_pts.clear()
        self._update_trail_poly()
        self.target_marker.SetPosition(float(x), float(y), float(z))
        self.target_marker.SetVisibility(True)
        self.win.Render()
        return True, f"Moviendo a ({x:.1f}, {y:.1f}, {z:.1f}) mm · q=[{q_tgt[0]:+.1f}, {q_tgt[1]:.1f}, {q_tgt[2]:+.1f}, {q_tgt[3]:+.1f}]°"

    def go_to_fk(self, q_deg_tgt, grip_mm: float = None, steps: int = 30):
        """Lleva el brazo suavemente hasta ángulos articulares exactos (J1..J4) validados."""
        q_tgt = np.array(q_deg_tgt, dtype=float)
        g_tgt = float(np.clip(self.grip_mm if grip_mm is None else grip_mm, 0.0, 30.0))
        safe, msg = check_physical_guard_sim(q_tgt, g_tgt)
        if not safe:
            self.ik_status_msg = msg
            self.update_pose(transmit=False)
            return False, msg
        tr = rtb.jtraj(np.deg2rad(self.q_deg), np.deg2rad(q_tgt), steps)
        gs = np.linspace(self.grip_mm, g_tgt, steps)
        frames = []
        for qi, g_i in zip(tr.q, gs):
            qd_i = np.rad2deg(qi)
            s_ok, s_msg = check_physical_guard_sim(qd_i, float(g_i))
            if not s_ok:
                return False, f"Trayectoria FK bloqueada: {s_msg}"
            frames.append((qd_i, float(g_i), None, True))
        tcp_tgt = self.robot.fkine_mm(np.deg2rad(q_tgt))
        self.anim_queue = frames
        self.demo_cube.SetVisibility(False)
        self.target_marker.SetVisibility(False)
        self.cube_held = False
        self.relaxed = False
        self.ik_status_msg = ""
        self.trail_pts.clear()
        self._update_trail_poly()
        self.target_marker.SetPosition(float(tcp_tgt[0]), float(tcp_tgt[1]), float(tcp_tgt[2]))
        self.target_marker.SetVisibility(True)
        self.win.Render()
        return True, f"Moviendo a q=[{q_tgt[0]:+.1f}, {q_tgt[1]:.1f}, {q_tgt[2]:+.1f}, {q_tgt[3]:+.1f}]°"

    def _open_goto_dialog(self):
        """Diálogo B2 Stealth para escribir una posición exacta (IK o FK) y mover el brazo hasta ella."""
        if self.offscreen or self._dialog_open:
            return
        try:
            import tkinter as tk
        except Exception as exc:
            self.ik_status_msg = f"Tkinter no disponible: {exc}"
            self.update_pose(transmit=False)
            return

        self._dialog_open = True
        try:
            tcp = self.robot.fkine_mm(np.deg2rad(self.q_deg))
            phi_now = float(self.q_deg[1] + self.q_deg[2] + self.q_deg[3])

            root = tk.Tk()
            root.title("Ir a Posición Exacta — Mini-Pro 4-DOF B2 Stealth")
            root.configure(bg="#0D0D0F")
            root.resizable(False, False)
            root.attributes("-topmost", True)

            mode_var = tk.StringVar(value="IK")
            traj_var = tk.StringVar(value="jtraj")

            # Encabezado
            tk.Label(
                root, text="IR A POSICIÓN EXACTA (IK / FK)", bg="#0D0D0F", fg="#F4F4F5",
                font=("Segoe UI", 12, "bold"),
            ).pack(pady=(14, 2), padx=18, anchor="w")
            tk.Label(
                root, text="Escribe las coordenadas objetivo y el brazo se moverá suavemente validando colisiones.",
                bg="#0D0D0F", fg="#9A9AA3", font=("Segoe UI", 9),
            ).pack(pady=(0, 10), padx=18, anchor="w")

            # Selector de pestaña IK / FK
            tab_fr = tk.Frame(root, bg="#0D0D0F")
            tab_fr.pack(fill="x", padx=18, pady=(0, 10))
            btn_ik = tk.Button(tab_fr, text="Cinemática Inversa · IK (X, Y, Z, Phi)", relief="flat", bd=0, pady=6,
                               font=("Segoe UI", 9, "bold"), cursor="hand2")
            btn_fk = tk.Button(tab_fr, text="Cinemática Directa · FK (J1..J4)", relief="flat", bd=0, pady=6,
                               font=("Segoe UI", 9, "bold"), cursor="hand2")
            btn_ik.pack(side="left", expand=True, fill="x", padx=(0, 4))
            btn_fk.pack(side="left", expand=True, fill="x", padx=(4, 0))

            # Tarjeta de entradas numéricas
            card = tk.Frame(root, bg="#161619", highlightbackground="#2B2B30", highlightthickness=1, padx=14, pady=12)
            card.pack(fill="x", padx=18)

            labels_w = []
            entries_w = []
            hints_w = []
            for r in range(5):
                lbl = tk.Label(card, text="", bg="#161619", fg="#E4E4E7", font=("Segoe UI", 10, "bold"), width=18, anchor="w")
                ent = tk.Entry(card, bg="#0D0D0F", fg="#FFFFFF", insertbackground="#2294E6",
                               relief="flat", highlightbackground="#3A3A44", highlightthickness=1,
                               font=("Consolas", 11, "bold"), width=11, justify="right")
                hnt = tk.Label(card, text="", bg="#161619", fg="#7E7E8A", font=("Segoe UI", 8), anchor="w")
                lbl.grid(row=r, column=0, sticky="w", pady=4)
                ent.grid(row=r, column=1, padx=(8, 10), pady=4)
                hnt.grid(row=r, column=2, sticky="w", pady=4)
                labels_w.append(lbl)
                entries_w.append(ent)
                hints_w.append(hnt)

            # Presets rápidos (para modo IK)
            pre_fr = tk.Frame(root, bg="#0D0D0F")
            pre_fr.pack(fill="x", padx=18, pady=(10, 0))
            tk.Label(pre_fr, text="Ejemplos rápidos IK:", bg="#0D0D0F", fg="#9A9AA3", font=("Segoe UI", 8)).pack(anchor="w")
            pbtn_fr = tk.Frame(pre_fr, bg="#0D0D0F")
            pbtn_fr.pack(fill="x", pady=(4, 0))

            def fill_vals(vals):
                for e, v in zip(entries_w, vals):
                    e.delete(0, tk.END)
                    e.insert(0, f"{v:.1f}")

            def set_preset(vals):
                mode_var.set("IK")
                refresh_mode(keep_vals=False)
                fill_vals(vals)

            for title, pvals in [
                ("Frente", (145.0, 0.0, 125.0, 0.0, 15.0)),
                ("Izquierda", (125.0, 65.0, 95.0, -20.0, 15.0)),
                ("Derecha", (125.0, -65.0, 95.0, -20.0, 15.0)),
                ("Bajo Mesa", (135.0, 0.0, 50.0, -25.0, 22.0)),
            ]:
                tk.Button(
                    pbtn_fr, text=title, bg="#1F1F25", fg="#E4E4E7", activebackground="#2E2E38", activeforeground="#FFF",
                    relief="flat", bd=0, padx=8, pady=4, font=("Segoe UI", 8, "bold"), cursor="hand2",
                    command=lambda v=pvals: set_preset(v),
                ).pack(side="left", expand=True, fill="x", padx=2)

            # Tipo de trayectoria (solo relevante en IK)
            tr_fr = tk.Frame(root, bg="#0D0D0F")
            tr_fr.pack(fill="x", padx=18, pady=(10, 4))
            tk.Radiobutton(
                tr_fr, text="Trayectoria suave (jtraj · recomendada)", variable=traj_var, value="jtraj",
                bg="#0D0D0F", fg="#E4E4E7", selectcolor="#161619", activebackground="#0D0D0F",
                activeforeground="#FFF", font=("Segoe UI", 9),
            ).pack(anchor="w")
            tk.Radiobutton(
                tr_fr, text="Línea recta cartesiana exacta (ctraj)", variable=traj_var, value="ctraj",
                bg="#0D0D0F", fg="#E4E4E7", selectcolor="#161619", activebackground="#0D0D0F",
                activeforeground="#FFF", font=("Segoe UI", 9),
            ).pack(anchor="w")

            status_lbl = tk.Label(root, text="", bg="#0D0D0F", fg="#F97316", font=("Segoe UI", 9, "bold"), wraplength=390, justify="left")
            status_lbl.pack(fill="x", padx=18, pady=(4, 6))

            def refresh_mode(keep_vals: bool = False):
                is_ik = (mode_var.get() == "IK")
                btn_ik.configure(bg="#2294E6" if is_ik else "#1B1B20", fg="#FFFFFF" if is_ik else "#A1A1AA")
                btn_fk.configure(bg="#F4F4F5" if not is_ik else "#1B1B20", fg="#0D0D0F" if not is_ik else "#A1A1AA")
                if is_ik:
                    meta = [
                        ("X · Alcance (mm)", "35 .. 199 mm", tcp[0]),
                        ("Y · Lateral (mm)", "-170 .. +170 mm", tcp[1]),
                        ("Z · Altura (mm)",  "12 .. 260 mm", tcp[2]),
                        ("Phi · Pinza (°)",  "-90 .. +90°", phi_now),
                        ("Pinza · Apertura", "0 .. 30 mm", self.grip_mm),
                    ]
                else:
                    meta = [
                        ("J1 · Base (°)",   f"{SIM_QLIM_DEG[0,0]:+.0f} .. {SIM_QLIM_DEG[0,1]:+.0f}°", self.q_deg[0]),
                        ("J2 · Hombro (°)", f"{SIM_QLIM_DEG[1,0]:+.0f} .. {SIM_QLIM_DEG[1,1]:+.0f}°", self.q_deg[1]),
                        ("J3 · Codo (°)",   f"{SIM_QLIM_DEG[2,0]:+.0f} .. {SIM_QLIM_DEG[2,1]:+.0f}°", self.q_deg[2]),
                        ("J4 · Muñeca (°)", f"{SIM_QLIM_DEG[3,0]:+.0f} .. {SIM_QLIM_DEG[3,1]:+.0f}°", self.q_deg[3]),
                        ("Pinza · Apertura", "0 .. 30 mm", self.grip_mm),
                    ]
                for idx, (t, h, v) in enumerate(meta):
                    labels_w[idx].configure(text=t)
                    hints_w[idx].configure(text=h)
                    if not keep_vals:
                        entries_w[idx].delete(0, tk.END)
                        entries_w[idx].insert(0, f"{v:.1f}")
                status_lbl.configure(text="")

            btn_ik.configure(command=lambda: (mode_var.set("IK"), refresh_mode()))
            btn_fk.configure(command=lambda: (mode_var.set("FK"), refresh_mode()))
            refresh_mode()

            def on_submit(_evt=None):
                try:
                    vals = [float(e.get().strip().replace(",", ".")) for e in entries_w]
                except ValueError:
                    status_lbl.configure(text="Ingresa solo números válidos (ej. 130.0, -25.0).")
                    return
                if mode_var.get() == "IK":
                    ok, msg = self.go_to_ik(vals[0], vals[1], vals[2], vals[3], grip_mm=vals[4],
                                            linear=(traj_var.get() == "ctraj"))
                    if ok:
                        self._set_control_mode("IK")
                        self.ik_target = np.array(vals[:4], dtype=float)
                        root.destroy()
                    else:
                        status_lbl.configure(text=f"⚠ {msg}")
                else:
                    ok, msg = self.go_to_fk(vals[:4], grip_mm=vals[4])
                    if ok:
                        self._set_control_mode("FK")
                        root.destroy()
                    else:
                        status_lbl.configure(text=f"⚠ {msg}")

            act_fr = tk.Frame(root, bg="#0D0D0F")
            act_fr.pack(fill="x", padx=18, pady=(6, 16))
            tk.Button(
                act_fr, text="Cancelar (Esc)", command=root.destroy, bg="#1F1F25", fg="#D4D4D8",
                relief="flat", bd=0, padx=14, pady=8, font=("Segoe UI", 9, "bold"), cursor="hand2",
            ).pack(side="left")
            tk.Button(
                act_fr, text="Mover brazo a esta posición (Enter)", command=on_submit, bg="#2294E6", fg="#FFFFFF",
                activebackground="#1978BD", activeforeground="#FFFFFF",
                relief="flat", bd=0, padx=16, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2",
            ).pack(side="right", fill="x", expand=True, padx=(8, 0))

            root.bind("<Return>", on_submit)
            root.bind("<Escape>", lambda _e: root.destroy())
            entries_w[0].focus_set()
            entries_w[0].select_range(0, tk.END)
            root.mainloop()
        finally:
            self._dialog_open = False

    def _trigger_action(self, bid: str):
        if bid == "mode_fk":
            self._set_control_mode("FK")
        elif bid == "mode_ik":
            self._set_control_mode("IK")
        elif bid == "goto":
            self._open_goto_dialog()
        elif bid == "hero":
            self.ik_status_msg = ""
            self._queue_move(np.rad2deg(Q_HERO_RAD), HERO_GRIP)
        elif bid == "home":
            self.ik_status_msg = ""
            self._queue_move(np.rad2deg(Q_HOME_RAD), 15.0)
        elif bid == "jtraj":
            self.ik_status_msg = ""
            self._start_demo_jtraj()
        elif bid == "ctraj":
            self.ik_status_msg = ""
            self._start_demo_ctraj()
        elif bid == "xray":
            self.xray = not self.xray
            self._apply_visual_toggles()
        elif bid == "kin":
            self.show_kin = not self.show_kin
            self._apply_visual_toggles()
        elif bid == "relax":
            self.anim_queue.clear()
            self.target_marker.SetVisibility(False)
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
        self.target_marker.SetVisibility(False)
        self.cube_held = False
        self.relaxed = False
        if idx < 4:
            if self.control_mode == "IK":
                cand = self.ik_target.copy()
                cand[idx] = val
                self._apply_ik_target(cand, slide_clamp=True)
            else:
                cand_q = self.q_deg.copy()
                cand_q[idx] = val
                self._apply_fk_target(cand_q, slide_clamp=True)
        else:
            ok_g, msg_g = check_physical_guard_sim(self.q_deg, val)
            if ok_g:
                self.grip_mm = val
                self.ik_status_msg = ""
            else:
                self.ik_status_msg = msg_g
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
                step = (5.0 if s_idx < 3 else 3.0) if (self.control_mode == "IK" and s_idx < 4) else (2.0 if s_idx < 4 else 1.0)
                self.anim_queue.clear()
                self.target_marker.SetVisibility(False)
                self.relaxed = False
                if s_idx < 4:
                    if self.control_mode == "IK":
                        cand = self.ik_target.copy()
                        cand[s_idx] = float(np.clip(cand[s_idx] + direction * step, ui["vmin"], ui["vmax"]))
                        self._apply_ik_target(cand, slide_clamp=True)
                    else:
                        cand_q = self.q_deg.copy()
                        cand_q[s_idx] = float(np.clip(cand_q[s_idx] + direction * step, ui["vmin"], ui["vmax"]))
                        self._apply_fk_target(cand_q, slide_clamp=True)
                else:
                    cand_g = float(np.clip(self.grip_mm + direction * step, ui["vmin"], ui["vmax"]))
                    ok_g, msg_g = check_physical_guard_sim(self.q_deg, cand_g)
                    if ok_g:
                        self.grip_mm = cand_g
                        self.ik_status_msg = ""
                    else:
                        self.ik_status_msg = msg_g
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
        if self._dialog_open:
            return
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
        elif key == "f":
            self._set_control_mode("FK")
        elif key == "i":
            self._set_control_mode("IK")
        elif key == "g":
            self._trigger_action("goto")
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
        if self._dialog_open:
            return
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
            tcp = self.robot.fkine_mm(np.deg2rad(self.q_deg))
            self.ik_target = np.array([tcp[0], tcp[1], tcp[2], float(self.q_deg[1] + self.q_deg[2] + self.q_deg[3])], dtype=float)
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
    parser.add_argument("--goto", nargs=4, type=float, metavar=("X", "Y", "Z", "PHI"),
                        help="Inicia moviendo el brazo suavemente a la posición IK (mm, mm, mm, deg)")
    args = parser.parse_args()

    link = ArmLink(port=args.port, baud=args.baud, wifi_ip=args.wifi, udp_port=args.udp_port)
    app = DigitalTwinApp(link=link, offscreen=False)
    if args.goto:
        app._set_control_mode("IK")
        ok, msg = app.go_to_ik(*args.goto)
        print(f"[GOTO] {msg}")
    app.run()


if __name__ == "__main__":
    main()
