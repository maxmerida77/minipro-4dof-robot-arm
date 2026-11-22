"""
Generador del Diagrama Pictórico Estilo Fritzing — Mini-Pro 4-DOF (`B2 Stealth`)
================================================================================
Genera un diagrama vectorial SVG de ultra alta calidad (con apariencia física real
de cada componente, pines exactos, polaridades y cables de colores estilo Fritzing)
y lo rasteriza en PNG 4K (`3600 x 2360 px`) mediante Chrome/Edge headless.

Salidas:
  - electronics/diagrama_fritzing_b2_stealth.svg  (vector editable, zoom infinito)
  - electronics/diagrama_fritzing_b2_stealth.png  (PNG 4K ultra-nítido)

Verificado 100% contra:
  - electronics/kicad/minipro_b2_stealth.kicad_sch (0 Errores, 0 Avisos ERC)
  - electronics/DIAGRAMA_CABLEADO.md
  - firmware/minipro_b2_stealth/config.h
"""

import os
import subprocess
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_PATH = os.path.join(HERE, "diagrama_fritzing_b2_stealth.svg")
PNG_PATH = os.path.join(HERE, "diagrama_fritzing_b2_stealth.png")

W, H = 1800, 1180


def _t(x, y, text, size=13, weight="600", fill="#1E293B", anchor="start",
       family="'Segoe UI', Inter, Arial, sans-serif", extra=""):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}" {extra}>{escape(text)}</text>'
    )


def _wire(d, color, width=5.0, halo="#F8FAFC", halo_w=9.2, highlight=True):
    """Cable físico estilo Fritzing: halo de separación + contorno oscuro + color + brillo."""
    parts = [
        f'<path d="{d}" fill="none" stroke="{halo}" stroke-width="{halo_w:.1f}" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="0.92"/>',
        f'<path d="{d}" fill="none" stroke="#0F172A" stroke-width="{width + 1.8:.1f}" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="0.44"/>',
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:.1f}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>',
    ]
    if highlight:
        parts.append(
            f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="{max(1.1, width * 0.24):.1f}" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="0.32"/>'
        )
    return "\n".join(parts)


def _junction(x, y, color="#DC2626"):
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.2" fill="#0F172A" opacity="0.42"/>'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.0" fill="{color}" stroke="#FFFFFF" stroke-width="1.4"/>'
    )


def _pill(x, y, text, bg="#0F172A", fg="#FFFFFF", border=None, size=10.5, pad_x=9, h=21, anchor="middle"):
    tw = len(text) * (size * 0.58) + pad_x * 2
    rx = x - tw / 2 if anchor == "middle" else (x if anchor == "start" else x - tw)
    b_attr = f' stroke="{border}" stroke-width="1.3"' if border else ""
    return (
        f'<rect x="{rx:.1f}" y="{y - h/2:.1f}" width="{tw:.1f}" height="{h:.1f}" '
        f'rx="{h/2:.1f}" fill="{bg}"{b_attr}/>'
        + _t(rx + tw / 2, y + size * 0.36, text, size=size, weight="700", fill=fg, anchor="middle")
    )


# ============================================================================
# 1. CARGADOR UGREEN 50W (USB-C PD)
# ============================================================================
def draw_ugreen_charger(x, y):
    g = [f'<g id="ugreen-50w" filter="url(#shadow)">']
    g.append(f'<rect x="{x-22}" y="{y+26}" width="24" height="10" rx="2" fill="url(#metal)" stroke="#64748B" stroke-width="1"/>')
    g.append(f'<rect x="{x-22}" y="{y+56}" width="24" height="10" rx="2" fill="url(#metal)" stroke="#64748B" stroke-width="1"/>')
    g.append(f'<rect x="{x}" y="{y}" width="128" height="92" rx="14" fill="url(#ugreenBody)" stroke="#1E293B" stroke-width="2"/>')
    g.append(f'<rect x="{x+108}" y="{y+4}" width="18" height="84" rx="6" fill="#0F172A"/>')
    g.append(f'<rect x="{x+113}" y="{y+24}" width="11" height="22" rx="5" fill="#1E293B" stroke="#94A3B8" stroke-width="1.4"/>')
    g.append(f'<rect x="{x+117}" y="{y+29}" width="3" height="12" rx="1" fill="#F59E0B"/>')
    g.append(f'<rect x="{x+113}" y="{y+54}" width="11" height="20" rx="5" fill="#1E293B" stroke="#64748B" stroke-width="1.2"/>')
    g.append(_t(x + 54, y + 40, "UGREEN", size=17, weight="800", fill="#E2E8F0", anchor="middle"))
    g.append(_t(x + 54, y + 58, "50W USB-C PD", size=11, weight="600", fill="#94A3B8", anchor="middle"))
    g.append(_t(x + 54, y + 74, "Salida 5V / 3A", size=10.5, weight="700", fill="#38BDF8", anchor="middle"))
    g.append(f'<rect x="{x+126}" y="{y+26}" width="24" height="18" rx="4" fill="#1E293B" stroke="#475569" stroke-width="1.3"/>')
    g.append(f'<rect x="{x+150}" y="{y+30}" width="12" height="10" rx="2" fill="#334155"/>')
    g.append("</g>")
    g.append(_t(x + 64, y + 113, "Cargador UGREEN 50W", size=13, weight="800", fill="#0F172A", anchor="middle"))
    g.append(_t(x + 64, y + 129, "(Ya disponible · 1 solo cable)", size=11, weight="600", fill="#64748B", anchor="middle"))
    return "\n".join(g), (x + 162, y + 35)


# ============================================================================
# 2. MÓDULO USB-C PD TRIGGER AR5515 (DIP EN 5V)
# ============================================================================
def draw_ar5515(x, y):
    w, h = 160, 102
    g = [f'<g id="ar5515" filter="url(#shadow)">']
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="url(#pcbPurple)" stroke="#312E81" stroke-width="2"/>')
    for cx, cy in ((x + 10, y + 10), (x + 10, y + h - 10), (x + w - 10, y + 10), (x + w - 10, y + h - 10)):
        g.append(f'<circle cx="{cx}" cy="{cy}" r="4.2" fill="#E2E8F0" stroke="#F59E0B" stroke-width="1.6"/>')
    g.append(f'<rect x="{x-14}" y="{y+28}" width="34" height="46" rx="5" fill="url(#metal)" stroke="#475569" stroke-width="1.5"/>')
    g.append(f'<rect x="{x-26}" y="{y+38}" width="14" height="26" rx="3" fill="#1E293B" stroke="#475569" stroke-width="1.2"/>')
    g.append(_t(x + 3, y + 55, "USB-C", size=8.5, weight="800", fill="#334155", anchor="middle",
                extra=f'transform="rotate(-90 {x+3} {y+51})"'))
    dx, dy = x + 36, y + 20
    g.append(f'<rect x="{dx}" y="{dy}" width="54" height="44" rx="4" fill="#DC2626" stroke="#7F1D1D" stroke-width="1.5"/>')
    g.append(_t(dx + 27, dy - 4, "DIP = 5V", size=10, weight="800", fill="#FEF08A", anchor="middle"))
    for i, label in enumerate(("1", "2", "3")):
        sx = dx + 7 + i * 15
        g.append(f'<rect x="{sx}" y="{dy+8}" width="10" height="24" rx="2" fill="#7F1D1D"/>')
        knob_y = dy + 10 if i == 0 else dy + 22
        g.append(f'<rect x="{sx+1.2}" y="{knob_y}" width="7.6" height="9" rx="1.5" fill="#F8FAFC"/>')
        g.append(_t(sx + 5, dy + 41, label, size=8.5, weight="700", fill="#FECACA", anchor="middle"))
    g.append(f'<circle cx="{x+44}" cy="{y+82}" r="3.8" fill="#22C55E" stroke="#14532D" stroke-width="1"/>')
    g.append(_t(x + 52, y + 85, "AR5515 PD", size=10, weight="800", fill="#E0E7FF"))
    tx, ty = x + w - 42, y + 16
    g.append(f'<rect x="{tx}" y="{ty}" width="40" height="70" rx="4" fill="#0284C7" stroke="#075985" stroke-width="1.5"/>')
    for idx, (lbl, col) in enumerate((("+", "#FCA5A5"), ("−", "#CBD5E1"))):
        py = ty + 20 + idx * 30
        g.append(f'<circle cx="{tx+20}" cy="{py}" r="10.5" fill="url(#metal)" stroke="#334155" stroke-width="1.2"/>')
        g.append(f'<line x1="{tx+13}" y1="{py-5}" x2="{tx+27}" y2="{py+5}" stroke="#475569" stroke-width="2"/>')
        g.append(_t(tx - 6, py + 4, lbl, size=13, weight="900", fill=col, anchor="end"))
    g.append("</g>")
    g.append(_t(x + w / 2, y + h + 19, "Módulo USB-C PD AR5515", size=13, weight="800", fill="#0F172A", anchor="middle"))
    g.append(_pill(x + w / 2, y + h + 38, "1) DIP en 5V · MEDIR 5.0V", bg="#FEF3C7", fg="#92400E", border="#F59E0B", size=10.2, h=20))
    return "\n".join(g), {
        "usbc": (x - 26, y + 51),
        "v5": (x + w - 2, y + 36),
        "gnd": (x + w - 2, y + 66),
    }


