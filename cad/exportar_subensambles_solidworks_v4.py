"""
Exportador de Subensambles Locales para SolidWorks 2025 (Ensamble Articulado con Mates Reales)
==============================================================================================
Exporta los 11 cuerpos rígidos cinemáticos del `CAD v4 Clean-DFA` (`B2 Stealth`) en sus
marcos locales exactos (`Origen = pivote articular`) como archivos `.STEP` multi-cuerpo
coloreados (conservando PLA Negro Mate, PLA Blanco Mate, servos azules, PCBs verdes y acero),
junto con un manifiesto JSON de poses iniciales (Pose Héroe) y ejes de referencia para que
el script de automatización SolidWorks 2025 (`cad/construir_ensamble_solidworks_v4.ps1`)
arme el `.SLDASM` nativo con relaciones de posición (Mates) mecánicas, límites articulares,
acoplamiento simétrico de pinza 4 barras y detección de interferencias real.
"""

import json
import math
import os
import sys
import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from params import (
    D1_BASE_TO_SHOULDER,
    A2_LOWER_ARM,
    A3_FOREARM,
    GRIP_V4,
    HERO_POSE_DEG,
    gripper_kinematics_v4,
)
from mini_pro_b2_stealth_v4 import build_cad_v4

OUT_DIR = os.path.join(HERE, "exports", "v4_clean_dfa", "solidworks")
STEP_DIR = os.path.join(OUT_DIR, "step_subensambles")


def _inv_place_xz(shape: cq.Workplane, origin_xz, angle_deg: float) -> cq.Workplane:
    """Inversa exacta de `_place_xz`: lleva una pieza en pose mundo a su marco local en (0, 0, 0)."""
    ox, oz = origin_xz
    return shape.translate((-ox, 0.0, -oz)).rotate((0, 0, 0), (0, 1, 0), +angle_deg)


