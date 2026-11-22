"""
Generador de Esquema de Cableado Eléctrico — Mini-Pro 4-DOF (`B2 Stealth`)
Produce una lámina técnica limpia y sin superposiciones en:
  `electronics/esquema_cableado_b2_stealth.png`
"""

import os
import shutil
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
ART_DIR = os.environ.get("ARTIFACT_DIR", "")


def draw_box(ax, x, y, w, h, title, subtitle="", face="#FFFFFF", edge="#18181B", dark=False, title_col=None, lw=2.0):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.35,rounding_size=1.4",
        facecolor=face, edgecolor=edge, linewidth=lw, zorder=3,
    )
    ax.add_patch(box)
    t_col = title_col if title_col else ("#FFFFFF" if dark else "#18181B")
    s_col = "#D4D4D8" if dark else "#3F3F46"
    ax.text(x + w / 2, y + h - 2.0, title, ha="center", va="top", fontsize=10.5, fontweight="bold", color=t_col, zorder=5)
    if subtitle:
        ax.text(x + w / 2, y + h - 5.2, subtitle, ha="center", va="top", fontsize=8.0, color=s_col, linespacing=1.35, zorder=5)


def draw_pin(ax, x, y, label, align="left", col="#18181B", dark_bg=False):
    ax.add_patch(Circle((x, y), 0.72, facecolor="#FFFFFF", edgecolor=col, lw=1.6, zorder=6))
    dx = 1.6 if align == "left" else -1.6
    ha = "left" if align == "left" else "right"
    txt_col = "#F4F4F5" if dark_bg and col == "#18181B" else col
    ax.text(x + dx, y, label, ha=ha, va="center", fontsize=8.0, fontweight="bold", color=txt_col, zorder=6)


def wire(ax, pts, color, lw=2.5, ls="-", label=None, label_pos=None):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=color, linewidth=lw, linestyle=ls, solid_capstyle="round", solid_joinstyle="round", zorder=2)
    if label and label_pos:
        ax.text(label_pos[0], label_pos[1], label, fontsize=7.8, fontweight="bold", color=color,
                ha="center", va="center", bbox=dict(boxstyle="round,pad=0.22", fc="#FFFFFF", ec="none", alpha=0.92), zorder=7)