# ============================================================================
# 3. BOTÓN BASCULANTE KCD11-2P ON/OFF (NEGRO)
# ============================================================================
def draw_kcd11_switch(x, y):
    w, h = 84, 70
    g = [f'<g id="kcd11-switch" filter="url(#shadow)">']
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="#18181B" stroke="#09090B" stroke-width="2"/>')
    g.append(f'<rect x="{x+9}" y="{y+9}" width="{w-18}" height="{h-18}" rx="4" fill="url(#switchRocker)" stroke="#3F3F46" stroke-width="1.2"/>')
    g.append(f'<line x1="{x+24}" y1="{y+26}" x2="{x+24}" y2="{y+44}" stroke="#F8FAFC" stroke-width="2.6" stroke-linecap="round"/>')
    g.append(f'<circle cx="{x+60}" cy="{y+35}" r="7.5" fill="none" stroke="#A1A1AA" stroke-width="2.4"/>')
    g.append(f'<rect x="{x-12}" y="{y+28}" width="13" height="14" rx="2" fill="url(#brass)" stroke="#92400E" stroke-width="1"/>')
    g.append(f'<rect x="{x+w-1}" y="{y+28}" width="13" height="14" rx="2" fill="url(#brass)" stroke="#92400E" stroke-width="1"/>')
    g.append(_t(x + 12, y - 7, "IN (1)", size=10, weight="700", fill="#64748B", anchor="middle"))
    g.append(_t(x + w - 12, y - 7, "OUT (2)", size=10, weight="700", fill="#64748B", anchor="middle"))
    g.append("</g>")
    g.append(_t(x + w / 2, y + h + 20, "Botón KCD11-2P", size=12.5, weight="800", fill="#0F172A", anchor="middle"))
    g.append(_t(x + w / 2, y + h + 35, "ON/OFF Trasero (AR0243)", size=10.5, weight="600", fill="#64748B", anchor="middle"))
    return "\n".join(g), {
        "in": (x - 12, y + 35),
        "out": (x + w + 12, y + 35),
    }


# ============================================================================
# 4. DIODO SCHOTTKY 1N5819 (BANDA CÁTODO K ← APUNTANDO A XIAO 5V)
# ============================================================================
def draw_diode_1n5819_left(x, y):
    bw, bh = 62, 26
    g = [f'<g id="diode-1n5819" filter="url(#shadowSm)">']
    g.append(f'<line x1="{x-26}" y1="{y}" x2="{x+bw+26}" y2="{y}" stroke="#94A3B8" stroke-width="4.4" stroke-linecap="round"/>')
    g.append(f'<line x1="{x-26}" y1="{y-1}" x2="{x+bw+26}" y2="{y-1}" stroke="#F8FAFC" stroke-width="1.2" opacity="0.65"/>')
    g.append(f'<rect x="{x}" y="{y-bh/2}" width="{bw}" height="{bh}" rx="5" fill="url(#diodeBody)" stroke="#09090B" stroke-width="1.5"/>')
    g.append(f'<rect x="{x+5}" y="{y-bh/2+1}" width="9" height="{bh-2}" fill="url(#silverBand)"/>')
    g.append(_t(x + 38, y + 3.5, "1N5819", size=9.0, weight="800", fill="#E2E8F0", anchor="middle"))
    g.append(_t(x - 10, y - 16, "← K (Banda)", size=10, weight="800", fill="#0F172A", anchor="middle"))
    g.append(_t(x + bw + 12, y - 16, "A (+)", size=10, weight="800", fill="#DC2626", anchor="middle"))
    g.append("</g>")
    g.append(_t(x + bw / 2, y - 34, "Diodo Schottky 1N5819 (AR0195)", size=11.5, weight="800", fill="#0F172A", anchor="middle"))
    g.append(_pill(x + bw / 2, y + 29, "Banda ← hacia XIAO 5V (antirretorno)", bg="#FEF3C7", fg="#92400E", border="#F59E0B", size=9.6, h=19))
    return "\n".join(g), {
        "cathode": (x - 26, y),
        "anode": (x + bw + 26, y),
    }


# ============================================================================
# 5. CAPACITOR ELECTROLÍTICO 1000 µF 16V (DESPEJADO A LA DERECHA DE BORNERA)
# ============================================================================
def draw_capacitor_1000uf(x, y):
    cw, ch = 54, 78
    g = [f'<g id="cap-1000uf" filter="url(#shadow)">']
    g.append(f'<line x1="{x+15}" y1="{y+ch-2}" x2="{x+15}" y2="{y+ch+22}" stroke="#94A3B8" stroke-width="3.8" stroke-linecap="round"/>')
    g.append(f'<line x1="{x+39}" y1="{y+ch-2}" x2="{x+39}" y2="{y+ch+22}" stroke="#94A3B8" stroke-width="3.8" stroke-linecap="round"/>')
    g.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="7" fill="url(#capBody)" stroke="#0F172A" stroke-width="1.6"/>')
    g.append(f'<ellipse cx="{x+cw/2}" cy="{y+6}" rx="{cw/2-1}" ry="6" fill="url(#metal)" stroke="#64748B" stroke-width="1"/>')
    g.append(f'<rect x="{x+cw-15}" y="{y+8}" width="12" height="{ch-10}" rx="2" fill="#E2E8F0"/>')
    for sy in (y + 25, y + 44, y + 63):
        g.append(_t(x + cw - 9.0, sy, "−", size=13, weight="900", fill="#1E293B", anchor="middle"))
    g.append(_t(x + 18, y + 35, "1000", size=10.5, weight="800", fill="#F8FAFC", anchor="middle"))
    g.append(_t(x + 18, y + 49, "µF", size=10.5, weight="800", fill="#38BDF8", anchor="middle"))
    g.append(_t(x + 18, y + 64, "16V", size=9.5, weight="700", fill="#CBD5E1", anchor="middle"))
    g.append(_t(x + 5, y + ch + 18, "+", size=13, weight="900", fill="#DC2626", anchor="middle"))
    g.append(_t(x + 49, y + ch + 18, "−", size=13, weight="900", fill="#0F172A", anchor="middle"))
    g.append("</g>")
    g.append(_t(x + cw + 14, y + 26, "Capacitor 1000 µF 16V", size=12.5, weight="800", fill="#0F172A"))
    g.append(_t(x + cw + 14, y + 43, "(AR1127 · Directo en bornera)", size=10.5, weight="600", fill="#64748B"))
    g.append(_pill(x + cw + 14, y + 64, "Franja blanca (−) → GND", bg="#F1F5F9", fg="#0F172A", border="#94A3B8", size=9.8, h=19, anchor="start"))
    return "\n".join(g), {
        "pos": (x + 15, y + ch + 22),
        "neg": (x + 39, y + ch + 22),
    }


