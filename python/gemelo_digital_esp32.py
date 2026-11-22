"""
Gemelo Digital Interactivo en Vivo — Peter Corke Python -> XIAO ESP32 (USB Serial o Wi-Fi UDP)
==============================================================================================
Ejecútalo en cualquier momento para controlar el modelo 3D de Peter Corke con sliders
interactivos (4 DOF + pinza) y sincronizarlo en vivo con tu XIAO ESP32-S3/C3:

    python python/gemelo_digital_esp32.py                      # Modo simulación (DRY_RUN)
    python python/gemelo_digital_esp32.py --wifi 192.168.4.1   # Por Wi-Fi UDP (¡1 solo cable!)
    python python/gemelo_digital_esp32.py --port COM5          # Por USB Serial (115200 baud)

Protocolo ASCII unificado (Serial 115200 / UDP puerto 4210):
    G <q1_deg> <q2_deg> <q3_deg> <q4_deg> <grip_mm>\n
    RELAX\n
    STATUS\n
"""

import argparse
import socket
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import roboticstoolbox as rtb

from robot_minipro_rtb import MiniPro4DOF, QLIM_DEG, Q_HERO_RAD, Q_HOME_RAD, BASE_DIA_MM

try:
    import serial
except ImportError:
    serial = None


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
            print("[DRY_RUN] Modo simulación (usa --wifi <IP> o --port COMx para hardware real).")

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


