"""
Kit de Calibración de Tolerancias (20 min · ~14 g PLA) — Bambu Lab A1 Combo
===========================================================================
Imprime este cupón compacto ANTES de imprimir el brazo completo para validar tus
ajustes reales con el carrito de UNIT Electronics:
  1. Bolsillo exacto para `MG90S` (`AR1240`) / tu `SG90` (23.2 × 12.6 mm)
  2. Asiento de presión para rodamiento `608ZZ-7` (`AR4602`, Ø 22.14 × 7.0 mm) + muñón eje Ø 7.86 mm
  3. Barrenos de prueba para inserto térmico `AR2811` (Ø 4.0, 4.1 y 4.2 mm — elige el más firme)
  4. Recorte snap-fit para el interruptor `KCD11-2P` (`AR0243`, 13.5 × 9.0 mm)
  5. Par de engranes `14T` de la pinza paralela sobre base de prueba (verifica giro sedoso)

Exporta: `cad/exports/tolerance_test_kit_bambu_a1.stl`
"""

import os
import cadquery as cq

from params import (
    MG90S,
    BEARING_608,
    SWITCH_KCD11,
    CLEARANCE_FIT,
    BEARING_FIT,
    INSERT_M3_DIA,
)
from mini_pro_b2_stealth_v2 import _spur_gear


def build_tolerance_kit():
    plate_l, plate_w, plate_h = 84.0, 44.0, 8.5
    base = (
        cq.Workplane("XY")
        .rect(plate_l, plate_w)
        .extrude(plate_h)
        .edges("|Z")
        .fillet(4.0)
        .edges(">Z or <Z")
        .chamfer(0.6)
    )

    # 1. Bolsillo pasante MG90S / SG90 (izquierda: X = -27, Y = 0)
    servo_cut = (
        cq.Workplane("XY")
        .workplane(offset=-0.5)
        .center(-27.0, 0.0)
        .rect(MG90S["body_w"] + CLEARANCE_FIT * 2, MG90S["body_l"] + CLEARANCE_FIT * 2)
        .extrude(plate_h + 1.0)
    )

    # 2. Asiento rodamiento 608ZZ (centro-izq: X = -2, Y = 4, profundidad 7.2 mm) + eje Ø 7.86 mm arriba
    brg_cut = (
        cq.Workplane("XY")
        .workplane(offset=plate_h - 7.2)
        .center(-2.0, 4.0)
        .circle((BEARING_608["od"] + BEARING_FIT) / 2.0)
        .extrude(8.0)
    )
    brg_thru = (
        cq.Workplane("XY")
        .workplane(offset=-0.5)
        .center(-2.0, 4.0)
        .circle(6.5)
        .extrude(plate_h + 1.0)
    )
    # Muñón Ø 7.86 mm saliendo hacia +Z para probar el ajuste interior del 608ZZ
    pin_boss = (
        cq.Workplane("XY")
        .workplane(offset=plate_h)
        .center(-2.0, -14.0)
        .circle((BEARING_608["id"] - BEARING_FIT) / 2.0)
        .extrude(7.5)
        .edges(">Z")
        .chamfer(0.5)
    )

    # 3. 3 barrenos graduados para inserto térmico `AR2811` (4.0, 4.1, 4.2 mm en X = +18, Y = -12, 0, +12)
    kit = base.union(pin_boss).cut(servo_cut).cut(brg_cut).cut(brg_thru)
    for dy, d_hole in [(-12.0, INSERT_M3_DIA - 0.1), (0.0, INSERT_M3_DIA), (12.0, INSERT_M3_DIA + 0.1)]:
        kit = kit.cut(
            cq.Workplane("XY").workplane(offset=plate_h - 4.5).center(17.5, dy).circle(d_hole / 2.0).extrude(5.5)
        )

    # 4. Recorte snap-fit para interruptor KCD11-2P (derecha: X = +32.5, Y = 0)
    sw_cut = (
        cq.Workplane("XY")
        .workplane(offset=-0.5)
        .center(32.5, 0.0)
        .rect(SWITCH_KCD11["cut_h"], SWITCH_KCD11["cut_w"])
        .extrude(plate_h + 1.0)
    )
    kit = kit.cut(sw_cut)

    # 5. Dos engranes 14T de prueba sueltos al frente del cupón (para probar engrane sin imprimir la pinza entera)
    g1 = _spur_gear(14, 1.0, 4.6, 2.0).translate((-12.0, -34.0, 0.0))
    g2 = _spur_gear(14, 1.0, 4.6, 2.0).translate((12.0, -34.0, 0.0))

    return kit.union(g1).union(g2)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out_stl = os.path.join(here, "exports", "tolerance_test_kit_bambu_a1.stl")
    os.makedirs(os.path.dirname(out_stl), exist_ok=True)
    kit = build_tolerance_kit()
    cq.exporters.export(kit, out_stl, tolerance=0.025, angularTolerance=0.07)
    print("Exported 20-min Tolerance Test Kit:", out_stl)