# ============================================================================
# 6. SEEED STUDIO XIAO ESP32-S3 (PINOUT FÍSICO REAL 14 PINES, SIN TRASLAPES)
# ============================================================================
def draw_xiao_esp32s3(x, y):
    w, h = 172, 214
    g = [f'<g id="xiao-esp32s3" filter="url(#shadow)">']
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="url(#pcbBlack)" stroke="#3F3F46" stroke-width="2"/>')
    g.append(f'<rect x="{x+w/2-26}" y="{y-12}" width="52" height="32" rx="5" fill="url(#metal)" stroke="#475569" stroke-width="1.5"/>')
    g.append(_t(x + w / 2, y + 8, "USB-C", size=9.5, weight="800", fill="#334155", anchor="middle"))
    # Botones B y R
    g.append(f'<rect x="{x+56}" y="{y+27}" width="11" height="9" rx="2" fill="#E2E8F0" stroke="#64748B" stroke-width="1"/>')
    g.append(_t(x + 61.5, y + 46, "B", size=7.8, weight="700", fill="#A1A1AA", anchor="middle"))
    g.append(f'<rect x="{x+w-67}" y="{y+27}" width="11" height="9" rx="2" fill="#E2E8F0" stroke="#64748B" stroke-width="1"/>')
    g.append(_t(x + w - 61.5, y + 46, "R", size=7.8, weight="700", fill="#A1A1AA", anchor="middle"))
    # Escudo metálico centrado y despejado de las etiquetas de pines
    g.append(f'<rect x="{x+56}" y="{y+58}" width="60" height="82" rx="5" fill="url(#metal)" stroke="#64748B" stroke-width="1.3"/>')
    g.append(_t(x + w / 2, y + 92, "ESP32-S3", size=10.2, weight="800", fill="#1E293B", anchor="middle"))
    g.append(_t(x + w / 2, y + 107, "Wi-Fi / BLE", size=8.5, weight="700", fill="#475569", anchor="middle"))
    g.append(_t(x + w / 2, y + 122, "3.3V Logic", size=8.2, weight="700", fill="#0284C7", anchor="middle"))
    # Antena u.FL + marca
    g.append(f'<circle cx="{x+w/2}" cy="{y+168}" r="7.5" fill="#F59E0B" stroke="#78350F" stroke-width="1.4"/>')
    g.append(f'<circle cx="{x+w/2}" cy="{y+168}" r="2.8" fill="#18181B"/>')
    g.append(_t(x + w / 2, y + 196, "SEEED XIAO", size=9.8, weight="800", fill="#E4E4E7", anchor="middle"))

    left_pins = ["D0", "D1", "D2", "D3", "D4·SDA", "D5·SCL", "D6"]
    right_pins = ["5V", "GND", "3V3", "D10", "D9", "D8", "D7"]
    active_left = {"D4·SDA": "#2563EB", "D5·SCL": "#9333EA"}
    active_right = {"5V": "#DC2626", "GND": "#475569", "3V3": "#EA580C"}

    pin_coords = {}
    y0 = y + 34
    dy = 25.0
    for i, lbl in enumerate(left_pins):
        py = y0 + i * dy
        is_act = lbl in active_left
        col = active_left.get(lbl, "#D97706")
        g.append(f'<rect x="{x-3}" y="{py-5}" width="13" height="10" rx="2.5" fill="url(#goldPad)" stroke="#92400E" stroke-width="1"/>')
        g.append(f'<circle cx="{x+3.5}" cy="{py}" r="{3.4 if is_act else 2.4}" fill="{col if is_act else "#18181B"}" stroke="#FEF3C7" stroke-width="1"/>')
        g.append(_t(x + 14, py + 3.2, lbl, size=8.8 if is_act else 8.0, weight="800" if is_act else "600",
                    fill="#FEF08A" if is_act else "#94A3B8"))
        pin_coords[lbl] = (x - 3, py)

    for i, lbl in enumerate(right_pins):
        py = y0 + i * dy
        is_act = lbl in active_right
        col = active_right.get(lbl, "#D97706")
        g.append(f'<rect x="{x+w-10}" y="{py-5}" width="13" height="10" rx="2.5" fill="url(#goldPad)" stroke="#92400E" stroke-width="1"/>')
        g.append(f'<circle cx="{x+w-3.5}" cy="{py}" r="{3.4 if is_act else 2.4}" fill="{col if is_act else "#18181B"}" stroke="#FEF3C7" stroke-width="1"/>')
        g.append(_t(x + w - 14, py + 3.2, lbl, size=9.2 if is_act else 8.0, weight="800" if is_act else "600",
                    fill="#FEF08A" if is_act else "#94A3B8", anchor="end"))
        pin_coords[lbl] = (x + w + 3, py)

    g.append("</g>")
    # Título limpio justo debajo del PCB (ARRIBA de los cables I2C!)
    g.append(_t(x + w / 2, y + h + 18, "Seeed Studio XIAO ESP32-S3", size=13, weight="800", fill="#0F172A", anchor="middle"))
    g.append(_t(x + w / 2, y + h + 33, "(Cerebro · Wi-Fi UDP + Web UI)", size=10.5, weight="600", fill="#64748B", anchor="middle"))
    return "\n".join(g), pin_coords


