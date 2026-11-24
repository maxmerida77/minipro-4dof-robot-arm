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
    GRIP_V4,
    gripper_kinematics_v4,
    gripper_grip_point_local_v4,
    check_physical_guard_v4,
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
    def _solve_ik_planar(q1: float, r_signed: float, z_mm: float, phi_deg: float, elbow_up: bool,
                         eff_x_mm: float = A4_MM, eff_z_mm: float = 0.0):
        """Resuelve la cadena planar 2R+muñeca con radio firmado y offset opcional (eff_x, eff_z)."""
        phi = math.radians(phi_deg)
        c_p, s_p = math.cos(phi), math.sin(phi)
        # Punto en marco J4 -> (eff_x*cos(phi) - eff_z*sin(phi), eff_x*sin(phi) + eff_z*cos(phi))
        rw = r_signed - (eff_x_mm * c_p - eff_z_mm * s_p)
        zw = (z_mm - D1_MM) - (eff_x_mm * s_p + eff_z_mm * c_p)

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
        return np.clip(q, QLIM_RAD[:, 0], QLIM_RAD[:, 1]), True, "OK"

    @staticmethod
    def ikine_analytic_mm(
        x_mm: float, y_mm: float, z_mm: float, phi_deg: float = 0.0,
        elbow_up: bool = True, q1_ref_rad: float = 0.0,
        eff_x_mm: float = A4_MM, eff_z_mm: float = 0.0,
    ):
        """
        Cinemática Inversa Analítica 4R exacta (en mm y grados) con soporte de radio firmado:
          - Rechaza entradas no finitas (`NaN`/`Inf`).
          - Si `r ≈ 0`, conserva `q1_ref_rad` sin saltos espurios de base.
          - Si la rama frontal (`r > 0`) saca a `J1` de `[-85°, +85°]` (p. ej. poses sobre el hombro
            hacia atrás como `(0, 145, 20, 80)` con `X < 0`), evalúa automáticamente la rama
            de radio negativo (`q1 ± π`, `r_signed = -r`).
        Retorna: (q_rad, ok, msg)
        """
        vals = (float(x_mm), float(y_mm), float(z_mm), float(phi_deg), float(q1_ref_rad), float(eff_x_mm), float(eff_z_mm))
        if not all(math.isfinite(v) for v in vals):
            return None, False, "Entrada no finita (NaN/Inf) rechazada"

        r = math.hypot(x_mm, y_mm)
        if r < 1e-4:
            q1_fwd = float(np.clip(q1_ref_rad, QLIM_RAD[0, 0], QLIM_RAD[0, 1]))
            candidates = [(q1_fwd, 0.0)]
        else:
            q1_fwd = math.atan2(y_mm, x_mm)
            q1_rev = math.atan2(math.sin(q1_fwd + math.pi), math.cos(q1_fwd + math.pi))
            # Priorizar la rama con q1 dentro de límites (o frontal primero si ambas cumplen)
            candidates = [(q1_fwd, +r), (q1_rev, -r)]

        first_fail = (None, False, "Fuera de alcance")
        for eu_c in (elbow_up, not elbow_up):
            for q1_c, r_c in candidates:
                q_sol, ok, msg = MiniPro4DOF._solve_ik_planar(q1_c, r_c, z_mm, phi_deg, eu_c, eff_x_mm, eff_z_mm)
                if ok:
                    return q_sol, True, "OK"
                if first_fail[0] is None:
                    first_fail = (q_sol, False, msg)
        return first_fail

    def fkine_grip_mm(self, q_rad: np.ndarray, grip_open_mm: float = 15.0) -> np.ndarray:
        """
        Posición 3D REAL del centro de agarre entre las almohadillas blancas `w04` (mm),
        incluyendo el desplazamiento longitudinal `tcp_x(g)` y la altura local `Z = +5.80 mm`
        respecto al TCP académico DH (`a4 = 53.0 mm`).
        """
        q1, q2, q3, q4 = [float(v) for v in q_rad]
        gx_loc, _gy, gz_loc = gripper_grip_point_local_v4(grip_open_mm)
        phi = q2 + q3 + q4
        r = A2_MM * math.cos(q2) + A3_MM * math.cos(q2 + q3) + gx_loc * math.cos(phi) - gz_loc * math.sin(phi)
        z = D1_MM + A2_MM * math.sin(q2) + A3_MM * math.sin(q2 + q3) + gx_loc * math.sin(phi) + gz_loc * math.cos(phi)
        return np.array([r * math.cos(q1), r * math.sin(q1), z], dtype=float)

    def ikine_grip_mm(
        self, x_mm: float, y_mm: float, z_mm: float, phi_deg: float = 0.0,
        grip_open_mm: float = 15.0, elbow_up: bool = True, q1_ref_rad: float = 0.0,
    ):
        """IK analítica apuntando el centro REAL de las almohadillas `w04` (con apertura `grip_open_mm` y `Z_pad=+5.8 mm`)."""
        if not math.isfinite(float(grip_open_mm)):
            return None, False, "Apertura de pinza no finita (NaN/Inf)"
        gx_loc, _gy, gz_loc = gripper_grip_point_local_v4(grip_open_mm)
        return self.ikine_analytic_mm(
            x_mm, y_mm, z_mm, phi_deg, elbow_up=elbow_up, q1_ref_rad=q1_ref_rad,
            eff_x_mm=gx_loc, eff_z_mm=gz_loc,
        )

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

    def check_physical_guard(self, q_rad: np.ndarray, grip_open_mm: float = 15.0):
        """Guarda física 3D completa desde `cad/params.py` (límites + mesa/SG90 + base + auto-colisión)."""
        return check_physical_guard_v4(np.rad2deg(q_rad), grip_open_mm)

    def check_table_guard(self, q_rad: np.ndarray, grip_open_mm: float = 15.0):
        """
        Guarda física completa sincronizada con `cad/params.py` y el firmware (`config.h`):
        verifica límites seguros, altura libre real (incluyendo panza SG90 `-21.8 mm` y puntas
        de dedos `+7.1 mm`), despeje contra la base cilíndrica Ø106 mm y auto-colisión L4 vs L2.
        Retorna: (ok, z_j3, z_j4, z_tcp, msg)
        """
        q2, q3, q4 = float(q_rad[1]), float(q_rad[2]), float(q_rad[3])
        _th, tcp_x_eff, _dx, _sdeg = gripper_kinematics_v4(grip_open_mm)
        z_j3 = D1_MM + A2_MM * math.sin(q2)
        z_j4 = z_j3 + A3_MM * math.sin(q2 + q3)
        z_tcp = z_j4 + tcp_x_eff * math.sin(q2 + q3 + q4)
        ok_phys, msg_phys = check_physical_guard_v4(np.rad2deg(q_rad), grip_open_mm)
        if not ok_phys:
            return False, z_j3, z_j4, z_tcp, msg_phys
        return True, z_j3, z_j4, z_tcp, "OK"


if __name__ == "__main__":
    robot = MiniPro4DOF()
    print(robot)
    tcp = robot.fkine_mm(Q_HERO_RAD)
    q_chk, ok, msg = robot.ikine_analytic_mm(tcp[0], tcp[1], tcp[2], 0.0, True)
    print(f"TCP Pose Héroe (mm): {tcp.round(2)} | IK: {msg} | Error máx: {np.max(np.abs(np.rad2deg(Q_HERO_RAD - q_chk))):.2e} deg")