def main():
    fig, ax = plt.subplots(figsize=(16.5, 9.8), dpi=190, facecolor="#F7F7F5")
    ax.set_facecolor("#F7F7F5")
    ax.set_xlim(0, 166)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Título
    ax.text(2.5, 96.5, "ESQUEMA ELÉCTRICO DEFINITIVO — MINI-PRO 4-DOF (B2 STEALTH · 100% UNIT ELECTRONICS)",
            fontsize=14.5, fontweight="bold", color="#18181B")
    ax.text(2.5, 92.8, "Alimentación por 1 solo cable USB-C (UGREEN 50W → AR5515 fijado en 5V) + Botón ON/OFF KCD11-2P + Protección USB con diodo 1N5819",
            fontsize=9.5, color="#52525B")

    # Zona punteada de la base Ø 94 mm
    base_zone = FancyBboxPatch((27.5, 11), 94.5, 78, boxstyle="round,pad=0.4,rounding_size=2.0",
                               facecolor="#FFFFFF", edgecolor="#A1A1AA", linewidth=1.6, linestyle="--", zorder=1)
    ax.add_patch(base_zone)
    ax.text(29.5, 86.8, "INTERIOR DE LA BASE CILÍNDRICA (Ø 94 mm)  ·  PANEL TRASERO A LA IZQUIERDA",
            fontsize=8.6, fontweight="bold", color="#71717A")

    # 1. Cargador UGREEN 50W (Externo)
    draw_box(ax, 2.5, 62, 20.5, 20, "UGREEN 50W", "Cargador USB-C PD\n(abajo del escritorio)\nPerfil base: 5V / 3A\n1 cable USB-C negro", face="#18181B", edge="#18181B", dark=True)

    # 2. Módulo USB-C PD AR5515
    draw_box(ax, 30.5, 63, 25.5, 19, "USB-C PD AR5515", "SKU: AR5515 ($32)\n28×10×12 mm\n¡DIP FIJADO EN 5V!", face="#ECFDF5", edge="#059669", title_col="#065F46")
    draw_pin(ax, 56.0, 72.5, "+5V", align="right", col="#DC2626")
    draw_pin(ax, 56.0, 66.5, "GND", align="right", col="#18181B")

    # Alerta multímetro
    warn = FancyBboxPatch((30.5, 53.0), 25.5, 7.2, boxstyle="round,pad=0.25,rounding_size=0.8",
                          facecolor="#FEF3C7", edgecolor="#D97706", linewidth=1.5, zorder=4)
    ax.add_patch(warn)
    ax.text(43.25, 56.6, "MEDIR 5.0V CON MULTÍMETRO\nantes de conectar PCA9685 / XIAO",
            ha="center", va="center", fontsize=7.6, fontweight="bold", color="#92400E", zorder=5)

    # 3. Interruptor ON/OFF KCD11-2P
    draw_box(ax, 63.0, 67, 19.0, 14, "KCD11-2P", "ON / OFF Negro\nSKU: AR0243 ($5)", face="#27272A", edge="#18181B", dark=True)
    draw_pin(ax, 63.0, 72.5, "IN", align="left", col="#F87171", dark_bg=True)
    draw_pin(ax, 82.0, 72.5, "OUT", align="right", col="#F87171", dark_bg=True)

    # 4. Capacitor Electrolítico 1000 µF 16V
    draw_box(ax, 63.5, 49.5, 18.0, 12.5, "Cap 1000 µF", "16V · AR1127 ($3)\nAbsorbe picos", face="#EFF6FF", edge="#2563EB", title_col="#1D4ED8")
    ax.text(72.5, 62.9, "+ (pata larga)", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#DC2626", zorder=6)
    ax.text(72.5, 48.6, "− (franja blanca)", ha="center", va="top", fontsize=7.5, fontweight="bold", color="#18181B", zorder=6)
    ax.add_patch(Circle((72.5, 62.0), 0.72, facecolor="#FFFFFF", edgecolor="#DC2626", lw=1.6, zorder=6))
    ax.add_patch(Circle((72.5, 49.5), 0.72, facecolor="#FFFFFF", edgecolor="#18181B", lw=1.6, zorder=6))

    # 5. Diodo Schottky 1N5819
    draw_box(ax, 62.0, 31.0, 21.0, 13.0, "Diodo 1N5819", "Schottky · AR0195 ($2)", face="#FEF2F2", edge="#DC2626", title_col="#991B1B")
    # Símbolo claro apuntando a la IZQUIERDA (hacia XIAO 5V)
    tri = Polygon([(74.8, 33.4), (74.8, 37.2), (70.4, 35.3)], closed=True, facecolor="#DC2626", edgecolor="#991B1B", zorder=6)
    ax.add_patch(tri)
    ax.plot([70.0, 70.0], [33.1, 37.5], color="#18181B", lw=3.0, zorder=6)
    ax.text(75.8, 35.3, "Ánodo (+)", fontsize=7.2, va="center", ha="left", color="#991B1B", fontweight="bold", zorder=6)
    ax.text(69.1, 35.3, "Banda (−)", fontsize=7.2, va="center", ha="right", color="#18181B", fontweight="bold", zorder=6)

    # 6. XIAO ESP32-S3
    draw_box(ax, 30.5, 13.5, 25.5, 34.0, "XIAO ESP32-S3", "(ó XIAO ESP32-C3)\n21.0 × 17.8 mm\nWi-Fi + USB-C", face="#18181B", edge="#18181B", dark=True)
    draw_pin(ax, 56.0, 35.3, "5V (VBUS)", align="right", col="#F87171", dark_bg=True)
    draw_pin(ax, 56.0, 29.0, "3V3", align="right", col="#FB923C", dark_bg=True)
    draw_pin(ax, 56.0, 24.0, "D4 (SDA)", align="right", col="#60A5FA", dark_bg=True)
    draw_pin(ax, 56.0, 19.0, "D5 (SCL)", align="right", col="#C084FC", dark_bg=True)
    draw_pin(ax, 56.0, 15.0, "GND", align="right", col="#E4E4E7", dark_bg=True)

    # PC / Python opcional
    draw_box(ax, 2.5, 18.0, 20.5, 19.5, "PC · Python", "Peter Corke RTB\nUSB-C (flasheo)\nó Wi-Fi UDP (0 cables)", face="#F4F4F5", edge="#52525B", title_col="#18181B")

    # 7. PCA9685
    draw_box(ax, 91.5, 13.5, 28.0, 69.5, "PCA9685", "16-ch PWM 12-bit I2C\nSKU: AR0389 ($99)\nDir: 0x40 · 50 Hz", face="#EFF6FF", edge="#1D4ED8", title_col="#1E3A8A")
    draw_pin(ax, 91.5, 72.5, "V+ (Bornera 5V)", align="left", col="#DC2626")
    draw_pin(ax, 91.5, 66.5, "GND (Bornera)", align="left", col="#18181B")
    draw_pin(ax, 91.5, 29.0, "VCC (3.3V!)", align="left", col="#EA580C")
    draw_pin(ax, 91.5, 24.0, "SDA", align="left", col="#2563EB")
    draw_pin(ax, 91.5, 19.0, "SCL", align="left", col="#7C3AED")
    draw_pin(ax, 91.5, 15.0, "GND (Lógica)", align="left", col="#18181B")

    # Servos CH0..CH4
    ch_y = [67, 55, 43, 31, 19]
    ch_names = [
        ("CH0", "J1 · Base Yaw", "MG90S (AR1240)"),
        ("CH1", "J2 · Hombro Pitch", "MG90S (AR1240)"),
        ("CH2", "J3 · Codo Pitch", "MG90S (AR1240)"),
        ("CH3", "J4 · Muñeca 4.º Eje", "MG90S + Dupont 20cm"),
        ("CH4", "Pinza 2 Dedos", "SG90 + Dupont 20cm"),
    ]
    for cy, (ch, name, model) in zip(ch_y, ch_names):
        draw_pin(ax, 119.5, cy, ch, align="right", col="#1E3A8A")
        draw_box(ax, 132.5, cy - 4.4, 30.5, 8.8, name, model, face="#FFFFFF", edge="#18181B", lw=1.6)
        wire(ax, [(119.5, cy + 1.2), (132.5, cy + 1.2)], "#EA580C", lw=1.9)
        wire(ax, [(119.5, cy), (132.5, cy)], "#DC2626", lw=1.9)
        wire(ax, [(119.5, cy - 1.2), (132.5, cy - 1.2)], "#78350F", lw=1.9)

    ax.text(147.8, 79.5, "Orden en pines PCA9685:\n• Arriba (PWM): Naranja / Amarillo\n• Centro (V+): Rojo\n• Abajo (GND): Café / Negro",
            ha="center", va="center", fontsize=8.0, color="#18181B",
            bbox=dict(boxstyle="round,pad=0.5", fc="#FFF7ED", ec="#EA580C", lw=1.4), zorder=6)

    # ==================================================================
    # CABLES PRINCIPALES (cero cruces confusos)
    # ==================================================================
    wire(ax, [(23.0, 72.0), (30.5, 72.0)], "#18181B", lw=4.0, label="USB-C", label_pos=(26.7, 75.5))
    wire(ax, [(23.0, 27.5), (30.5, 27.5)], "#2563EB", lw=2.4, ls="--", label="USB-C\n(opcional)", label_pos=(26.7, 32.5))

    # +5V: AR5515 -> KCD11 -> PCA9685 V+
    wire(ax, [(56.0, 72.5), (63.0, 72.5)], "#DC2626", lw=3.2)
    wire(ax, [(82.0, 72.5), (91.5, 72.5)], "#DC2626", lw=3.2, label="+5V (3A)", label_pos=(86.8, 75.5))

    # Derivación +5V conmutado -> Cap (+) y Diodo 1N5819 Ánodo
    wire(ax, [(85.5, 72.5), (85.5, 65.0), (72.5, 65.0), (72.5, 62.0)], "#DC2626", lw=2.5)
    ax.add_patch(Circle((85.5, 72.5), 0.72, color="#DC2626", zorder=7))
    wire(ax, [(85.5, 65.0), (85.5, 35.3), (83.0, 35.3)], "#DC2626", lw=2.3)
    ax.add_patch(Circle((85.5, 65.0), 0.65, color="#DC2626", zorder=7))
    wire(ax, [(62.0, 35.3), (56.0, 35.3)], "#DC2626", lw=2.5)

    # Bus GND común limpio
    wire(ax, [(56.0, 66.5), (59.5, 66.5), (59.5, 46.5), (88.5, 46.5), (88.5, 66.5), (91.5, 66.5)], "#18181B", lw=3.0)
    wire(ax, [(72.5, 49.5), (72.5, 46.5)], "#18181B", lw=2.4)
    ax.add_patch(Circle((72.5, 46.5), 0.65, color="#18181B", zorder=7))
    wire(ax, [(88.5, 46.5), (88.5, 15.0), (91.5, 15.0)], "#18181B", lw=2.4)
    ax.add_patch(Circle((88.5, 46.5), 0.65, color="#18181B", zorder=7))
    wire(ax, [(56.0, 15.0), (88.5, 15.0)], "#18181B", lw=2.4, label="GND común", label_pos=(73.5, 13.0))
    ax.add_patch(Circle((88.5, 15.0), 0.65, color="#18181B", zorder=7))

    # Bus Lógico I2C 3.3V (XIAO <-> PCA9685)
    wire(ax, [(56.0, 29.0), (91.5, 29.0)], "#EA580C", lw=2.2, label="3.3V Lógica (NO 5V)", label_pos=(73.5, 27.0))
    wire(ax, [(56.0, 24.0), (91.5, 24.0)], "#2563EB", lw=2.2, label="SDA (I2C)", label_pos=(73.5, 22.1))
    wire(ax, [(56.0, 19.0), (91.5, 19.0)], "#7C3AED", lw=2.2, label="SCL (I2C)", label_pos=(73.5, 17.2))

    # Pie de seguridad en 2 líneas limpias dentro del margen
    ax.text(2.5, 5.2,
            "REGLAS DE SEGURIDAD:  (1) Ajusta el DIP del AR5515 en 5V y mídelo con multímetro ANTES de conectar PCA9685 o XIAO.   "
            "(2) Conecta 3V3 de la XIAO al pin VCC del PCA9685 (lógica segura 3.3V).\n"
            "(3) La banda plateada/blanca del diodo 1N5819 SIEMPRE apunta hacia el pin 5V de la XIAO (así puedes conectar USB-C a tu PC y UGREEN 50W al mismo tiempo sin riesgo).",
            fontsize=8.3, color="#27272A", fontweight="bold", linespacing=1.45)

    out_elec = os.path.join(HERE, "esquema_cableado_b2_stealth.png")
    plt.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.01)
    fig.savefig(out_elec, dpi=190)
    plt.close(fig)
    if ART_DIR and os.path.isdir(ART_DIR):
        shutil.copy2(out_elec, os.path.join(ART_DIR, "esquema_cableado_b2_stealth.png"))
    print("Saved polished schematic:", out_elec)


if __name__ == "__main__":
    main()