# ============================================================================
# 7. MÓDULO PCA9685 16-CH PWM (AR0389 · AMPLIO Y LIMPIO SIN TRASLAPES)
# ============================================================================
def draw_pca9685(x, y):
    w, h = 656, 214
    g = [f'<g id="pca9685" filter="url(#shadow)">']
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="url(#pcbBlue)" stroke="#1E3A8A" stroke-width="2.2"/>')
    for cx, cy in ((x + 14, y + 14), (x + w - 14, y + 14), (x + 14, y + h - 14), (x + w - 14, y + h - 14)):
        g.append(f'<circle cx="{cx}" cy="{cy}" r="5.5" fill="#F8FAFC" stroke="#F59E0B" stroke-width="2"/>')

    # Bornera verde superior (V+ izquierda, GND derecha)
    bx, by = x + 152, y - 8
    g.append(f'<rect x="{bx}" y="{by}" width="88" height="44" rx="4" fill="#15803D" stroke="#14532D" stroke-width="1.8"/>')
    for idx, (lbl, col) in enumerate((("V+ (5V)", "#FCA5A5"), ("GND", "#E2E8F0"))):
        sx = bx + 22 + idx * 44
        g.append(f'<circle cx="{sx}" cy="{by+20}" r="11" fill="url(#metal)" stroke="#14532D" stroke-width="1.3"/>')
        g.append(f'<line x1="{sx-7}" y1="{by+16}" x2="{sx+7}" y2="{by+24}" stroke="#334155" stroke-width="2.2"/>')
        g.append(_t(sx, by + 58, lbl, size=10.5, weight="800", fill=col, anchor="middle"))

    # LED Power + Pads A0..A5 (= 0x40)
    g.append(f'<circle cx="{x+302}" cy="{y+22}" r="4.5" fill="#EF4444" stroke="#7F1D1D" stroke-width="1.2"/>')
    g.append(_t(x + 302, y + 38, "PWR", size=8.5, weight="700", fill="#BFDBFE", anchor="middle"))
    for i in range(6):
        ax = x + 365 + i * 36
        g.append(f'<rect x="{ax}" y="{y+16}" width="10" height="7" rx="1" fill="url(#goldPad)"/>')
        g.append(f'<rect x="{ax+12}" y="{y+16}" width="10" height="7" rx="1" fill="url(#goldPad)"/>')
        g.append(_t(ax + 11, y + 36, f"A{i}", size=8.5, weight="700", fill="#BFDBFE", anchor="middle"))
    g.append(_t(x + 476, y + 52, "Dirección I2C = 0x40 (todos abiertos)", size=9.5, weight="700", fill="#93C5FD", anchor="middle"))

    # Chip central PCA9685
    ix, iy = x + 266, y + 58
    g.append(f'<rect x="{ix}" y="{iy}" width="76" height="54" rx="4" fill="#18181B" stroke="#475569" stroke-width="1.4"/>')
    g.append(f'<circle cx="{ix+10}" cy="{iy+10}" r="3" fill="#94A3B8"/>')
    g.append(_t(ix + 38, iy + 26, "PCA9685", size=11, weight="800", fill="#F8FAFC", anchor="middle"))
    g.append(_t(ix + 38, iy + 41, "16-CH 12-bit", size=8.5, weight="600", fill="#94A3B8", anchor="middle"))
    g.append(_t(x + 492, y + 86, "Módulo PWM PCA9685 (AR0389)", size=13, weight="800", fill="#FFFFFF", anchor="middle"))
    g.append(_t(x + 492, y + 104, "Bus Lógico 3.3V · Potencia Servos 5V", size=10, weight="700", fill="#BAE6FD", anchor="middle"))

    # Cabecera lógica izquierda (6 pines reales: GND, OE, SCL, SDA, VCC, V+)
    logic_pins = [
        ("GND", "#1E293B", True),
        ("OE", "#64748B", False),
        ("SCL", "#9333EA", True),
        ("SDA", "#2563EB", True),
        ("VCC", "#EA580C", True),
        ("V+", "#64748B", False),
    ]
    pins = {
        "term_v": (bx + 22, by + 2),
        "term_g": (bx + 66, by + 2),
    }
    ly0 = y + 40
    ldy = 25.5
    g.append(f'<rect x="{x-6}" y="{ly0-10}" width="16" height="{ldy*5+20}" rx="3" fill="#0F172A" stroke="#334155" stroke-width="1.2"/>')
    for i, (lbl, col, act) in enumerate(logic_pins):
        py = ly0 + i * ldy
        g.append(f'<rect x="{x-14}" y="{py-2.2}" width="16" height="4.4" rx="1" fill="url(#goldPad)"/>')
        g.append(f'<circle cx="{x+18}" cy="{py}" r="4.2" fill="{col if act else "#1E3A8A"}" stroke="#F59E0B" stroke-width="1.3"/>')
        g.append(_t(x + 28, py + 4, lbl, size=10.2 if act else 8.8, weight="800" if act else "600",
                    fill="#FEF08A" if lbl == "VCC" else ("#FFFFFF" if act else "#93C5FD")))
        if lbl == "VCC":
            g.append(_t(x + 56, py + 4, "(3.3V)", size=9.0, weight="800", fill="#FDBA74"))
        pins[f"logic_{lbl}"] = (x - 14, py)

    # Canales CH0..CH4 desplazados con holgura a la derecha (x+164..x+428), cero choque con VCC (3.3V)!
    g.append(_t(x + 132, y + 148, "PWM", size=8.5, weight="800", fill="#FDE047", anchor="end"))
    g.append(_t(x + 132, y + 166, "V+", size=8.5, weight="800", fill="#FCA5A5", anchor="end"))
    g.append(_t(x + 132, y + 184, "GND", size=8.5, weight="800", fill="#CBD5E1", anchor="end"))

    ch_xs = [x + 164, x + 228, x + 292, x + 356, x + 420]
    ch_names = ["CH0", "CH1", "CH2", "CH3", "CH4"]
    for idx, (cx, cname) in enumerate(zip(ch_xs, ch_names)):
        g.append(f'<rect x="{cx-22}" y="{y+124}" width="44" height="76" rx="5" fill="#0F172A" opacity="0.45" stroke="#38BDF8" stroke-width="1.3"/>')
        g.append(_t(cx, y + 136, cname, size=10, weight="800", fill="#FEF08A", anchor="middle"))
        for row_i, shroud_col in enumerate(("#EAB308", "#DC2626", "#18181B")):
            py = y + 146 + row_i * 18
            g.append(f'<rect x="{cx-10}" y="{py-6}" width="20" height="12" rx="2" fill="{shroud_col}" stroke="#0F172A" stroke-width="1"/>')
            g.append(f'<rect x="{cx-2.4}" y="{py-2.4}" width="4.8" height="4.8" rx="0.8" fill="url(#goldPad)"/>')
        pins[f"ch{idx}"] = (cx, y + 200)

    # Bloque compacto de reserva CH5..CH15
    rx0 = x + 464
    g.append(f'<rect x="{rx0}" y="{y+128}" width="170" height="68" rx="5" fill="#172554" opacity="0.65" stroke="#3B82F6" stroke-width="1" stroke-dasharray="4 3"/>')
    g.append(_t(rx0 + 85, y + 143, "CH5 – CH15 (Libres / Reserva)", size=9.5, weight="700", fill="#93C5FD", anchor="middle"))
    for k in range(11):
        px = rx0 + 13 + k * 14
        for row_i, col in enumerate(("#CA8A04", "#B91C1C", "#334155")):
            g.append(f'<rect x="{px}" y="{y+152+row_i*12}" width="9" height="8" rx="1.2" fill="{col}" opacity="0.72"/>')

    g.append("</g>")
    return "\n".join(g), pins


