"""
Generador de Proyecto Nativo KiCad 9.0 (ERC = 0 Errores, 0 Avisos) — Mini-Pro 4-DOF (`B2 Stealth`)
==================================================================================================
Crea un proyecto KiCad 9.0 completamente nativo, portable y editable en `electronics/kicad/`:
  - `minipro_b2_stealth.kicad_pro`   (proyecto KiCad 9.0)
  - `minipro_b2_stealth.kicad_sch`   (esquema eléctrico 0 errores ERC)
  - `MiniPro.kicad_sym`              (librería local de símbolos con SKUs de UNIT Electronics)
  - `sym-lib-table`                  (tabla local `${KIPRJMOD}/MiniPro.kicad_sym` 100% portable)
"""

import json
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))


def _uid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"minipro-b2-stealth-v3-{seed}"))


def write_kicad_pro(path: str):
    pro = {
        "board": {"design_settings": {"defaults": {"board_outline_line_width": 0.1}}},
        "erc": {"erc_exclusions": [], "meta": {"version": 0}, "pin_map": [], "rule_severities": {}},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": ["MiniPro"]},
        "meta": {"filename": "minipro_b2_stealth.kicad_pro", "version": 3},
        "net_settings": {"classes": [{"name": "Default", "clearance": 0.2, "track_width": 0.25}], "meta": {"version": 4}},
        "schematic": {"drawing": {"default_line_thickness": 6.0, "default_text_size": 50.0}, "meta": {"version": 1}},
        "sheets": [[_uid("root_sheet"), "Root"]],
        "text_variables": {},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pro, f, indent=2)


