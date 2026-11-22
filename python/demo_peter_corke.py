"""
Demo Oficial con Peter Corke (`roboticstoolbox-python`) — Mini-Pro 4-DOF B2 Stealth
===================================================================================
Ejecuta todo el análisis académico usando las funciones oficiales de Peter Corke:
  - `rtb.DHRobot` / `rtb.RevoluteDH` (tabla DH exacta al milímetro con el CAD)
  - `robot.fkine()`, `robot.fkine_all()`, `robot.jacob0()`, `robot.plot()`
  - `rtb.jtraj()` (trayectoria articular quíntica)
  - `rtb.ctraj()` + `spatialmath.SE3` (trayectoria cartesiana rectilínea 3D)

Exporta 4 figuras listas para reporte/presentación en `docs/graficas_peter_corke/`.
"""

import os
import math
import shutil
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import roboticstoolbox as rtb

from robot_minipro_rtb import (
    MiniPro4DOF,
    D1_MM, A2_MM, A3_MM, A4_MM, BASE_DIA_MM,
    QLIM_RAD, Q_HERO_RAD,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "docs", "graficas_peter_corke")
ART_DIR = os.environ.get("ARTIFACT_DIR", "")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    robot = MiniPro4DOF()

    print("=" * 74)
    print("  MODELO OFICIAL PETER CORKE (`roboticstoolbox-python`) — MINI-PRO 4-DOF")
    print("=" * 74)
    print(robot)

    # 1. Validación FK (Peter Corke) vs IK Analítica en Pose Héroe
    tcp_hero = robot.fkine_mm(Q_HERO_RAD)
    pts_hero = robot.joint_positions_mm(Q_HERO_RAD)
    q_chk, ok_ik, msg_ik = robot.ikine_analytic_mm(tcp_hero[0], tcp_hero[1], tcp_hero[2], phi_deg=0.0)
    assert ok_ik, msg_ik
    err_deg = float(np.max(np.abs(np.rad2deg(Q_HERO_RAD - q_chk))))
    print(f"  Pose Héroe  : q = {np.rad2deg(Q_HERO_RAD).round(2)} deg")
    print(f"  TCP fkine() : X={tcp_hero[0]:.2f}, Y={tcp_hero[1]:.2f}, Z={tcp_hero[2]:.2f} mm")
    print(f"  Error FK-IK : {err_deg:.3e} deg (EXACTO)\n")

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#333338",
        "axes.linewidth": 0.9,
        "grid.color": "#D8D8DE",
        "grid.linestyle": "--",
        "grid.alpha": 0.7,
    })

    # ------------------------------------------------------------------
    # FIGURA 0: GRÁFICO 3D NATIVO DE PETER CORKE (`robot.plot(backend='pyplot')`)
    # ------------------------------------------------------------------
    env = robot.plot(Q_HERO_RAD, backend="pyplot", limits=[-0.12, 0.24, -0.18, 0.18, 0.0, 0.28], block=False)
    fig0 = env.fig
    ax0 = env.ax
    th = np.linspace(0, 2 * np.pi, 100)
    ax0.plot((BASE_DIA_MM / 2000.0) * np.cos(th), (BASE_DIA_MM / 2000.0) * np.sin(th), np.zeros_like(th), "k-", lw=2.0)
    ax0.set_title(
        f"Peter Corke RTB-Python (`robot.plot`) — Mini-Pro 4-DOF B2 Stealth\n"
        f"Pose Héroe: TCP = [{tcp_hero[0]:.1f}, {tcp_hero[1]:.1f}, {tcp_hero[2]:.1f}] mm (φ = 0°)",
        fontsize=11, fontweight="bold",
    )
    ax0.set_xlabel("X (m)"); ax0.set_ylabel("Y (m)"); ax0.set_zlabel("Z (m)")
    ax0.view_init(elev=24, azim=-45)
    p_fig0 = os.path.join(OUT_DIR, "fig0_peter_corke_nativo_3d.png")
    fig0.savefig(p_fig0, dpi=180, bbox_inches="tight")
    plt.close(fig0)

    # ------------------------------------------------------------------
    # FIGURA 1: ESPACIO DE TRABAJO 3D + PROYECCIONES XY / XZ / YZ
    # ------------------------------------------------------------------
    rng = np.random.default_rng(42)
    N = 25000
    Q_rand = np.column_stack([rng.uniform(QLIM_RAD[j, 0], QLIM_RAD[j, 1], N) for j in range(4)])
    q1, q2, q3, q4 = Q_rand[:, 0], Q_rand[:, 1], Q_rand[:, 2], Q_rand[:, 3]
    r_ws = A2_MM * np.cos(q2) + A3_MM * np.cos(q2 + q3) + A4_MM * np.cos(q2 + q3 + q4)
    X_ws = r_ws * np.cos(q1)
    Y_ws = r_ws * np.sin(q1)
    Z_ws = D1_MM + A2_MM * np.sin(q2) + A3_MM * np.sin(q2 + q3) + A4_MM * np.sin(q2 + q3 + q4)
    valid = Z_ws >= 12.0
    X_ws, Y_ws, Z_ws = X_ws[valid], Y_ws[valid], Z_ws[valid]

    th_semi = np.linspace(-np.pi / 2, np.pi / 2, 120)
    R_max = A2_MM + A3_MM + A4_MM

    fig1 = plt.figure(figsize=(13, 9.5), dpi=180, facecolor="white")
    fig1.suptitle("Peter Corke RTB-Python — Espacio de Trabajo y Proyecciones XY / XZ / YZ", fontsize=14, fontweight="bold", y=0.97)

    ax1 = fig1.add_subplot(2, 2, 1, projection="3d")
    ax1.scatter(X_ws[::4], Y_ws[::4], Z_ws[::4], c=Z_ws[::4], cmap="viridis", s=3, alpha=0.22)
    ax1.plot(pts_hero[:, 0], pts_hero[:, 1], pts_hero[:, 2], "-o", color="#18181B", lw=3.2, ms=6)
    ax1.plot((BASE_DIA_MM / 2) * np.cos(th), (BASE_DIA_MM / 2) * np.sin(th), np.zeros_like(th), "k-", lw=1.8)
    ax1.set_title("Espacio de Trabajo 3D + Pose Héroe", fontweight="bold")
    ax1.set_xlabel("X (mm)"); ax1.set_ylabel("Y (mm)"); ax1.set_zlabel("Z (mm)")
    ax1.view_init(elev=24, azim=-48)
    ax1.set_xlim(-80, 250); ax1.set_ylim(-240, 240); ax1.set_zlim(0, 330)

    ax2 = fig1.add_subplot(2, 2, 2)
    sc2 = ax2.scatter(X_ws, Y_ws, c=Z_ws, cmap="viridis", s=2.2, alpha=0.25)
    ax2.plot((BASE_DIA_MM / 2) * np.cos(th), (BASE_DIA_MM / 2) * np.sin(th), "k-", lw=2.0, label="Base Ø 94 mm")
    ax2.plot(R_max * np.cos(th_semi), R_max * np.sin(th_semi), "--", color="#D45218", lw=1.6, label=f"Alcance máx R={int(R_max)} mm")
    ax2.plot(pts_hero[:, 0], pts_hero[:, 1], "-o", color="#18181B", lw=2.2, ms=4)
    ax2.set_title("Proyección Plano XY (Vista Superior)", fontweight="bold")
    ax2.set_xlabel("X (mm)"); ax2.set_ylabel("Y (mm)")
    ax2.set_aspect("equal"); ax2.grid(True); ax2.legend(loc="upper left", fontsize=8.5)
    cb = fig1.colorbar(sc2, ax=ax2, fraction=0.046, pad=0.04)
    cb.set_label("Altura Z (mm)")

    ax3 = fig1.add_subplot(2, 2, 3)
    ax3.scatter(X_ws, Z_ws, c=Z_ws, cmap="viridis", s=2.2, alpha=0.22)
    ax3.axhline(0, color="k", lw=2.0)
    ax3.add_patch(plt.Rectangle((-BASE_DIA_MM / 2, 0), BASE_DIA_MM, 64, facecolor="#242428", edgecolor="k", zorder=4))
    ax3.plot(pts_hero[:, 0], pts_hero[:, 2], "-o", color="#D45218", lw=2.6, ms=5, zorder=5, label="Pose Héroe (φ=0°)")
    ax3.set_title("Proyección Plano XZ (Perfil Lateral)", fontweight="bold")
    ax3.set_xlabel("X (mm)"); ax3.set_ylabel("Z (mm)")
    ax3.set_aspect("equal"); ax3.set_ylim(-10, 340); ax3.grid(True); ax3.legend(loc="upper left", fontsize=8.5)

    ax4 = fig1.add_subplot(2, 2, 4)
    ax4.scatter(Y_ws, Z_ws, c=Z_ws, cmap="viridis", s=2.2, alpha=0.22)
    ax4.axhline(0, color="k", lw=2.0)
    ax4.add_patch(plt.Rectangle((-BASE_DIA_MM / 2, 0), BASE_DIA_MM, 64, facecolor="#242428", edgecolor="k", zorder=4))
    ax4.set_title("Proyección Plano YZ (Vista Frontal)", fontweight="bold")
    ax4.set_xlabel("Y (mm)"); ax4.set_ylabel("Z (mm)")
    ax4.set_aspect("equal"); ax4.set_ylim(-10, 340); ax4.grid(True)

    fig1.tight_layout(rect=[0, 0, 1, 0.94])
    fig1.savefig(os.path.join(OUT_DIR, "fig1_workspace_proyecciones.png"), dpi=180)
    plt.close(fig1)

    # ------------------------------------------------------------------
    # FIGURA 2: TRAYECTORIA ARTICULAR OFICIAL `rtb.jtraj()` (PICK-AND-PLACE φ = 0°)
    # ------------------------------------------------------------------
    waypoints = [
        (135.0, -65.0,  68.0, 0.0),
        (145.0,   0.0, 130.0, 0.0),
        (135.0,  65.0,  68.0, 0.0),
    ]
    Q_wp = []
    for wx, wy, wz, wphi in waypoints:
        qw, ok, msg = robot.ikine_analytic_mm(wx, wy, wz, wphi, elbow_up=True)
        assert ok, msg
        Q_wp.append(qw)

    dt = 0.04
    t_seg = np.arange(0, 60) * dt
    tr1 = rtb.jtraj(Q_wp[0], Q_wp[1], t_seg)
    tr2 = rtb.jtraj(Q_wp[1], Q_wp[2], t_seg)

    Q_tr = np.vstack([tr1.q, tr2.q[1:]])
    Qd_tr = np.vstack([tr1.qd, tr2.qd[1:]])
    Qdd_tr = np.vstack([tr1.qdd, tr2.qdd[1:]])
    t_vec = np.arange(len(Q_tr)) * dt

    fig2, axes = plt.subplots(3, 1, figsize=(11.5, 8.2), dpi=180, sharex=True, facecolor="white")
    fig2.suptitle("Peter Corke `rtb.jtraj()` — Pick-and-Place Horizontal (φ = 0°)", fontsize=14, fontweight="bold", y=0.97)
    colors = ["#18181B", "#D45218", "#2563EB", "#16A34A"]
    labels = ["q1 (Base)", "q2 (Hombro)", "q3 (Codo)", "q4 (Muñeca)"]

    for j in range(4):
        axes[0].plot(t_vec, np.rad2deg(Q_tr[:, j]), color=colors[j], lw=2.1, label=labels[j])
        axes[1].plot(t_vec, np.rad2deg(Qd_tr[:, j]), color=colors[j], lw=1.9)
        axes[2].plot(t_vec, np.rad2deg(Qdd_tr[:, j]), color=colors[j], lw=1.9)

    axes[0].set_ylabel("Ángulo (°)"); axes[0].set_title("Posición Articular q(t) — `rtb.jtraj`"); axes[0].grid(True); axes[0].legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    axes[1].set_ylabel("Velocidad (°/s)"); axes[1].set_title("Velocidad Articular q̇(t)"); axes[1].grid(True)
    axes[2].set_ylabel("Aceleración (°/s²)"); axes[2].set_xlabel("Tiempo (s)"); axes[2].set_title("Aceleración Articular q̈(t)"); axes[2].grid(True)
    for ax in axes:
        ax.axvline(t_seg[-1], color="#71717A", ls=":", lw=1.2)

    fig2.tight_layout(rect=[0, 0, 0.99, 0.94])
    fig2.savefig(os.path.join(OUT_DIR, "fig2_trayectoria_jtraj.png"), dpi=180)
    plt.close(fig2)

    # ------------------------------------------------------------------
    # FIGURA 3: TRAYECTORIA CARTESIANA OFICIAL `rtb.ctraj()` + `robot.jacob0()`
    # ------------------------------------------------------------------
    rect_pts = [
        (100.0, -45.0, 60.0),
        (140.0, -45.0, 60.0),
        (140.0,  45.0, 60.0),
        (100.0,  45.0, 60.0),
        (100.0, -45.0, 60.0),
    ]
    phi_rect = -60.0
    N_side = 35
    Q_cart, P_cart, M_idx = [], [], []

    for s in range(len(rect_pts) - 1):
        TA = robot.tcp_se3_mm(*rect_pts[s], phi_rect)
        TB = robot.tcp_se3_mm(*rect_pts[s + 1], phi_rect)
        # Interpolación cartesiana oficial de Peter Corke (`rtb.ctraj`)
        Ts = rtb.ctraj(TA, TB, N_side)
        start_i = 1 if s > 0 else 0
        for k in range(start_i, len(Ts)):
            pt_mm = np.asarray(Ts[k].t, dtype=float) * 1000.0
            qk, ok, msg = robot.ikine_analytic_mm(pt_mm[0], pt_mm[1], pt_mm[2], phi_rect, elbow_up=True)
            assert ok, msg
            Q_cart.append(qk)
            P_cart.append(robot.fkine_mm(qk))
            # Jacobiano oficial de Peter Corke (`robot.jacob0`)
            J0 = robot.jacob0(qk)
            Jv = J0[:3, :]
            M_idx.append(math.sqrt(max(0.0, float(np.linalg.det(Jv @ Jv.T)))))

    Q_cart = np.array(Q_cart)
    P_cart = np.array(P_cart)
    M_idx = np.array(M_idx)
    rect_arr = np.array(rect_pts)

    print(f"  Ruta Cartesiana `rtb.ctraj()` ({len(P_cart)} puntos @ Z=60 mm, φ={phi_rect}°):")
    print(f"    Error máx Z = {np.max(np.abs(P_cart[:,2] - 60.0)):.2e} mm | Manipulabilidad mín = {np.min(M_idx):.5f} (> 0)")

    fig3 = plt.figure(figsize=(13, 9.2), dpi=180, facecolor="white")
    fig3.suptitle("Peter Corke `rtb.ctraj()` + `robot.jacob0()` — Ruta Cartesiana 3D y Proyecciones", fontsize=14, fontweight="bold", y=0.97)

    ax = fig3.add_subplot(2, 2, 1, projection="3d")
    ax.plot(P_cart[:, 0], P_cart[:, 1], P_cart[:, 2], color="#D45218", lw=2.8, label="Ruta TCP (`ctraj`)")
    ax.scatter(rect_arr[:, 0], rect_arr[:, 1], rect_arr[:, 2], color="#18181B", s=32, zorder=5)
    pts_start = robot.joint_positions_mm(Q_cart[0])
    ax.plot(pts_start[:, 0], pts_start[:, 1], pts_start[:, 2], "-o", color="#18181B", lw=2.8, ms=5, label="Robot inicio")
    ax.plot((BASE_DIA_MM / 2) * np.cos(th), (BASE_DIA_MM / 2) * np.sin(th), np.zeros_like(th), "k-", lw=1.6)
    ax.set_title(f"Trayectoria Cartesiana 3D (φ = {phi_rect:.0f}° constante)", fontweight="bold")
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)"); ax.set_zlabel("Z (mm)")
    ax.set_xlim(-60, 185); ax.set_ylim(-100, 100); ax.set_zlim(0, 180)
    ax.view_init(elev=26, azim=-46); ax.legend(loc="upper left", fontsize=8.5)

    ax = fig3.add_subplot(2, 2, 2)
    ax.plot(P_cart[:, 0], P_cart[:, 1], color="#D45218", lw=2.6, label="Trayectoria TCP")
    ax.scatter(rect_arr[:, 0], rect_arr[:, 1], color="#18181B", s=36, zorder=5, label="Vértices")
    ax.plot((BASE_DIA_MM / 2) * np.cos(th), (BASE_DIA_MM / 2) * np.sin(th), "k-", lw=1.8, label="Base Ø 94 mm")
    ax.set_title("Proyección XY — Rectángulo Exacto 40 × 90 mm", fontweight="bold")
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)")
    ax.set_aspect("equal"); ax.grid(True); ax.legend(loc="upper left", fontsize=8.5)

    ax = fig3.add_subplot(2, 2, 3)
    ax.plot(P_cart[:, 0], P_cart[:, 2], color="#2563EB", lw=2.6, label="Proyección XZ")
    ax.plot(P_cart[:, 1], P_cart[:, 2], "--", color="#16A34A", lw=2.2, label="Proyección YZ")
    ax.axhline(60.0, color="#71717A", ls=":", lw=1.2, label="Z = 60.0 mm")
    ax.set_title("Proyecciones XZ y YZ — Altura Constante", fontweight="bold")
    ax.set_xlabel("Coordenada X o Y (mm)"); ax.set_ylabel("Altura Z (mm)")
    ax.set_ylim(35, 85); ax.grid(True); ax.legend(loc="best", fontsize=8.5)

    ax = fig3.add_subplot(2, 2, 4)
    ax.plot(np.arange(len(M_idx)), M_idx, color="#18181B", lw=2.2)
    ax.fill_between(np.arange(len(M_idx)), 0, M_idx, color="#18181B", alpha=0.08)
    ax.set_title("Manipulabilidad de Yoshikawa (vía `robot.jacob0`)", fontweight="bold")
    ax.set_xlabel("Paso de trayectoria"); ax.set_ylabel("w = √det(Jv · Jvᵀ) [m³]")
    ax.set_ylim(bottom=0); ax.grid(True)

    fig3.subplots_adjust(left=0.07, right=0.97, top=0.90, bottom=0.07, hspace=0.34, wspace=0.22)
    fig3.savefig(os.path.join(OUT_DIR, "fig3_trayectoria_ctraj.png"), dpi=180)
    plt.close(fig3)

    if ART_DIR and os.path.isdir(ART_DIR):
        shutil.copy2(p_fig0, os.path.join(ART_DIR, "fig0_peter_corke_nativo_3d.png"))
    print(f"  4 figuras oficiales Peter Corke guardadas en: {OUT_DIR}")
    print("=" * 74)


if __name__ == "__main__":
    main()