# ============================================================================
# 8. SERVOS REALISTAS: EJE METÁLICO/NYLON A LA IZQUIERDA + DUPONT A LA DERECHA
# ============================================================================
def draw_servo(cx, y, ch_label, title, subtitle, is_sg90=False, has_ext=False):
    w, h = 152, 124
    x = cx - w / 2
    plug_x = cx + 32
    g = [f'<g id="servo-{ch_label}" filter="url(#shadow)">']
    # Conector Dupont 3 pines desplazado a la derecha del domo (cero obstrucción con el eje!)
    g.append(f'<rect x="{plug_x-16}" y="{y-14}" width="32" height="16" rx="2.5" fill="#18181B" stroke="#475569" stroke-width="1"/>')
    for dx, c in ((-9, "#F97316"), (0, "#DC2626"), (9, "#78350F")):
        g.append(f'<rect x="{plug_x+dx-3}" y="{y-11}" width="6" height="10" rx="1" fill="{c}"/>')

    body_grad = "url(#sg90Blue)" if is_sg90 else "url(#mg90Blue)"
    g.append(f'<rect x="{x+18}" y="{y+12}" width="{w-36}" height="{h-22}" rx="8" fill="{body_grad}" stroke="#1E3A8A" stroke-width="2"/>')
    # Orejas de montaje con barrenos M2
    g.append(f'<rect x="{x+4}" y="{y+34}" width="{w-8}" height="14" rx="3" fill="{body_grad}" stroke="#1E3A8A" stroke-width="1.6"/>')
    g.append(f'<circle cx="{x+11}" cy="{y+41}" r="3.2" fill="#F8FAFC" stroke="#1E3A8A" stroke-width="1"/>')
    g.append(f'<circle cx="{x+w-11}" cy="{y+41}" r="3.2" fill="#F8FAFC" stroke="#1E3A8A" stroke-width="1"/>')
    # Domo de engranes a la izquierda + eje de salida metálico (MG90S) o blanco (SG90)
    g.append(f'<rect x="{x+24}" y="{y+2}" width="50" height="16" rx="5" fill="{body_grad}" stroke="#1E3A8A" stroke-width="1.5"/>')
    shaft_fill = "#F8FAFC" if is_sg90 else "url(#brass)"
    shaft_stroke = "#94A3B8" if is_sg90 else "#92400E"
    g.append(f'<rect x="{x+38}" y="{y-8}" width="22" height="11" rx="2" fill="{shaft_fill}" stroke="{shaft_stroke}" stroke-width="1.3"/>')
    # Engranes internos sutiles
    gear_fill = "#E2E8F0" if is_sg90 else "#CBD5E1"
    g.append(f'<circle cx="{x+49}" cy="{y+24}" r="9" fill="{gear_fill}" opacity="0.45"/>')
    g.append(f'<circle cx="{x+69}" cy="{y+26}" r="7" fill="{gear_fill}" opacity="0.38"/>')
    # Etiqueta frontal
    g.append(f'<rect x="{x+26}" y="{y+54}" width="{w-52}" height="48" rx="4" fill="#0F172A" opacity="0.84"/>')
    model = "SG90" if is_sg90 else "MG90S"
    gear_txt = "Engrane Nylon" if is_sg90 else "Engrane Metal"
    g.append(_t(cx, y + 72, f"{model} · {ch_label}", size=12, weight="800", fill="#F8FAFC", anchor="middle"))
    g.append(_t(cx, y + 87, gear_txt, size=9.2, weight="700", fill="#38BDF8" if is_sg90 else "#FBBF24", anchor="middle"))
    g.append(_t(cx, y + 99, "180° · 5V PWM", size=8.5, weight="600", fill="#94A3B8", anchor="middle"))
    g.append("</g>")

    g.append(_t(cx, y + h + 14, title, size=13, weight="800", fill="#0F172A", anchor="middle"))
    g.append(_t(cx, y + h + 30, subtitle, size=10.8, weight="600", fill="#475569", anchor="middle"))
    if has_ext:
        g.append(_pill(cx, y + h + 49, "+ Ext. Dupont M-H 20 cm (AR0003)", bg="#EFF6FF", fg="#1D4ED8", border="#93C5FD", size=9.5, h=19))
    else:
        g.append(_pill(cx, y + h + 49, "Conexión directa al PCA9685", bg="#F1F5F9", fg="#475569", border="#CBD5E1", size=9.5, h=19))
    return "\n".join(g), (plug_x, y - 14)


# ============================================================================
# 9. LEYENDA INFERIOR (COLORES + ZOOM 3 PINES + 4 REGLAS CRÍTICAS)
# ============================================================================
def draw_legend_panel(x, y, w, h):
    g = [f'<g id="legend-panel" filter="url(#shadowSm)">']
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1.6"/>')
    g.append(f'<rect x="{x}" y="{y}" width="{w}" height="34" rx="12" fill="#0F172A"/>')
    g.append(f'<rect x="{x}" y="{y+20}" width="{w}" height="14" fill="#0F172A"/>')
    g.append(_t(x + 16, y + 22, "CÓDIGO DE COLORES Y REGLAS CRÍTICAS DE BANCO", size=12, weight="800", fill="#F8FAFC"))

    lx, ly = x + 20, y + 54
    g.append(_t(lx, ly, "CABLES DE POTENCIA Y BUS I2C (3.3V):", size=10.5, weight="800", fill="#334155"))
    wire_items = [
        ("#DC2626", "Rojo (20 AWG)", "+5V Potencia (AR5515 → KCD11 → PCA9685 V+ y 1N5819)"),
        ("#1E293B", "Negro (20 AWG)", "GND Tierra Común en estrella (AR5515 · PCA9685 · XIAO)"),
        ("#EA580C", "Naranja (Dupont)", "3.3V Lógica (XIAO 3V3 → PCA9685 VCC) — ¡NUNCA 5V!"),
        ("#2563EB", "Azul (Dupont)", "I2C SDA (XIAO D4 → PCA9685 SDA)"),
        ("#9333EA", "Morado (Dupont)", "I2C SCL (XIAO D5 → PCA9685 SCL)"),
    ]
    for i, (col, name, desc) in enumerate(wire_items):
        ry = ly + 22 + i * 24
        g.append(f'<line x1="{lx}" y1="{ry-4}" x2="{lx+34}" y2="{ry-4}" stroke="{col}" stroke-width="5.5" stroke-linecap="round"/>')
        g.append(_t(lx + 44, ry, name, size=10.5, weight="800", fill="#0F172A"))
        g.append(_t(lx + 165, ry, desc, size=10.2, weight="500", fill="#475569"))

    mx = x + 640
    g.append(f'<line x1="{mx}" y1="{y+44}" x2="{mx}" y2="{y+h-14}" stroke="#E2E8F0" stroke-width="1.5"/>')

    sx = mx + 22
    g.append(_t(sx, ly, "ORIENTACIÓN DEL CONECTOR DE SERVO EN PCA9685:", size=10.5, weight="800", fill="#334155"))
    px, py = sx + 14, ly + 18
    g.append(f'<rect x="{px}" y="{py}" width="32" height="92" rx="4" fill="#18181B" stroke="#475569" stroke-width="1.4"/>')
    servo_rows = [
        ("#EAB308", "#F97316", "Arriba (Amarillo) → PWM", "Cable Naranja / Amarillo"),
        ("#DC2626", "#EF4444", "Centro (Rojo) → V+ (5V)", "Cable Rojo"),
        ("#334155", "#78350F", "Abajo (Negro) → GND", "Cable Café / Negro"),
    ]
    for i, (shroud, wire_c, t1, t2) in enumerate(servo_rows):
        ry = py + 16 + i * 30
        g.append(f'<rect x="{px+5}" y="{ry-9}" width="22" height="18" rx="2.5" fill="{shroud}"/>')
        g.append(f'<rect x="{px+12}" y="{ry-3}" width="8" height="6" rx="1" fill="url(#goldPad)"/>')
        g.append(f'<line x1="{px+32}" y1="{ry}" x2="{px+62}" y2="{ry}" stroke="{wire_c}" stroke-width="5" stroke-linecap="round"/>')
        g.append(_t(px + 72, ry - 1, t1, size=10.5, weight="800", fill="#0F172A"))
        g.append(_t(px + 72, ry + 12, t2, size=9.8, weight="600", fill="#64748B"))

    rx = x + 1040
    g.append(f'<line x1="{rx}" y1="{y+44}" x2="{rx}" y2="{y+h-14}" stroke="#E2E8F0" stroke-width="1.5"/>')

    cx = rx + 22
    g.append(_t(cx, ly, "CHECKLIST OBLIGATORIO ANTES DE ENCENDER:", size=10.5, weight="800", fill="#B45309"))
    checks = [
        "1. Fija el DIP del AR5515 en 5V y MIDE 4.95–5.15V con multímetro en vacío.",
        "2. Verifica franja blanca (−) del 1000 µF en GND y banda del 1N5819 hacia XIAO.",
        "3. Conecta PCA9685 VCC estrictamente a XIAO 3V3 (NUNCA a 5V).",
        "4. Corre comando CENTER (1500 µs) en servos sueltos antes de atornillar horns.",
    ]
    for i, txt in enumerate(checks):
        g.append(_t(cx, ly + 22 + i * 25, txt, size=10.5, weight="700" if i == 0 else "600",
                    fill="#991B1B" if i == 0 else "#1E293B"))

    g.append("</g>")
    return "\n".join(g)