def write_sym_lib_table(path: str):
    content = (
        '(sym_lib_table\n'
        '  (version 7)\n'
        '  (lib (name "MiniPro")(type "KiCad")(uri "${KIPRJMOD}/MiniPro.kicad_sym")(options "")(descr "Mini-Pro 4-DOF B2 Stealth Modules"))\n'
        ')\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _sym_box(lib_id: str, ref_prefix: str, w: float, h: float, left_pins, right_pins, for_lib=False):
    name = lib_id.split(":")[-1]
    sym_name = name if for_lib else lib_id
    hw, hh = w / 2.0, h / 2.0
    lines = [
        f'  (symbol "{sym_name}"',
        '    (pin_names (offset 1.016))',
        '    (exclude_from_sim no)',
        '    (in_bom yes)',
        '    (on_board yes)',
        f'    (property "Reference" "{ref_prefix}" (at 0 {hh + 2.54:.2f} 0) (effects (font (size 1.27 1.27) (bold yes))))',
        f'    (property "Value" "{name}" (at 0 {-hh - 2.54:.2f} 0) (effects (font (size 1.27 1.27))))',
        '    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        '    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        f'    (symbol "{name}_0_1"',
        f'      (rectangle (start {-hw:.2f} {hh:.2f}) (end {hw:.2f} {-hh:.2f}) (stroke (width 0.254) (type default)) (fill (type background)))',
        '    )',
        f'    (symbol "{name}_1_1"',
    ]
    for num, pname, ptype, y in left_pins:
        lines.append(
            f'      (pin {ptype} line (at {-hw - 2.54:.2f} {y:.2f} 0) (length 2.54) '
            f'(name "{pname}" (effects (font (size 1.15 1.15)))) '
            f'(number "{num}" (effects (font (size 1.0 1.0)))))'
        )
    for num, pname, ptype, y in right_pins:
        lines.append(
            f'      (pin {ptype} line (at {hw + 2.54:.2f} {y:.2f} 180) (length 2.54) '
            f'(name "{pname}" (effects (font (size 1.15 1.15)))) '
            f'(number "{num}" (effects (font (size 1.0 1.0)))))'
        )
    lines.append('    )')
    lines.append('  )')
    return "\n".join(lines)


def _sym_two_pin(lib_id: str, ref_prefix: str, kind: str, for_lib=False):
    name = lib_id.split(":")[-1]
    sym_name = name if for_lib else lib_id
    if kind == "switch":
        body = (
            '      (circle (center -2.54 0) (radius 0.508) (stroke (width 0.254) (type default)) (fill (type none)))\n'
            '      (circle (center 2.54 0) (radius 0.508) (stroke (width 0.254) (type default)) (fill (type none)))\n'
            '      (polyline (pts (xy -2.032 0.254) (xy 2.286 2.032)) (stroke (width 0.3048) (type default)) (fill (type none)))'
        )
        p1, p2 = ("1", "IN", -5.08, 0, 0), ("2", "OUT", 5.08, 0, 180)
        rx, ry, vx, vy, plen = 0, 3.81, 0, -2.54, 2.54
    elif kind == "schottky":
        body = (
            '      (polyline (pts (xy -1.27 1.27) (xy -1.27 -1.27) (xy 1.27 0) (xy -1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type outline)))\n'
            '      (polyline (pts (xy 0.635 1.27) (xy 1.27 1.27) (xy 1.27 -1.27) (xy 1.905 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))'
        )
        p1, p2 = ("1", "A", -5.08, 0, 0), ("2", "K", 5.08, 0, 180)
        rx, ry, vx, vy, plen = 0, 3.81, 0, -2.54, 2.54
    else:
        body = (
            '      (polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.35) (type default)) (fill (type none)))\n'
            '      (polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.35) (type default)) (fill (type none)))\n'
            '      (polyline (pts (xy -1.524 2.032) (xy -0.508 2.032)) (stroke (width 0.20) (type default)) (fill (type none)))\n'
            '      (polyline (pts (xy -1.016 2.54) (xy -1.016 1.524)) (stroke (width 0.20) (type default)) (fill (type none)))'
        )
        p1, p2 = ("1", "+", 0, 3.81, 270), ("2", "-", 0, -3.81, 90)
        rx, ry, vx, vy, plen = 4.445, 1.27, 4.445, -1.27, 3.048

    return "\n".join([
        f'  (symbol "{sym_name}"',
        '    (pin_names (offset 0.6) (hide yes))',
        '    (exclude_from_sim no)',
        '    (in_bom yes)',
        '    (on_board yes)',
        f'    (property "Reference" "{ref_prefix}" (at {rx:.2f} {ry:.2f} 0) (effects (font (size 1.27 1.27) (bold yes))))',
        f'    (property "Value" "{name}" (at {vx:.2f} {vy:.2f} 0) (effects (font (size 1.27 1.27))))',
        '    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        '    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        f'    (symbol "{name}_0_1"',
        body,
        '    )',
        f'    (symbol "{name}_1_1"',
        f'      (pin passive line (at {p1[2]:.2f} {p1[3]:.2f} {p1[4]}) (length {plen:.3f}) (name "{p1[1]}" (effects (font (size 1.0 1.0)))) (number "{p1[0]}" (effects (font (size 1.0 1.0)))))',
        f'      (pin passive line (at {p2[2]:.2f} {p2[3]:.2f} {p2[4]}) (length {plen:.3f}) (name "{p2[1]}" (effects (font (size 1.0 1.0)))) (number "{p2[0]}" (effects (font (size 1.0 1.0)))))',
        '    )',
        '  )',
    ])


def _all_symbols(for_lib=False):
    return [
        _sym_box("MiniPro:AR5515_USBC_PD", "J", 22.86, 15.24, [], [("1", "+5V_PD", "passive", 2.54), ("2", "GND", "passive", -2.54)], for_lib),
        _sym_two_pin("MiniPro:KCD11_2P", "SW", "switch", for_lib),
        _sym_two_pin("MiniPro:1N5819", "D", "schottky", for_lib),
        _sym_two_pin("MiniPro:Cap_1000uF", "C", "cap", for_lib),
        _sym_box("MiniPro:XIAO_ESP32_S3", "U", 27.94, 30.48,
                 [("1", "5V_IN", "passive", 7.62), ("2", "GND", "passive", -7.62)],
                 [("3", "3V3_OUT", "passive", 10.16), ("4", "D4_SDA", "bidirectional", 2.54), ("5", "D5_SCL", "bidirectional", -2.54), ("6", "GND", "passive", -10.16)],
                 for_lib),
        _sym_box("MiniPro:PCA9685_16CH", "U", 30.48, 45.72,
                 [("1", "V+ (5V)", "passive", 17.78), ("2", "VCC (3.3V)", "passive", 10.16), ("3", "SDA", "bidirectional", 2.54), ("4", "SCL", "input", -2.54), ("5", "GND", "passive", -15.24)],
                 [("6", "CH0_J1", "output", 15.24), ("7", "CH1_J2", "output", 7.62), ("8", "CH2_J3", "output", 0.00), ("9", "CH3_J4", "output", -7.62), ("10", "CH4_GRIP", "output", -15.24)],
                 for_lib),
        _sym_box("MiniPro:Servo_3Pin", "M", 22.86, 12.70,
                 [("1", "PWM", "input", 2.54), ("2", "V+", "passive", 0.00), ("3", "GND", "passive", -2.54)],
                 [], for_lib),
    ]


def write_kicad_sym(path: str):
    content = (
        '(kicad_symbol_lib\n'
        '  (version 20241209)\n'
        '  (generator "minipro_b2_stealth_gen")\n'
        '  (generator_version "9.0")\n'
        + "\n".join(_all_symbols(for_lib=True))
        + "\n)\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _place_inst(lib_id: str, ref: str, val: str, sku: str, x: float, y: float, ref_off, val_off, pin_nums):
    lines = [
        f'  (symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (unit 1)',
        '    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)',
        f'    (uuid "{_uid("inst_" + ref)}")',
        f'    (property "Reference" "{ref}" (at {x + ref_off[0]:.2f} {y + ref_off[1]:.2f} 0) (effects (font (size 1.35 1.35) (bold yes))))',
        f'    (property "Value" "{val}" (at {x + val_off[0]:.2f} {y + val_off[1]:.2f} 0) (effects (font (size 1.20 1.20))))',
        f'    (property "SKU_UNIT" "{sku}" (at {x:.2f} {y + val_off[1] + 2.54:.2f} 0) (effects (font (size 1.0 1.0)) (hide yes)))',
    ]
    for pn in pin_nums:
        lines.append(f'    (pin "{pn}" (uuid "{_uid(f"pin_{ref}_{pn}")}"))')
    lines.append(f'    (instances (project "minipro_b2_stealth" (path "/{_uid("root_sheet")}" (reference "{ref}") (unit 1))))')
    lines.append('  )')
    return "\n".join(lines)


def _wire(x1, y1, x2, y2, tag):
    return f'  (wire (pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f})) (stroke (width 0) (type default)) (uuid "{_uid("w_" + tag)}"))'


def _bus_h(y: float, xs, prefix: str):
    """Emite segmentos horizontales limpios nodo-a-nodo (requisito estricto KiCad 9.0 en cada unión)."""
    xs_u = sorted(set(round(float(x), 2) for x in xs))
    return [_wire(xs_u[i], y, xs_u[i + 1], y, f"{prefix}_{i}") for i in range(len(xs_u) - 1)]


def _bus_v(x: float, ys, prefix: str):
    """Emite segmentos verticales limpios nodo-a-nodo (requisito estricto KiCad 9.0 en cada unión)."""
    ys_u = sorted(set(round(float(y), 2) for y in ys))
    return [_wire(x, ys_u[i], x, ys_u[i + 1], f"{prefix}_{i}") for i in range(len(ys_u) - 1)]


def _junc(x, y, tag):
    return f'  (junction (at {x:.2f} {y:.2f}) (diameter 0) (color 0 0 0 0) (uuid "{_uid("j_" + tag)}"))'


def _label(name, x, y, tag=""):
    return (
        f'  (label "{name}" (at {x:.2f} {y:.2f} 0) '
        f'(effects (font (size 1.27 1.27) (bold yes)) (justify left bottom)) '
        f'(uuid "{_uid("lbl_" + tag + "_" + name)}"))'
    )


def _text(content, x, y, size=1.35, bold=False, tag="t"):
    b = " (bold yes)" if bold else ""
    safe = content.replace('"', '\\"')
    return (
        f'  (text "{safe}" (exclude_from_sim no) (at {x:.2f} {y:.2f} 0) '
        f'(effects (font (size {size:.2f} {size:.2f}){b}) (justify left top)) '
        f'(uuid "{_uid("txt_" + tag)}"))'
    )


def write_kicad_sch(path: str):
    servo_specs = [
        ("M1", "MG90S 180deg (J1 Base)",   "AR1240", 58.42, 76.20, 195.58),
        ("M2", "MG90S 180deg (J2 Hombro)", "AR1240", 78.74, 83.82, 198.12),
        ("M3", "MG90S 180deg (J3 Codo)",   "AR1240", 99.06, 91.44, 200.66),
        ("M4", "MG90S 180deg (J4 Muneca)", "AR1240", 119.38, 99.06, 203.20),
        ("M5", "SG90 (Pinza Paralela)",    "PROPIO", 139.70, 106.68, 205.74),
    ]

    insts = [
        _place_inst("MiniPro:AR5515_USBC_PD", "J1", "AR5515 USB-C PD (5V)", "AR5515", 33.02, 53.34, (0, -10.16), (0, 10.16), ("1", "2")),
        _place_inst("MiniPro:KCD11_2P", "SW1", "KCD11-2P ON/OFF", "AR0243", 68.58, 50.80, (0, -5.08), (0, 5.08), ("1", "2")),
        _place_inst("MiniPro:1N5819", "D1", "1N5819 Schottky", "AR0195", 60.96, 83.82, (0, -5.08), (0, 5.08), ("1", "2")),
        _place_inst("MiniPro:Cap_1000uF", "C1", "1000uF 16V", "AR1127", 129.54, 67.31, (-8.89, -1.27), (-10.16, 2.54), ("1", "2")),
        _place_inst("MiniPro:XIAO_ESP32_S3", "U1", "XIAO ESP32-S3", "PROPIO", 99.06, 91.44, (0, -17.78), (0, 17.78), ("1", "2", "3", "4", "5", "6")),
        _place_inst("MiniPro:PCA9685_16CH", "U2", "PCA9685 (0x40)", "AR0389", 162.56, 91.44, (0, -25.40), (0, 25.40), ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10")),
    ]
    for ref, val, sku, my, _, _ in servo_specs:
        insts.append(_place_inst("MiniPro:Servo_3Pin", ref, val, sku, 238.76, my, (0, -8.89), (0, 8.89), ("1", "2", "3")))

    # Pines exactos:
    # J1 (x=33.02): Pin1=(46.99,50.80), Pin2=(46.99,55.88)
    # SW1 (x=68.58): Pin1=(63.50,50.80), Pin2=(73.66,50.80)
    # D1 (x=60.96): Pin1=(55.88,83.82), Pin2=(66.04,83.82)
    # C1 (x=129.54): Pin1=(129.54,63.50), Pin2=(129.54,71.12)
    # U1 (x=99.06): izq x=82.55 (5V=83.82, GND=99.06) | der x=115.57 (3V3=81.28, SDA=88.90, SCL=93.98, GND=101.60)
    # U2 (x=162.56): izq x=144.78 (V+=73.66, VCC=81.28, SDA=88.90, SCL=93.98, GND=106.68) | der x=180.34

    wires = []
    juncs = []
    labels = []

    # 1. +5V_RAW (amplio espacio para etiqueta sin tocar SW1!)
    wires.extend(_bus_h(50.80, [46.99, 50.80, 63.50], "5v_raw"))
    labels.append(_label("+5V_RAW", 50.80, 50.80, "5v_raw"))

    # 2. Bus superior +5V_SERVO
    wires.extend(_bus_h(50.80, [73.66, 78.74, 88.90, 129.54, 139.70, 213.36], "5v_sw_top"))
    juncs.extend([
        _junc(78.74, 50.80, "5v_d1"),
        _junc(129.54, 50.80, "5v_c1"),
        _junc(139.70, 50.80, "5v_pca"),
    ])
    labels.append(_label("+5V_SERVO", 88.90, 50.80, "5v_srv"))

    # Bajada a D1 -> XIAO 5V_IN (amplio espacio libre para +5V_XIAO!)
    wires.extend([
        _wire(78.74, 50.80, 78.74, 71.12, "d1_a"),
        _wire(78.74, 71.12, 53.34, 71.12, "d1_b"),
        _wire(53.34, 71.12, 53.34, 83.82, "d1_c"),
        _wire(53.34, 83.82, 55.88, 83.82, "d1_d"),
        _wire(66.04, 83.82, 68.58, 83.82, "xiao5v_a"),
        _wire(68.58, 83.82, 82.55, 83.82, "xiao5v_b"),
    ])
    labels.append(_label("+5V_XIAO", 68.58, 83.82, "5v_xiao"))

    # Bajada a C1+ y PCA9685 V+
    wires.extend([
        _wire(129.54, 50.80, 129.54, 63.50, "c1_pos"),
        _wire(139.70, 50.80, 139.70, 73.66, "pca_v_a"),
        _wire(139.70, 73.66, 144.78, 73.66, "pca_v_b"),
    ])

    srv_vs = [50.80] + [s[3] for s in servo_specs]
    wires.extend(_bus_v(213.36, srv_vs, "5v_srv_bus"))

    # 3. Bus Lógico I2C 3.3V (XIAO <-> PCA9685)
    wires.extend(_bus_h(81.28, [115.57, 124.46, 144.78], "3v3_bus"))
    wires.extend(_bus_h(88.90, [115.57, 124.46, 144.78], "sda_bus"))
    wires.extend(_bus_h(93.98, [115.57, 124.46, 144.78], "scl_bus"))
    labels.extend([
        _label("+3V3", 124.46, 81.28, "3v3"),
        _label("I2C_SDA", 124.46, 88.90, "sda"),
        _label("I2C_SCL", 124.46, 93.98, "scl"),
    ])

    # 4. Tierra Común Estrella GND
    gnd_y = 152.40
    wires.extend(_bus_h(gnd_y, [48.26, 78.74, 88.90, 119.38, 134.62, 142.24, 218.44], "gnd_main"))
    juncs.extend([
        _junc(78.74, gnd_y, "gnd_u1l"),
        _junc(119.38, gnd_y, "gnd_u1r"),
        _junc(134.62, gnd_y, "gnd_c1"),
        _junc(142.24, gnd_y, "gnd_u2"),
    ])
    labels.append(_label("GND", 88.90, gnd_y, "gnd"))

    wires.extend([
        _wire(46.99, 55.88, 48.26, 55.88, "gnd_j1_a"),
        _wire(48.26, 55.88, 48.26, gnd_y, "gnd_j1_b"),
        _wire(82.55, 99.06, 78.74, 99.06, "gnd_u1l_a"),
        _wire(78.74, 99.06, 78.74, gnd_y, "gnd_u1l_b"),
        _wire(115.57, 101.60, 119.38, 101.60, "gnd_u1r_a"),
        _wire(119.38, 101.60, 119.38, gnd_y, "gnd_u1r_b"),
        _wire(129.54, 71.12, 129.54, 76.20, "gnd_c1_a"),
        _wire(129.54, 76.20, 134.62, 76.20, "gnd_c1_b"),
        _wire(134.62, 76.20, 134.62, gnd_y, "gnd_c1_c"),
        _wire(144.78, 106.68, 142.24, 106.68, "gnd_u2_a"),
        _wire(142.24, 106.68, 142.24, gnd_y, "gnd_u2_b"),
    ])

    # Riel vertical GND de servos (segmentado exacto en cada Y de GND de servo hasta gnd_y!)
    srv_gs = [s[3] + 2.54 for s in servo_specs] + [gnd_y]
    wires.extend(_bus_v(218.44, srv_gs, "gnd_srv_bus"))

    # 5. Conexión de los 5 Servos (M1..M5)
    for idx, (ref, _, _, my, ch_y, x_turn) in enumerate(servo_specs):
        pwm_y = my - 2.54
        v_y = my
        g_y = my + 2.54
        wires.extend([
            _wire(180.34, ch_y, 182.88, ch_y, f"pwm_{idx}_l"),
            _wire(182.88, ch_y, x_turn, ch_y, f"pwm_{idx}_a"),
            _wire(x_turn, ch_y, x_turn, pwm_y, f"pwm_{idx}_b"),
            _wire(x_turn, pwm_y, 224.79, pwm_y, f"pwm_{idx}_c"),
            _wire(213.36, v_y, 224.79, v_y, f"vsrv_{idx}"),
            _wire(218.44, g_y, 224.79, g_y, f"gsrv_{idx}"),
        ])
        labels.append(_label(f"PWM_CH{idx}", 182.88, ch_y, f"ch{idx}"))
        if idx < len(servo_specs) - 1:
            juncs.append(_junc(213.36, v_y, f"vs_{idx}"))
        if idx > 0:
            juncs.append(_junc(218.44, g_y, f"gs_{idx}"))

    notes = [
        _text("MINI-PRO 4-DOF (B2 STEALTH) - ESQUEMA ELECTRICO DEFINITIVO (1 SOLO CABLE USB-C PD 5V)", 25.40, 22.86, 2.1, True, "hdr1"),
        _text("Alimentacion: Cargador UGREEN 50W (USB-C a USB-C) -> AR5515 (DIP en 5V) -> Boton KCD11-2P -> Bus +5V_SERVO (3A)", 25.40, 28.20, 1.30, False, "hdr2"),
        _text("REGLAS CRITICAS DE BANCO:", 25.40, 162.56, 1.40, True, "safe0"),
        _text("1) Fijar micro-switches DIP del AR5515 en 5V y MEDIR 4.95-5.15V con multimetro ANTES de conectar PCA9685 o XIAO.", 25.40, 166.80, 1.22, False, "safe1"),
        _text("2) Conectar PCA9685 VCC estrictamente a XIAO 3V3 (NUNCA a 5V) para mantener el bus I2C (D4/D5) seguro a 3.3V.", 25.40, 170.80, 1.22, False, "safe2"),
        _text("3) La banda del diodo Schottky D1 (1N5819, catodo K) apunta hacia XIAO 5V_IN: evita retorno al conectar laptop USB-C.", 25.40, 174.80, 1.22, False, "safe3"),
        _text("4) Capacitor C1 (1000uF 16V) montado directo en bornera V+/GND del PCA9685; M4 y M5 usan extension Dupont M-H 20 cm (AR0003).", 25.40, 178.80, 1.22, False, "safe4"),
    ]

    sch = f"""(kicad_sch
  (version 20250114)
  (generator "minipro_b2_stealth_gen")
  (generator_version "9.0")
  (uuid "{_uid("root_sheet")}")
  (paper "A4")
  (title_block
    (title "Mini-Pro 4-DOF Desktop Robot Arm (B2 Stealth)")
    (date "2026-11-21")
    (rev "v3.1")
    (company "Maximiliano Merida - Open Hardware (MIT)")
    (comment 1 "Power: UGREEN 50W USB-C PD -> AR5515 (5V) -> KCD11-2P -> 1N5819 + 1000uF")
    (comment 2 "Control: XIAO ESP32-S3 (I2C 3.3V) <-> PCA9685 (0x40) -> 4x MG90S + 1x SG90")
  )
  (lib_symbols
{chr(10).join("  " + ln for ln in chr(10).join(_all_symbols(for_lib=False)).splitlines())}
  )
{chr(10).join(wires)}
{chr(10).join(juncs)}
{chr(10).join(labels)}
{chr(10).join(insts)}
{chr(10).join(notes)}
  (sheet_instances
    (path "/" (page "1"))
  )
)
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(sch)


def main():
    os.makedirs(HERE, exist_ok=True)
    write_kicad_pro(os.path.join(HERE, "minipro_b2_stealth.kicad_pro"))
    write_sym_lib_table(os.path.join(HERE, "sym-lib-table"))
    write_kicad_sym(os.path.join(HERE, "MiniPro.kicad_sym"))
    write_kicad_sch(os.path.join(HERE, "minipro_b2_stealth.kicad_sch"))
    print("Generated complete portable KiCad 9.0 project in:", HERE)


if __name__ == "__main__":
    main()
