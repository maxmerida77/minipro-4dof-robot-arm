"""
Modelo Oficial Peter Corke (`roboticstoolbox-python`) — Brazo Mini-Pro 4-DOF B2 Stealth
=======================================================================================
Parámetros Denavit-Hartenberg Estándar leídos directamente de `cad/params.py`
(Single Source of Truth) para concordancia al milímetro con el CAD 3D:
  - d1 = 82 mm  (0.082 m)  Base escritorio -> eje Hombro J2
  - a2 = 82 mm  (0.082 m)  Hombro J2 -> Codo J3
  - a3 = 70 mm  (0.070 m)  Codo J3 -> Muñeca J4
  - a4 = 53 mm  (0.053 m)  Muñeca J4 -> centro de pinza TCP

Nota de unidades:
  El modelo `DHRobot` de Peter Corke usa metros (m) internamente para que los gráficos
  nativos `robot.plot()` tengan proporciones ideales; las funciones auxiliares reciben y
  reportan coordenadas cartesianas en milímetros (mm) para coincidir con el CAD.
"""

import os
import sys
import math
import numpy as np
import roboticstoolbox as rtb
from spatialmath import SE3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "cad"))

from params import (
    D1_BASE_TO_SHOULDER as D1_MM,
    A2_LOWER_ARM as A2_MM,
    A3_FOREARM as A3_MM,
    A4_WRIST_TO_TCP as A4_MM,
    BASE_DIA as BASE_DIA_MM,
    TABLE_SAFE_Z_TCP_MM,
    TABLE_SAFE_Z_JOINT_MM,
    Q_LIMITS_DEG,
    HERO_POSE_DEG,
    gripper_kinematics_v4,
)

QLIM_DEG = np.array([
    Q_LIMITS_DEG["q1_base"],
    Q_LIMITS_DEG["q2_shoulder"],
    Q_LIMITS_DEG["q3_elbow"],
    Q_LIMITS_DEG["q4_wrist"],
], dtype=float)
QLIM_RAD = np.deg2rad(QLIM_DEG)

Q_HERO_RAD = np.deg2rad([
    HERO_POSE_DEG["q1"],
    HERO_POSE_DEG["q2"],
    HERO_POSE_DEG["q3"],
    HERO_POSE_DEG["q4"],
])
Q_HOME_RAD = np.deg2rad([0.0, 90.0, -90.0, 0.0])