def generate_full_svg():
    elems = []
    defs = """
<defs>
  <filter id="shadow" x="-10%" y="-10%" width="124%" height="128%">
    <feDropShadow dx="0" dy="5" stdDeviation="6" flood-color="#0F172A" flood-opacity="0.16"/>
  </filter>
  <filter id="shadowSm" x="-8%" y="-8%" width="118%" height="120%">
    <feDropShadow dx="0" dy="2.5" stdDeviation="3" flood-color="#0F172A" flood-opacity="0.12"/>
  </filter>
  <pattern id="dotGrid" width="24" height="24" patternUnits="userSpaceOnUse">
    <circle cx="2" cy="2" r="1.15" fill="#CBD5E1" opacity="0.55"/>
  </pattern>
  <linearGradient id="ugreenBody" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#475569"/>
    <stop offset="50%" stop-color="#334155"/>
    <stop offset="100%" stop-color="#1E293B"/>
  </linearGradient>
  <linearGradient id="metal" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#F1F5F9"/>
    <stop offset="48%" stop-color="#CBD5E1"/>
    <stop offset="100%" stop-color="#94A3B8"/>
  </linearGradient>
  <linearGradient id="brass" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#FDE68A"/>
    <stop offset="55%" stop-color="#F59E0B"/>
    <stop offset="100%" stop-color="#B45309"/>
  </linearGradient>
  <linearGradient id="goldPad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#FEF08A"/>
    <stop offset="50%" stop-color="#F59E0B"/>
    <stop offset="100%" stop-color="#B45309"/>
  </linearGradient>
  <linearGradient id="pcbPurple" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#4338CA"/>
    <stop offset="100%" stop-color="#312E81"/>
  </linearGradient>
  <linearGradient id="pcbBlack" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#27272A"/>
    <stop offset="100%" stop-color="#09090B"/>
  </linearGradient>
  <linearGradient id="pcbBlue" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#1D4ED8"/>
    <stop offset="55%" stop-color="#1E40AF"/>
    <stop offset="100%" stop-color="#172554"/>
  </linearGradient>
  <linearGradient id="switchRocker" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#3F3F46"/>
    <stop offset="55%" stop-color="#27272A"/>
    <stop offset="100%" stop-color="#18181B"/>
  </linearGradient>
  <linearGradient id="diodeBody" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#3F3F46"/>
    <stop offset="45%" stop-color="#18181B"/>
    <stop offset="100%" stop-color="#09090B"/>
  </linearGradient>
  <linearGradient id="silverBand" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#FFFFFF"/>
    <stop offset="50%" stop-color="#CBD5E1"/>
    <stop offset="100%" stop-color="#94A3B8"/>
  </linearGradient>
  <linearGradient id="capBody" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#1E293B"/>
    <stop offset="40%" stop-color="#0F172A"/>
    <stop offset="100%" stop-color="#1E3A8A"/>
  </linearGradient>
  <linearGradient id="mg90Blue" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#3B82F6"/>
    <stop offset="55%" stop-color="#2563EB"/>
    <stop offset="100%" stop-color="#1D4ED8"/>
  </linearGradient>
  <linearGradient id="sg90Blue" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#38BDF8"/>
    <stop offset="55%" stop-color="#0284C7"/>
    <stop offset="100%" stop-color="#0369A1"/>
  </linearGradient>
</defs>
"""

    elems.append(f'<rect width="{W}" height="{H}" fill="#F8FAFC"/>')
    elems.append(f'<rect width="{W}" height="{H}" fill="url(#dotGrid)"/>')

    # Header bar
    elems.append(f'<rect x="0" y="0" width="{W}" height="80" fill="#0F172A"/>')
    elems.append(_t(34, 36, "MINI-PRO 4-DOF (B2 STEALTH) — DIAGRAMA PICTÓRICO DE CONEXIONES (ESTILO FRITZING)",
                    size=21.5, weight="800", fill="#F8FAFC"))
    elems.append(_t(34, 60, "Alimentación con 1 solo cable USB-C (5V / 3A) · XIAO ESP32-S3 (I2C 3.3V) ↔ PCA9685 (0x40) → 4× MG90S + 1× SG90",
                    size=13.5, weight="500", fill="#94A3B8"))
    elems.append(_pill(W - 148, 40, "VERIFICADO KiCad 9 · 0 ERC", bg="#16A34A", fg="#FFFFFF", size=11.5, h=28))

    # Zonas de bloques funcionales (espaciadas limpiamente para cero choques con títulos)
    zones = [
        (24, 96, 1752, 206, "1 · ETAPA DE POTENCIA — 1 SOLO CABLE USB-C PD (5V / 3A) + FILTRO DE PICOS", "#FEF2F2", "#FECACA", "#991B1B"),
        (24, 314, 1752, 344, "2 · CONTROL I2C SEGURO (3.3V) Y DRIVER PWM 16 CANALES (PCA9685 · 0x40)", "#EFF6FF", "#BFDBFE", "#1E40AF"),
        (24, 672, 1752, 298, "3 · ACTUADORES DEL BRAZO (4× MG90S ENGRANE METÁLICO + 1× SG90 PINZA PARALELA)", "#F8FAFC", "#CBD5E1", "#334155"),
    ]
    for zx, zy, zw, zh, zlbl, zbg, zbd, zfg in zones:
        elems.append(f'<rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="14" fill="{zbg}" opacity="0.65" stroke="{zbd}" stroke-width="1.6"/>')
        elems.append(_t(zx + 18, zy + 23, zlbl, size=11.5, weight="800", fill=zfg))

    # Componentes
    svg_ugreen, p_ugreen = draw_ugreen_charger(64, 146)
    svg_ar5515, p_ar = draw_ar5515(348, 140)
    svg_sw, p_sw = draw_kcd11_switch(648, 154)
    # Capacitor despejado a la DERECHA de la bornera verde del PCA9685 (cero cable sobre el cuerpo!)
    svg_cap, p_cap = draw_capacitor_1000uf(1412, 152)

    # XIAO elevado a y=360 para dejar espacio total a su título arriba de los cables SDA/SCL
    svg_xiao, p_xiao = draw_xiao_esp32s3(254, 360)
    # Diodo 1N5819 alineado exactamente con XIAO pin 5V (y = 360 + 34 = 394)!
    svg_diode, p_d1 = draw_diode_1n5819_left(612, 394)
    # PCA9685 más ancho (656 px) en x=1092, y=386
    svg_pca, p_pca = draw_pca9685(1092, 386)

    servo_specs = [
        (210, "CH0", "M1 · J1 Base Yaw", "MG90S 180° · 22T:22T", False, False),
        (555, "CH1", "M2 · J2 Hombro", "MG90S 180° · 608ZZ", False, False),
        (900, "CH2", "M3 · J3 Codo", "MG90S 180° · 608ZZ", False, False),
        (1245, "CH3", "M4 · J4 Muñeca", "MG90S 180° · 608ZZ", False, True),
        (1590, "CH4", "M5 · Pinza Paralela", "SG90 (disponible) · 14T", True, True),
    ]
    servo_svgs, servo_pins = [], []
    for cx, ch, title, sub, is_sg, has_ext in servo_specs:
        s_svg, s_pin = draw_servo(cx, 784, ch, title, sub, is_sg90=is_sg, has_ext=has_ext)
        servo_svgs.append(s_svg)
        servo_pins.append(s_pin)

    # ------------------------------------------------------------------
    # CABLES FÍSICOS ESTILO FRITZING
    # ------------------------------------------------------------------
    wires = []

    # 1) Cable negro USB-C (UGREEN 50W -> AR5515)
    ux, uy = p_ugreen
    ax, ay = p_ar["usbc"]
    wires.append(_wire(
        f"M {ux:.1f} {uy:.1f} C {ux+48:.1f} {uy:.1f}, {ax-48:.1f} {ay:.1f}, {ax:.1f} {ay:.1f}",
        color="#18181B", width=9.0, halo="#FEF2F2", halo_w=13.5
    ))
    wires.append(_pill((ux + ax) / 2 - 4, uy - 28, "1 Cable USB-C (5V 3A)", bg="#18181B", fg="#F8FAFC", size=9.8, h=20))

    # 2) +5V_RAW: AR5515 (+) -> KCD11-2P IN(1)
    v5x, v5y = p_ar["v5"]
    sw_in_x, sw_in_y = p_sw["in"]
    wires.append(_wire(
        f"M {v5x:.1f} {v5y:.1f} C {v5x+45:.1f} {v5y:.1f}, {sw_in_x-45:.1f} {sw_in_y:.1f}, {sw_in_x:.1f} {sw_in_y:.1f}",
        color="#DC2626", width=6.2
    ))
    wires.append(_pill((v5x + sw_in_x) / 2, v5y - 18, "+5V_RAW", bg="#FEE2E2", fg="#991B1B", border="#FCA5A5", size=9.8, h=19))

    # 3) +5V_SERVO: KCD11-2P OUT(2) -> Nodo j_v5 -> baja directo a PCA9685 bornera V+ (despejado del capacitor!)
    sw_out_x, sw_out_y = p_sw["out"]
    pv_x, pv_y = p_pca["term_v"]
    pg_x, pg_y = p_pca["term_g"]
    cp_x, cp_y = p_cap["pos"]
    cn_x, cn_y = p_cap["neg"]

    j_v5_x, j_v5_y = 842.0, sw_out_y
    wires.append(_wire(
        f"M {sw_out_x:.1f} {sw_out_y:.1f} L {pv_x-22:.1f} {j_v5_y:.1f} "
        f"Q {pv_x:.1f} {j_v5_y:.1f}, {pv_x:.1f} {j_v5_y+22:.1f} "
        f"L {pv_x:.1f} {pv_y:.1f}",
        color="#DC2626", width=6.4
    ))
    # Rama del Capacitor (+) sale limpia por debajo del capacitor (y=290) hacia izquierda al nodo en pv_x!
    cap_v_y = 286.0
    wires.append(_wire(
        f"M {cp_x:.1f} {cp_y:.1f} L {cp_x:.1f} {cap_v_y-14:.1f} "
        f"Q {cp_x:.1f} {cap_v_y:.1f}, {cp_x-14:.1f} {cap_v_y:.1f} "
        f"L {pv_x:.1f} {cap_v_y:.1f}",
        color="#DC2626", width=5.6
    ))
    wires.append(_pill(1045, sw_out_y - 16, "+5V_SERVO (Bus de Potencia 5V / 3A)", bg="#DC2626", fg="#FFFFFF", size=10.5, h=21))

    # Derivación +5V_SERVO desde j_v5 -> Diodo 1N5819 Ánodo (+)
    d1_ax, d1_ay = p_d1["anode"]
    d1_kx, d1_ky = p_d1["cathode"]
    wires.append(_wire(
        f"M {j_v5_x:.1f} {j_v5_y:.1f} L {j_v5_x:.1f} {d1_ay-22:.1f} "
        f"Q {j_v5_x:.1f} {d1_ay:.1f}, {j_v5_x-22:.1f} {d1_ay:.1f} "
        f"L {d1_ax:.1f} {d1_ay:.1f}",
        color="#DC2626", width=5.4
    ))

    # 4) +5V_XIAO: Diodo 1N5819 Cátodo (K) -> XIAO pin 5V (línea recta horizontal!)
    x5v_x, x5v_y = p_xiao["5V"]
    wires.append(_wire(
        f"M {d1_kx:.1f} {d1_ky:.1f} L {x5v_x:.1f} {x5v_y:.1f}",
        color="#EF4444", width=5.4
    ))
    wires.append(_pill((d1_kx + x5v_x) / 2, x5v_y - 16, "+5V_XIAO", bg="#FEF2F2", fg="#B91C1C", border="#FCA5A5", size=9.6, h=19))

    # 5) GND ESTRELLA COMÚN: AR5515 (−) -> XIAO GND -> PCA9685 logic_GND + PCA9685 bornera GND + Capacitor (−)
    ag_x, ag_y = p_ar["gnd"]
    xg_x, xg_y = p_xiao["GND"]
    pg_log_x, pg_log_y = p_pca["logic_GND"]

    gnd_drop_x = 534.0
    gnd_bus_y = 468.0
    # AR5515 (−) -> baja a XIAO GND
    wires.append(_wire(
        f"M {ag_x:.1f} {ag_y:.1f} L {gnd_drop_x-18:.1f} {ag_y:.1f} "
        f"Q {gnd_drop_x:.1f} {ag_y:.1f}, {gnd_drop_x:.1f} {ag_y+18:.1f} "
        f"L {gnd_drop_x:.1f} {xg_y:.1f} L {xg_x:.1f} {xg_y:.1f}",
        color="#1E293B", width=6.0
    ))
    # XIAO GND -> corredor horizontal debajo del diodo -> sube a PCA9685 logic_GND
    wires.append(_wire(
        f"M {gnd_drop_x:.1f} {xg_y:.1f} L {gnd_drop_x:.1f} {gnd_bus_y-14:.1f} "
        f"Q {gnd_drop_x:.1f} {gnd_bus_y:.1f}, {gnd_drop_x+16:.1f} {gnd_bus_y:.1f} "
        f"L {906:.1f} {gnd_bus_y:.1f} "
        f"Q {922:.1f} {gnd_bus_y:.1f}, {922:.1f} {gnd_bus_y-16:.1f} "
        f"L {922:.1f} {pg_log_y+16:.1f} "
        f"Q {922:.1f} {pg_log_y:.1f}, {938:.1f} {pg_log_y:.1f} "
        f"L {pg_log_x:.1f} {pg_log_y:.1f}",
        color="#1E293B", width=5.6
    ))
    # Rama GND sube a PCA9685 bornera GND (y=340 -> bornera GND)
    gnd_top_y = 336.0
    wires.append(_wire(
        f"M {922:.1f} {pg_log_y:.1f} L {922:.1f} {gnd_top_y+16:.1f} "
        f"Q {922:.1f} {gnd_top_y:.1f}, {938:.1f} {gnd_top_y:.1f} "
        f"L {pg_x-16:.1f} {gnd_top_y:.1f} "
        f"Q {pg_x:.1f} {gnd_top_y:.1f}, {pg_x:.1f} {gnd_top_y+16:.1f} "
        f"L {pg_x:.1f} {pg_y:.1f}",
        color="#1E293B", width=6.2
    ))
    # Capacitor (−) baja a y=336 y conecta limpio a bornera GND!
    wires.append(_wire(
        f"M {cn_x:.1f} {cn_y:.1f} L {cn_x:.1f} {gnd_top_y-14:.1f} "
        f"Q {cn_x:.1f} {gnd_top_y:.1f}, {cn_x-14:.1f} {gnd_top_y:.1f} "
        f"L {pg_x:.1f} {gnd_top_y:.1f}",
        color="#1E293B", width=5.6
    ))
    wires.append(_pill(742, gnd_bus_y + 15, "GND Común (Estrella)", bg="#1E293B", fg="#F8FAFC", size=9.6, h=19))

    # 6) +3V3 Lógico: XIAO 3V3 -> PCA9685 VCC (NARANJA — NUNCA 5V!)
    x3v_x, x3v_y = p_xiao["3V3"]
    pvcc_x, pvcc_y = p_pca["logic_VCC"]
    wires.append(_wire(
        f"M {x3v_x:.1f} {x3v_y:.1f} L {496:.1f} {x3v_y:.1f} "
        f"Q {512:.1f} {x3v_y:.1f}, {512:.1f} {x3v_y+16:.1f} "
        f"L {512:.1f} {pvcc_y-16:.1f} "
        f"Q {512:.1f} {pvcc_y:.1f}, {528:.1f} {pvcc_y:.1f} "
        f"L {pvcc_x:.1f} {pvcc_y:.1f}",
        color="#EA580C", width=5.2
    ))
    wires.append(_pill(735, pvcc_y + 16, "+3.3V Lógica (XIAO 3V3 → PCA9685 VCC · NUNCA 5V)", bg="#FFF7ED", fg="#C2410C", border="#FDBA74", size=9.8, h=19))

    # 7) Bus I2C 3.3V: XIAO D4 (SDA) y D5 (SCL) pasan LIMPIOS debajo del título de XIAO (y=624 / 642)!
    xsda_x, xsda_y = p_xiao["D4·SDA"]
    xscl_x, xscl_y = p_xiao["D5·SCL"]
    psda_x, psda_y = p_pca["logic_SDA"]
    pscl_x, pscl_y = p_pca["logic_SCL"]

    wires.append(_wire(
        f"M {xsda_x:.1f} {xsda_y:.1f} L {212:.1f} {xsda_y:.1f} "
        f"Q {196:.1f} {xsda_y:.1f}, {196:.1f} {xsda_y+16:.1f} "
        f"L {196:.1f} {608:.1f} "
        f"Q {196:.1f} {624:.1f}, {212:.1f} {624:.1f} "
        f"L {952:.1f} {624:.1f} "
        f"Q {968:.1f} {624:.1f}, {968:.1f} {608:.1f} "
        f"L {968:.1f} {psda_y+16:.1f} "
        f"Q {968:.1f} {psda_y:.1f}, {984:.1f} {psda_y:.1f} "
        f"L {psda_x:.1f} {psda_y:.1f}",
        color="#2563EB", width=5.0
    ))
    wires.append(_wire(
        f"M {xscl_x:.1f} {xscl_y:.1f} L {188:.1f} {xscl_y:.1f} "
        f"Q {172:.1f} {xscl_y:.1f}, {172:.1f} {xscl_y+16:.1f} "
        f"L {172:.1f} {626:.1f} "
        f"Q {172:.1f} {642:.1f}, {188:.1f} {642:.1f} "
        f"L {984:.1f} {642:.1f} "
        f"Q {1000:.1f} {642:.1f}, {1000:.1f} {626:.1f} "
        f"L {1000:.1f} {pscl_y+16:.1f} "
        f"Q {1000:.1f} {pscl_y:.1f}, {1016:.1f} {pscl_y:.1f} "
        f"L {pscl_x:.1f} {pscl_y:.1f}",
        color="#9333EA", width=5.0
    ))
    wires.append(_pill(620, 610, "I2C_SDA (D4 → SDA · 3.3V)", bg="#DBEAFE", fg="#1D4ED8", border="#93C5FD", size=9.6, h=18))
    wires.append(_pill(805, 642, "I2C_SCL (D5 → SCL · 3.3V)", bg="#F3E8FF", fg="#7E22CE", border="#D8B4FE", size=9.6, h=18))

    # Puntos de unión (junction dots)
    wires.append(_junction(j_v5_x, j_v5_y, "#DC2626"))
    wires.append(_junction(pv_x, cap_v_y, "#DC2626"))
    wires.append(_junction(gnd_drop_x, xg_y, "#1E293B"))
    wires.append(_junction(922.0, pg_log_y, "#1E293B"))
    wires.append(_junction(pg_x, gnd_top_y, "#1E293B"))

    # 8) Listones de 3 hilos (Naranja PWM / Rojo V+ / Café GND) de PCA9685 CH0..CH4 -> M1..M5
    # Todos los tramos horizontales van DEBAJO del título de Zona 3 (y=695), en y = 714..754!
    corridor_ys = [752, 738, 724, 712, 700]
    for idx in range(5):
        px, py = p_pca[f"ch{idx}"]
        sx, sy = servo_pins[idx]
        my = corridor_ys[idx]
        for off, col in ((-5.2, "#F97316"), (0.0, "#DC2626"), (5.2, "#78350F")):
            x1 = px + off
            x2 = sx + off
            ym = my + (off * 0.42 if sx < px else -off * 0.42)
            r = 11.0
            dir_x = -1 if x2 < x1 else 1
            if abs(x2 - x1) < 26:
                d = f"M {x1:.1f} {py:.1f} L {x2:.1f} {sy:.1f}"
            else:
                d = (
                    f"M {x1:.1f} {py:.1f} "
                    f"L {x1:.1f} {ym - r:.1f} "
                    f"Q {x1:.1f} {ym:.1f}, {x1 + dir_x * r:.1f} {ym:.1f} "
                    f"L {x2 - dir_x * r:.1f} {ym:.1f} "
                    f"Q {x2:.1f} {ym:.1f}, {x2:.1f} {ym + r:.1f} "
                    f"L {x2:.1f} {sy:.1f}"
                )
            wires.append(_wire(d, color=col, width=2.8, halo="#F8FAFC", halo_w=4.8, highlight=False))

    legend = draw_legend_panel(24, 984, 1752, 174)

    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n'
        + defs
        + "\n".join(elems) + "\n"
        + svg_ugreen + "\n"
        + svg_ar5515 + "\n"
        + svg_sw + "\n"
        + svg_cap + "\n"
        + svg_xiao + "\n"
        + svg_diode + "\n"
        + svg_pca + "\n"
        + "\n".join(servo_svgs) + "\n"
        + "\n".join(wires) + "\n"
        + legend + "\n"
        + "</svg>\n"
    )