def main():
    os.makedirs(STEP_DIR, exist_ok=True)

    # Construir en Pose Neutro/Héroe limpia: q1=0, q2=0, q3=0, q4=0, g=0 (θ=0°)
    # Así cada subensamble queda alineado al milímetro con sus ejes locales (+X = largo eslabón, Z = vertical)!
    pose_zero = {"q1": 0.0, "q2": 0.0, "q3": 0.0, "q4": 0.0, "gripper_open_mm": 0.0}
    parts = build_cad_v4(pose_zero, explode=0.0)

    gx = float(GRIP_V4["gear_x"])     # 27.5
    gy = float(GRIP_V4["gear_y"])     # 9.20
    ix = float(GRIP_V4["idler_x"])    # 21.0
    iy = float(GRIP_V4["idler_y"])    # 16.90
    link_l = float(GRIP_V4["link_l"]) # 16.5

    p2 = (0.0, D1_BASE_TO_SHOULDER)                   # (0, 82)
    p3 = (A2_LOWER_ARM, D1_BASE_TO_SHOULDER)          # (82, 82)
    p4 = (A2_LOWER_ARM + A3_FOREARM, D1_BASE_TO_SHOULDER)  # (152, 82)

    # Colores oficiales B2 Stealth + Hardware
    C_BLK = cq.Color(0.11, 0.11, 0.13, 1.0)
    C_WHT = cq.Color(0.95, 0.95, 0.96, 1.0)
    C_SRV = cq.Color(0.12, 0.44, 0.84, 1.0)
    C_PCB = cq.Color(0.08, 0.56, 0.28, 1.0)
    C_STL = cq.Color(0.72, 0.74, 0.78, 1.0)

    blk = parts["black_named"]
    wht = parts["white_named"]
    srvs = parts["servos"]     # 0=J1, 1=J2, 2=J3, 3=J4, 4=SG90
    elec = parts["elec_pcb"]   # 0..4 in base
    stl  = parts["steel"]      # 0..4 in base, 5..6 fingerL, 7..8 fingerR, 9..11 palm

    # Helper para agregar a un Assembly ya transformado a marco local
    def save_sub(name: str, items):
        assy = cq.Assembly(name=name)
        for nm, shp, col in items:
            assy.add(shp, name=nm, color=col)
        fpath = os.path.join(STEP_DIR, f"{name}.step")
        assy.save(fpath)
        print(f"  [OK] {name}.step ({len(items)} cuerpos)")
        return fpath

    # 1. Base Fija (Origen = 0,0,0; Eje J1 = Z)
    base_items = [
        ("01_base_fija_v4", blk["01_base_fija_v4"], C_BLK),
        ("03_tapa_inferior_v4", blk["03_tapa_inferior_v4"], C_BLK),
        ("w01_aro_base_blanco", wht["w01_aro_base_blanco"], C_WHT),
        ("hw_mg90s_j1", srvs[0], C_SRV),
    ]
    for i, e in enumerate(elec):
        base_items.append((f"hw_elec_{i:02d}", e, C_PCB))
    for i in range(5):
        base_items.append((f"hw_base_steel_{i:02d}", stl[i], C_STL))
    save_sub("01_Base_Fija", base_items)

    # 2. Torreta J1 + Hub J2 (Origen = 0,0,0; Eje J1 = Z; Eje J2 = Y en (0, 0, 82))
    save_sub("02_Torreta_J1", [
        ("04_torreta_j1_hombro_v4", blk["04_torreta_j1_hombro_v4"], C_BLK),
        ("04b_reten_axial_j1", blk["04b_reten_axial_j1"], C_BLK),
        ("hw_mg90s_j2", srvs[1], C_SRV),
    ])

    # 3. Brazo L2 (Origen = J2 (0,0,0); Eje Prox = Y en (0,0); Eje Dist = Y en (82,0))
    def to_j2(s): return _inv_place_xz(s, p2, 0.0)
    save_sub("03_Brazo_L2", [
        ("05_eslabon_l2_v4", to_j2(blk["05_eslabon_l2_v4"]), C_BLK),
        ("13_tapa_cable_l2", to_j2(blk["13_tapa_cable_l2"]), C_BLK),
        ("11_separador_m3_j2", to_j2(blk["11_separador_m3_j2"]), C_BLK),
        ("tapa_j2_izq", to_j2(blk["tapa_j2_izq"]), C_BLK),
        ("tapa_j2_der", to_j2(blk["tapa_j2_der"]), C_BLK),
        ("w_aro_j2_izq", to_j2(wht["w_aro_j2_izq"]), C_WHT),
        ("w_aro_j2_der", to_j2(wht["w_aro_j2_der"]), C_WHT),
        ("hw_mg90s_j3", to_j2(srvs[2]), C_SRV),
    ])

    # 4. Antebrazo L3 (Origen = J3 (0,0,0); Eje Prox = Y en (0,0); Eje Dist = Y en (70,0))
    def to_j3(s): return _inv_place_xz(s, p3, 0.0)
    save_sub("04_Antebrazo_L3", [
        ("06_antebrazo_l3_v4", to_j3(blk["06_antebrazo_l3_v4"]), C_BLK),
        ("13_tapa_cable_l3", to_j3(blk["13_tapa_cable_l3"]), C_BLK),
        ("11_separador_m3_j3", to_j3(blk["11_separador_m3_j3"]), C_BLK),
        ("tapa_j3_izq", to_j3(blk["tapa_j3_izq"]), C_BLK),
        ("tapa_j3_der", to_j3(blk["tapa_j3_der"]), C_BLK),
        ("w_aro_j3_izq", to_j3(wht["w_aro_j3_izq"]), C_WHT),
        ("w_aro_j3_der", to_j3(wht["w_aro_j3_der"]), C_WHT),
        ("hw_mg90s_j4", to_j3(srvs[3]), C_SRV),
    ])

    # 5. Palma Muñeca J4 (Origen = J4 (0,0,0); ejes pinza Z en (gx, ±gy) e (ix, ±iy))
    def to_j4(s): return _inv_place_xz(s, p4, 0.0)
    save_sub("05_Palma_Muneca", [
        ("07_palma_pinza_v4", to_j4(blk["07_palma_pinza_v4"]), C_BLK),
        ("11_separador_m3_j4", to_j4(blk["11_separador_m3_j4"]), C_BLK),
        ("tapa_j4_izq", to_j4(blk["tapa_j4_izq"]), C_BLK),
        ("tapa_j4_der", to_j4(blk["tapa_j4_der"]), C_BLK),
        ("w_aro_j4_izq", to_j4(wht["w_aro_j4_izq"]), C_WHT),
        ("w_aro_j4_der", to_j4(wht["w_aro_j4_der"]), C_WHT),
        ("w02_collar_muneca_blanco", to_j4(wht["w02_collar_muneca_blanco"]), C_WHT),
        ("hw_sg90_pinza", to_j4(srvs[4]), C_SRV),
        ("hw_pin_palm_0", to_j4(stl[9]), C_STL),
        ("hw_pin_palm_1", to_j4(stl[10]), C_STL),
        ("hw_pin_palm_2", to_j4(stl[11]), C_STL),
    ])

    # 6 y 7. Engranes-brazo 12T Mod 1.5 (Origen = centro engrane (0,0,0); punta brazo en (link_l, 0, 0))
    save_sub("06_Engrane_Brazo_Izq", [
        ("08_engrane_brazo_izq_m15", to_j4(blk["08_engrane_brazo_izq_m15"]).translate((-gx, -gy, 0.0)), C_BLK),
    ])
    save_sub("07_Engrane_Brazo_Der", [
        ("09_engrane_brazo_der_m15", to_j4(blk["09_engrane_brazo_der_m15"]).translate((-gx, +gy, 0.0)), C_BLK),
    ])

    # 8 y 9. Bielas paralelas traseras (Origen = pivote palma (0,0,0); punta dedo en (link_l, 0, 0))
    save_sub("08_Biela_Izq", [
        ("12_biela_pinza_izq_v4", to_j4(blk["12_biela_pinza_izq_v4"]).translate((-ix, -iy, 0.0)), C_BLK),
    ])
    save_sub("09_Biela_Der", [
        ("12_biela_pinza_der_v4", to_j4(blk["12_biela_pinza_der_v4"]).translate((-ix, +iy, 0.0)), C_BLK),
    ])

    # 10 y 11. Dedos paralelos + Almohadillas blancas (Origen = pivote delantero (gx+link_l, ±gy, 0)!)
    # Así en marco local del dedo:
    #   - Pivote delantero = (0, 0, 0)
    #   - Pivote trasero   = (ix - gx, side*(iy - gy), 0) = (-6.5, ±7.7, 0)
    #   - Cara interna almohadilla w04 = Y = -side * gy (en contacto cuando ambos están en g=0!)
    save_sub("10_Dedo_Izq", [
        ("10_dedo_pinza_izq_v4", to_j4(blk["10_dedo_pinza_izq_v4"]).translate((-(gx + link_l), -gy, 0.0)), C_BLK),
        ("w04_almohadilla_izq", to_j4(wht["w04_almohadilla_izq"]).translate((-(gx + link_l), -gy, 0.0)), C_WHT),
        ("hw_pin_finger_l0", to_j4(stl[5]).translate((-(gx + link_l), -gy, 0.0)), C_STL),
        ("hw_pin_finger_l1", to_j4(stl[6]).translate((-(gx + link_l), -gy, 0.0)), C_STL),
    ])
    save_sub("11_Dedo_Der", [
        ("10_dedo_pinza_der_v4", to_j4(blk["10_dedo_pinza_der_v4"]).translate((-(gx + link_l), +gy, 0.0)), C_BLK),
        ("w04_almohadilla_der", to_j4(wht["w04_almohadilla_der"]).translate((-(gx + link_l), +gy, 0.0)), C_WHT),
        ("hw_pin_finger_r0", to_j4(stl[7]).translate((-(gx + link_l), +gy, 0.0)), C_STL),
        ("hw_pin_finger_r1", to_j4(stl[8]).translate((-(gx + link_l), +gy, 0.0)), C_STL),
    ])

    # Guardar manifiesto exacto en metros (unidad interna API SolidWorks!) para automatización
    th_hero, _, _, _ = gripper_kinematics_v4(HERO_POSE_DEG["gripper_open_mm"])
    manifest = {
        "d1_m": D1_BASE_TO_SHOULDER / 1000.0,
        "a2_m": A2_LOWER_ARM / 1000.0,
        "a3_m": A3_FOREARM / 1000.0,
        "gx_m": gx / 1000.0,
        "gy_m": gy / 1000.0,
        "ix_m": ix / 1000.0,
        "iy_m": iy / 1000.0,
        "link_l_m": link_l / 1000.0,
        "hero_q1_deg": HERO_POSE_DEG["q1"],
        "hero_q2_deg": HERO_POSE_DEG["q2"],
        "hero_q3_deg": HERO_POSE_DEG["q3"],
        "hero_q4_deg": HERO_POSE_DEG["q4"],
        "hero_grip_theta_deg": th_hero,
    }
    with open(os.path.join(OUT_DIR, "manifest_sw_v4.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[EXITO] 11 subensambles locales STEP listos en: {STEP_DIR}")


if __name__ == "__main__":
    main()