def main():
    parser = argparse.ArgumentParser(description="Gemelo Digital Interactivo Mini-Pro 4-DOF B2 Stealth")
    parser.add_argument("--port", type=str, default="", help="Puerto COM USB Serial (ej. COM5)")
    parser.add_argument("--baud", type=int, default=115200, help="Baudrate serial (default 115200)")
    parser.add_argument("--wifi", type=str, default="", help="IP Wi-Fi de la XIAO ESP32 (ej. 192.168.4.1)")
    parser.add_argument("--udp-port", type=int, default=4210, help="Puerto UDP del firmware (default 4210)")
    args = parser.parse_args()

    robot = MiniPro4DOF()
    link = ArmLink(port=args.port, baud=args.baud, wifi_ip=args.wifi, udp_port=args.udp_port)

    q_hero_deg = np.rad2deg(Q_HERO_RAD)
    q_home_deg = np.rad2deg(Q_HOME_RAD)
    grip_init = 16.0

    fig = plt.figure(figsize=(10.8, 7.8), facecolor="#F6F6F4")
    fig.canvas.manager.set_window_title("Gemelo Digital — Mini-Pro 4-DOF B2 Stealth (Peter Corke)")
    ax = fig.add_axes([0.05, 0.30, 0.90, 0.64], projection="3d")
    ax.set_facecolor("#F6F6F4")

    th = np.linspace(0, 2 * np.pi, 80)
    base_x = (BASE_DIA_MM / 2.0) * np.cos(th)
    base_y = (BASE_DIA_MM / 2.0) * np.sin(th)
    base_z = np.zeros_like(th)

    ax.plot(base_x, base_y, base_z, color="#18181B", lw=2.2)
    pts0 = robot.joint_positions_mm(Q_HERO_RAD)
    (line_arm,) = ax.plot(pts0[:, 0], pts0[:, 1], pts0[:, 2], "-o", color="#18181B", lw=5.0, ms=8, mfc="#FFFFFF", mec="#18181B", mew=2.0)
    (dot_tcp,) = ax.plot([pts0[-1, 0]], [pts0[-1, 1]], [pts0[-1, 2]], "o", color="#D45218", ms=9)
    # Proyecciones en vivo sobre los planos del cubo
    (proj_xy,) = ax.plot([pts0[-1, 0]], [pts0[-1, 1]], [0], "o", color="#2563EB", ms=5, alpha=0.7)
    (proj_line,) = ax.plot([pts0[-1, 0], pts0[-1, 0]], [pts0[-1, 1], pts0[-1, 1]], [0, pts0[-1, 2]], ":", color="#2563EB", lw=1.2)

    ax.set_xlim(-90, 220); ax.set_ylim(-180, 180); ax.set_zlim(0, 290)
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)"); ax.set_zlabel("Z (mm)")
    ax.view_init(elev=22, azim=-46)
    status_txt = fig.text(0.5, 0.955, "", ha="center", fontsize=11, fontweight="bold", color="#18181B")

    # Sliders minimalistas (sincronizados con cad/params.py y firmware/config.h)
    sliders = []
    s_defs = [
        ("J1 Base (°)",   QLIM_DEG[0, 0], QLIM_DEG[0, 1], q_hero_deg[0]),
        ("J2 Hombro (°)", QLIM_DEG[1, 0], QLIM_DEG[1, 1], q_hero_deg[1]),
        ("J3 Codo (°)",   QLIM_DEG[2, 0], QLIM_DEG[2, 1], q_hero_deg[2]),
        ("J4 Muñeca (°)", QLIM_DEG[3, 0], QLIM_DEG[3, 1], q_hero_deg[3]),
        ("Pinza (mm)",    0.0,            30.0,           grip_init),
    ]
    for idx, (lbl, vmin, vmax, v0) in enumerate(s_defs):
        ax_s = fig.add_axes([0.15, 0.228 - idx * 0.043, 0.61, 0.025], facecolor="#E4E4E7")
        s = Slider(ax_s, lbl, vmin, vmax, valinit=v0, color="#18181B")
        sliders.append(s)

    def send_and_draw(q_deg, grip_mm, transmit=True, throttle_s=0.0):
        q_rad = np.deg2rad(q_deg)
        pts = robot.joint_positions_mm(q_rad)
        tcp = pts[-1]
        phi = q_deg[1] + q_deg[2] + q_deg[3]
        line_arm.set_data_3d(pts[:, 0], pts[:, 1], pts[:, 2])
        dot_tcp.set_data_3d([tcp[0]], [tcp[1]], [tcp[2]])
        proj_xy.set_data_3d([tcp[0]], [tcp[1]], [0.0])
        proj_line.set_data_3d([tcp[0], tcp[0]], [tcp[1], tcp[1]], [0.0, tcp[2]])
        status_txt.set_text(
            f"[{link.mode_label}]  TCP = ({tcp[0]:.1f}, {tcp[1]:.1f}, {tcp[2]:.1f}) mm  |  φ = {phi:.1f}°  |  Pinza = {grip_mm:.0f} mm"
        )
        if transmit:
            link.send_pose(q_deg, grip_mm, throttle_s=throttle_s)
        fig.canvas.draw_idle()

    def set_sliders_silent(q_deg, grip_mm):
        for i in range(4):
            sliders[i].eventson = False
            sliders[i].set_val(q_deg[i])
            sliders[i].eventson = True
        sliders[4].eventson = False
        sliders[4].set_val(grip_mm)
        sliders[4].eventson = True

    def on_slider(_):
        q_deg = [sliders[i].val for i in range(4)]
        send_and_draw(q_deg, sliders[4].val, transmit=True, throttle_s=0.025)

    for s in sliders:
        s.on_changed(on_slider)

    # Panel derecho de botones de control rápido
    ax_btn_hero  = fig.add_axes([0.80, 0.210, 0.16, 0.045])
    ax_btn_home  = fig.add_axes([0.80, 0.155, 0.16, 0.045])
    ax_btn_demo  = fig.add_axes([0.80, 0.100, 0.16, 0.045])
    ax_btn_relax = fig.add_axes([0.80, 0.045, 0.16, 0.045])

    btn_hero = Button(ax_btn_hero, "Pose Héroe", color="#18181B", hovercolor="#3F3F46")
    btn_hero.label.set_color("white")

    btn_home = Button(ax_btn_home, "Home Vertical", color="#3F3F46", hovercolor="#52525B")
    btn_home.label.set_color("white")

    btn_demo = Button(ax_btn_demo, "Demo jtraj", color="#D45218", hovercolor="#EA580C")
    btn_demo.label.set_color("white")

    btn_relax = Button(ax_btn_relax, "Relajar Servos", color="#E4E4E7", hovercolor="#D4D4D8")
    btn_relax.label.set_color("#18181B")

    def on_hero(_):
        set_sliders_silent(q_hero_deg, 16.0)
        send_and_draw(q_hero_deg, 16.0, transmit=True)

    def on_home(_):
        set_sliders_silent(q_home_deg, 18.0)
        send_and_draw(q_home_deg, 18.0, transmit=True)

    def on_relax(_):
        link.send_raw("RELAX")
        status_txt.set_text(f"[{link.mode_label}]  SERVOS RELAJADOS (SIN TORQUE)")
        fig.canvas.draw_idle()

    def on_demo(_):
        # Secuencia Pick-and-Place con aproximación vertical (sincronizada con el firmware)
        wps = [
            ((135, -65, 105, 0), 24.0),
            ((135, -65,  68, 0), 24.0),
            ((135, -65,  68, 0),  6.0),
            ((135, -65, 105, 0),  6.0),
            ((145,   0, 130, 0),  6.0),
            ((135,  65, 105, 0),  6.0),
            ((135,  65,  68, 0),  6.0),
            ((135,  65,  68, 0), 24.0),
            ((135,  65, 105, 0), 24.0),
            ((145.52, 0, 125.17, 0), 16.0),
        ]
        qs = [(robot.ikine_analytic_mm(*w)[0], g) for w, g in wps]
        for k in range(len(qs) - 1):
            q0, g0 = qs[k]
            q1, g1 = qs[k + 1]
            steps = 12 if np.allclose(q0, q1) else 22
            tr = rtb.jtraj(q0, q1, steps)
            gs = np.linspace(g0, g1, steps)
            for qi, gi in zip(tr.q, gs):
                qd = np.rad2deg(qi)
                set_sliders_silent(qd, gi)
                send_and_draw(qd, float(gi), transmit=True)
                plt.pause(0.032)

    btn_hero.on_clicked(on_hero)
    btn_home.on_clicked(on_home)
    btn_demo.on_clicked(on_demo)
    btn_relax.on_clicked(on_relax)

    # Arranque seguro: dibuja Pose Héroe sin disparar movimiento automático si está en LIVE
    send_and_draw(q_hero_deg, grip_init, transmit=False)
    try:
        plt.show()
    finally:
        link.close()


if __name__ == "__main__":
    main()