class MiniPro4DOF(rtb.DHRobot):
    """Brazo robótico de escritorio Mini-Pro 4-DOF (Estilo B2 Stealth) en Peter Corke RTB."""

    def __init__(self):
        links = [
            rtb.RevoluteDH(d=D1_MM / 1000.0, a=0.0,            alpha=math.pi / 2.0, qlim=QLIM_RAD[0]),
            rtb.RevoluteDH(d=0.0,            a=A2_MM / 1000.0, alpha=0.0,           qlim=QLIM_RAD[1]),
            rtb.RevoluteDH(d=0.0,            a=A3_MM / 1000.0, alpha=0.0,           qlim=QLIM_RAD[2]),
            rtb.RevoluteDH(d=0.0,            a=A4_MM / 1000.0, alpha=0.0,           qlim=QLIM_RAD[3]),
        ]
        super().__init__(
            links,
            name="MiniPro-4DOF-B2-Stealth",
            manufacturer="DIY Bambu A1 / 4x MG90S + SG90 (UNIT)",
        )
        self.addconfiguration("hero", Q_HERO_RAD)
        self.addconfiguration("home", Q_HOME_RAD)
        self.qr = Q_HERO_RAD
        self.qz = np.zeros(4)

    def fkine_mm(self, q_rad: np.ndarray) -> np.ndarray:
        """Devuelve la posición TCP [X, Y, Z] en milímetros usando `robot.fkine` de Peter Corke."""
        T: SE3 = self.fkine(q_rad)
        return np.asarray(T.t, dtype=float) * 1000.0

    def joint_positions_mm(self, q_rad: np.ndarray) -> np.ndarray:
        """Devuelve las posiciones 3D (5x3 en mm) de [Base, J2, J3, J4, TCP] vía `fkine_all`."""
        Ts = self.fkine_all(q_rad)
        pts = [np.zeros(3)]
        for k in range(1, len(Ts)):
            pts.append(np.asarray(Ts[k].t, dtype=float) * 1000.0)
        return np.array(pts)

    @staticmethod
    def ikine_analytic_mm(x_mm: float, y_mm: float, z_mm: float, phi_deg: float = 0.0, elbow_up: bool = True):
        """
        Cinemática Inversa Analítica 4R exacta (en mm y grados):
          - x_mm, y_mm, z_mm : Posición deseada del TCP (Z=0 es el escritorio).
          - phi_deg          : Inclinación de la pinza en el plano vertical del brazo
                               (0° horizontal, -90° vertical hacia abajo).
          - elbow_up         : True = codo arriba (recomendado sobre escritorio).
        Retorna: (q_rad, ok, msg)
        """
        phi = math.radians(phi_deg)
        q1 = math.atan2(y_mm, x_mm)
        r = math.hypot(x_mm, y_mm)

        rw = r - A4_MM * math.cos(phi)
        zw = (z_mm - D1_MM) - A4_MM * math.sin(phi)

        dist2 = rw * rw + zw * zw
        D = (dist2 - A2_MM * A2_MM - A3_MM * A3_MM) / (2.0 * A2_MM * A3_MM)
        if abs(D) > 1.0 + 1e-9:
            return None, False, f"Fuera de alcance geométrico (D={D:.4f})"
        D = max(-1.0, min(1.0, D))

        q3 = math.atan2(-math.sqrt(1.0 - D * D), D) if elbow_up else math.atan2(math.sqrt(1.0 - D * D), D)
        q2 = math.atan2(zw, rw) - math.atan2(A3_MM * math.sin(q3), A2_MM + A3_MM * math.cos(q3))
        q4 = math.atan2(math.sin(phi - q2 - q3), math.cos(phi - q2 - q3))

        q = np.array([q1, q2, q3, q4], dtype=float)
        tol = math.radians(0.1)
        names = ["J1 Base", "J2 Hombro", "J3 Codo", "J4 Muñeca"]
        for i in range(4):
            if q[i] < QLIM_RAD[i, 0] - tol or q[i] > QLIM_RAD[i, 1] + tol:
                return q, False, f"{names[i]} fuera de límite: {math.degrees(q[i]):.1f}°"
        return q, True, "OK"

    def tcp_se3_mm(self, x_mm: float, y_mm: float, z_mm: float, phi_deg: float = 0.0) -> SE3:
        """Construye un objeto `spatialmath.SE3` (en metros) compatible con `rtb.ctraj`."""
        q, ok, msg = self.ikine_analytic_mm(x_mm, y_mm, z_mm, phi_deg, elbow_up=True)
        if not ok:
            raise ValueError(f"Pose ({x_mm}, {y_mm}, {z_mm}, phi={phi_deg}°) inalcanzable: {msg}")
        return self.fkine(q)

    @staticmethod
    def grip_kinematics(grip_open_mm: float):
        """Relación trigonométrica exacta de la Pinza Paralela MeArm Mod 1.5 (`cad/params.py`)."""
        return gripper_kinematics_v4(grip_open_mm)

    def check_table_guard(self, q_rad: np.ndarray, grip_open_mm: float = 15.0):
        """
        Guarda cinemática anti-mesa sincronizada con el firmware (`config.h`):
        verifica que ni J3, ni J4 (< 22 mm), ni el TCP real compensado por apertura de pinza (< 8 mm)
        choquen con la superficie del escritorio (Z = 0).
        Retorna: (ok, z_j3, z_j4, z_tcp, msg)
        """
        q2, q3, q4 = float(q_rad[1]), float(q_rad[2]), float(q_rad[3])
        _th, tcp_x_eff, _dx, _sdeg = gripper_kinematics_v4(grip_open_mm)
        z_j3 = D1_MM + A2_MM * math.sin(q2)
        z_j4 = z_j3 + A3_MM * math.sin(q2 + q3)
        z_tcp = z_j4 + tcp_x_eff * math.sin(q2 + q3 + q4)
        if z_j3 < TABLE_SAFE_Z_JOINT_MM:
            return False, z_j3, z_j4, z_tcp, f"Codo J3 muy bajo (Z={z_j3:.1f} < {TABLE_SAFE_Z_JOINT_MM:.0f} mm)"
        if z_j4 < TABLE_SAFE_Z_JOINT_MM:
            return False, z_j3, z_j4, z_tcp, f"Muñeca J4 muy baja (Z={z_j4:.1f} < {TABLE_SAFE_Z_JOINT_MM:.0f} mm)"
        if z_tcp < TABLE_SAFE_Z_TCP_MM:
            return False, z_j3, z_j4, z_tcp, f"TCP/Pinza chocaría con mesa (Z={z_tcp:.1f} < {TABLE_SAFE_Z_TCP_MM:.0f} mm)"
        return True, z_j3, z_j4, z_tcp, "OK"


if __name__ == "__main__":
    robot = MiniPro4DOF()
    print(robot)
    tcp = robot.fkine_mm(Q_HERO_RAD)
    q_chk, ok, msg = robot.ikine_analytic_mm(tcp[0], tcp[1], tcp[2], 0.0, True)
    print(f"TCP Pose Héroe (mm): {tcp.round(2)} | IK: {msg} | Error máx: {np.max(np.abs(np.rad2deg(Q_HERO_RAD - q_chk))):.2e} deg")