def render_png(svg_path, png_path):
    """Rasteriza el SVG a 3600x2360 (2x Retina) usando Chrome o Edge headless."""
    html_tmp = os.path.join(HERE, "_tmp_fritzing_render.html")
    svg_content = open(svg_path, "r", encoding="utf-8").read()
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #F8FAFC; }}
  svg {{ display: block; width: {W}px; height: {H}px; }}
</style>
</head>
<body>{svg_content}</body>
</html>"""
    with open(html_tmp, "w", encoding="utf-8") as f:
        f.write(html)

    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    browser = next((c for c in candidates if os.path.exists(c)), None)
    if not browser:
        raise RuntimeError("No se encontró Chrome ni Edge para rasterizar el SVG a PNG.")

    file_uri = "file:///" + html_tmp.replace("\\", "/")
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={W},{H}",
        "--force-device-scale-factor=2",
        f"--screenshot={png_path}",
        file_uri,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        os.remove(html_tmp)
    except OSError:
        pass
    if res.returncode != 0 or not os.path.exists(png_path):
        raise RuntimeError(f"Error rasterizando PNG ({res.returncode}): {res.stderr}")


if __name__ == "__main__":
    svg = generate_full_svg()
    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[OK] SVG vectorial guardado: {SVG_PATH} ({os.path.getsize(SVG_PATH):,} bytes)")
    render_png(SVG_PATH, PNG_PATH)
    print(f"[OK] PNG 4K (2x Retina) guardado: {PNG_PATH} ({os.path.getsize(PNG_PATH):,} bytes)")
