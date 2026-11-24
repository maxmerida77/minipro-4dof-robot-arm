"""
Visor 3D Interactivo de Piezas, Electrónica y Ensamble — Mini-Pro 4-DOF (`B2 Stealth` v4 Clean-DFA)
====================================================================================================
Abre una ventana 3D interactiva (VTK) con las 34 piezas `.STL` imprimibles de `CAD v4 Clean-DFA`
(100% sólido único conectado, 0.00 mm³ colisiones) + los 22 componentes reales internos (servos
MG90S/SG90, PCA9685 + envolvente Dupont, XIAO, AR5515, botón KCD11-2P con terminales, capacitor
1000 µF y pernos M3):

    python cad/visor_cad_interactivo.py

Controles dentro de la ventana 3D:
    Mouse izquierdo     : Rotar 360°
    Rueda del mouse     : Zoom
    Shift + Izquierdo   : Mover (Pan)
    Clic derecho        : Seleccionar / identificar cualquier pieza directamente en 3D
    [E]                 : Alternar Ensamblado <-> Vista Explosionada
    [X]                 : Alternar Sólido <-> Rayos-X (ver servos, conectores y bolsillos internos)
    [H]                 : Mostrar / ocultar Electrónica, Servos y Tornillería interna
    [→] / [←] o [N]/[P] : Recorrer las 34 piezas imprimibles una por una
    [I]                 : Alternar fantasma ON/OFF al aislar una pieza o subensamble
    [1]..[5]            : Filtrar por subensamble (1=Base, 2=Hombro, 3=Codo, 4=Muñeca, 5=Pinza)
    [K] / [W]           : Ver solo Negro Mate (24 pzas) / solo Blanco Mate (10 pzas)
    [A]                 : Mostrar ensamble completo (todas las piezas)
    [R]                 : Recentrar cámara
    [Esc]               : Cerrar visor
"""

import os
import vtk

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, "exports", "v4_clean_dfa")
BLK_DIR = os.path.join(EXP, "stl_negro_mate")
WHT_DIR = os.path.join(EXP, "stl_blanco_mate")
HW_DIR  = os.path.join(EXP, "hardware_ref")

# Metadatos por pieza imprimible v4 Clean-DFA: (subensamble 1..5, descripción, vector explosión [dx, dy, dz] mm)
PART_META = {
    # 1 · Base Coaxial Ø106 mm + Retén Axial Independiente + Bóveda Lastre + Bandeja Aislante
    "01_base_fija_v4.stl": (1, "Base fija coaxial Ø106 mm (v4): MG90S J1 centrado, pista anular Ø88 mm, 4 tuercas M3 cautivas, AR5515 + KCD11.", (0, 0, 0)),
    "03_tapa_inferior_v4.stl": (1, "Tapa inferior (v4): 6 patas perimetrales Ø10.6 mm + bóveda de lastre en herradura (~247-298 g acero).", (0, 0, -56)),
    "03b_bandeja_electronica_v4.stl": (1, "Bandeja electrónica aislante plana (v4): separa lastre metálico de PCA9685, XIAO y C1 1000 µF (0 soportes).", (0, 0, -34)),
    "04b_reten_axial_j1.stl": (1, "Retén axial independiente J1 (v4): 3× M3×8 al cuello de torreta bajo el techo; libera al horn de cargas axiales.", (0, 0, -16)),
    "w01_aro_base_blanco.stl": (1, "Aro estético blanco base Ø106 mm (0% purga AMS).", (0, 0, 26)),
    # 2 · Torreta J1 + Hombro J2 + Separador M3 + Bayonetas
    "04_torreta_j1_hombro_v4.stl": (2, "Torreta coaxial J1 + Hub J2 (v4): labio pista Ø88 mm, acceso superior Ø6 mm al horn J1, bolsillo M3 Nyloc en J2.", (0, 0, 48)),
    "11_separador_m3_j2.stl": (2, "Casquillo separador liso M3 J2 (v4): rosca M3 fuera del giro + luz axial 0.35 mm (Nyloc nunca frena la horquilla).", (0, -24, 48)),
    "tapa_j2_izq.stl": (2, "Tapa Stealth J2 izquierda de BAYONETA 32° (v4): 0 flexión PLA, cavidad interna para tornillo M3.", (0, -34, 48)),
    "tapa_j2_der.stl": (2, "Tapa Stealth J2 derecha de BAYONETA 32° (v4): acceso rápido al tornillo central del horn MG90S.", (0, 34, 48)),
    "w_aro_j2_izq.stl": (2, "Aro blanco incrustado B2 Stealth — J2 izquierda.", (0, -40, 48)),
    "w_aro_j2_der.stl": (2, "Aro blanco incrustado B2 Stealth — J2 derecha.", (0, 40, 48)),
    # 3 · Eslabón L2 Horquilla en U Monolítica + Codo J3
    "05_eslabon_l2_v4.stl": (3, "Eslabón L2 horquilla en U monolítica (v4, 1 sólido): acceso Ø5.2 mm horn J2, canal cola de milano + hub J3.", (16, 0, 74)),
    "13_tapa_cable_l2.stl": (3, "Tapa deslizable cola de milano L2 (v4): oculta el arnés de cables atrás sin clips frágiles.", (4, 0, 90)),
    "11_separador_m3_j3.stl": (3, "Casquillo separador liso M3 J3 (v4): pivote pasivo sin fricción de rosca.", (16, -24, 74)),
    "tapa_j3_izq.stl": (3, "Tapa Stealth J3 izquierda de BAYONETA 32° (v4).", (16, -34, 74)),
    "tapa_j3_der.stl": (3, "Tapa Stealth J3 derecha de BAYONETA 32° (v4).", (16, 34, 74)),
    "w_aro_j3_izq.stl": (3, "Aro blanco incrustado B2 Stealth — J3 izquierda.", (16, -40, 74)),
    "w_aro_j3_der.stl": (3, "Aro blanco incrustado B2 Stealth — J3 derecha.", (16, 40, 74)),
    # 4 · Antebrazo L3 Horquilla en U Monolítica + Muñeca J4
    "06_antebrazo_l3_v4.stl": (4, "Antebrazo L3 horquilla en U monolítica (v4, 1 sólido): despeje total hasta J3=-135°, canal cables + hub J4.", (50, 0, 62)),
    "13_tapa_cable_l3.stl": (4, "Tapa deslizable cola de milano L3 (v4): oculta el cableado de J4 y Pinza.", (50, 0, 78)),
    "11_separador_m3_j4.stl": (4, "Casquillo separador liso M3 J4 (v4): pivote pasivo de muñeca sin juego.", (50, -24, 62)),
    "tapa_j4_izq.stl": (4, "Tapa Stealth J4 izquierda de BAYONETA 32° (v4).", (50, -32, 62)),
    "tapa_j4_der.stl": (4, "Tapa Stealth J4 derecha de BAYONETA 32° (v4).", (50, 32, 62)),
    "w_aro_j4_izq.stl": (4, "Aro blanco incrustado B2 Stealth — J4 izquierda.", (50, -38, 62)),
    "w_aro_j4_der.stl": (4, "Aro blanco incrustado B2 Stealth — J4 derecha.", (50, 38, 62)),
    # 5 · Pinza Paralela Abierta MeArm Módulo 1.5 (Sector 12T · TCP = 53.00 mm @ g=15 mm)
    "07_palma_pinza_v4.stl": (5, "Palma abierta MeArm Mod 1.5 (v4): horquilla J4, carenado SG90 coaxial inferior, 0 puente superior cerrado.", (86, 0, 62)),
    "w02_collar_muneca_blanco.stl": (5, "Collar blanco de muñeca B2 Stealth (v4, 0% purga AMS).", (76, 0, 62)),
    "08_engrane_brazo_izq_m15.stl": (5, "Engrane-Brazo sector 12T mod 1.5 izq (v4): 1 sólido rígido con bolsillo horn SG90 + acceso Ø5 mm arriba.", (94, 12, 74)),
    "09_engrane_brazo_der_m15.stl": (5, "Engrane-Brazo sector 12T mod 1.5 der (v4): dientes conjugados 0.35 mm backlash FDM (L=16.5 mm).", (94, -12, 74)),
    "12_biela_pinza_izq_v4.stl": (5, "Biela paralela trasera izquierda (v4, L=16.5 mm): cierra paralelogramo exacto.", (90, 14, 82)),
    "12_biela_pinza_der_v4.stl": (5, "Biela paralela trasera derecha (v4, L=16.5 mm): garantiza caras paralelas 0–30 mm.", (90, -14, 82)),
    "10_dedo_pinza_izq_v4.stl": (5, "Dedo paralelo izq (v4): puente diagonal rígido + mordaza calibrada a TCP = 53.00 mm @ g=15 mm.", (116, 18, 62)),
    "10_dedo_pinza_der_v4.stl": (5, "Dedo paralelo der (v4): apertura paralela simétrica 0–30 mm sin cámara.", (116, -18, 62)),
    "11b_separador_pinza_engrane.stl": (5, "Casquillo liso M3 engrane pasivo derecho (Ø5.0×5.4 mm): giro libre bajo apriete Nyloc.", (94, -12, 70)),
    "11c_separador_pinza_biela_izq.stl": (5, "Casquillo liso con brida M3 biela izquierda sobre pilar palma (M3×10 arriba).", (90, 14, 88)),
    "11c_separador_pinza_biela_der.stl": (5, "Casquillo liso con brida M3 biela derecha sobre pilar palma (M3×10 arriba).", (90, -14, 88)),
    "11d_separador_pinza_dedo_f_izq.stl": (5, "Casquillo escalonado M3 pivote delantero dedo izq (M3×16 avellanado).", (116, 18, 72)),
    "11d_separador_pinza_dedo_f_der.stl": (5, "Casquillo escalonado M3 pivote delantero dedo der (M3×16 avellanado).", (116, -18, 72)),
    "11e_separador_pinza_dedo_r_izq.stl": (5, "Casquillo escalonado M3 pivote trasero dedo izq (M3×12).", (112, 22, 74)),
    "11e_separador_pinza_dedo_r_der.stl": (5, "Casquillo escalonado M3 pivote trasero dedo der (M3×12).", (112, -22, 74)),
    "w04_almohadilla_izq.stl": (5, "Almohadilla blanca dedo izquierdo (centro exacto en (53.00, 0, +5.80) mm a g=15 mm).", (120, 10, 62)),
    "w04_almohadilla_der.stl": (5, "Almohadilla blanca dedo derecho (centro exacto en (53.00, 0, +5.80) mm a g=15 mm).", (120, -10, 62)),
}

HW_META = {
    "hw_servo_00.stl": (1, (0.14, 0.44, 0.78), "Servo MG90S J1 Base Coaxial (AR1240)", (0, 0, -4)),
    "hw_servo_01.stl": (2, (0.14, 0.44, 0.78), "Servo MG90S J2 Hombro (AR1240 / compatible MG92B)", (0, 12, 48)),
    "hw_servo_02.stl": (3, (0.14, 0.44, 0.78), "Servo MG90S J3 Codo (AR1240)", (16, 12, 74)),
    "hw_servo_03.stl": (4, (0.14, 0.44, 0.78), "Servo MG90S J4 Muñeca (AR1240)", (50, 12, 62)),
    "hw_servo_04.stl": (5, (0.18, 0.56, 0.88), "Microservo SG90 Pinza MeArm Mod 1.5", (86, 0, 44)),
    "hw_elec_00.stl":  (1, (0.12, 0.56, 0.30), "Módulo USB-C PD AR5515 (fijado 5V)", (-22, 0, 0)),
    "hw_elec_01.stl":  (1, (0.10, 0.46, 0.24), "Bornera 5V del módulo AR5515", (-22, 0, 0)),
    "hw_elec_02.stl":  (1, (0.12, 0.56, 0.30), "Driver PWM 16-ch PCA9685 (AR0389, VCC a 3V3)", (0, 0, -52)),
    "hw_elec_03.stl":  (1, (0.10, 0.46, 0.28), "Seeed Studio XIAO ESP32-S3", (0, 0, -52)),
    "hw_elec_04.stl":  (1, (0.14, 0.34, 0.54), "Capacitor Electrolítico 1000 µF 16V (AR1127)", (0, 0, -52)),
    "hw_steel_00.stl": (1, (0.74, 0.76, 0.80), "Puerto USB-C AR5515", (-22, 0, 0)),
    "hw_steel_01.stl": (1, (0.28, 0.28, 0.32), "Interruptor KCD11-2P con terminales faston (19 mm)", (-22, 0, 0)),
    "hw_steel_02.stl": (1, (0.22, 0.22, 0.25), "Bisel trasero KCD11-2P", (-22, 0, 0)),
    "hw_steel_03.stl": (1, (0.58, 0.62, 0.70), "Envolvente conectores Dupont enchufados PCA9685 (23 mm)", (0, 0, -52)),
    "hw_steel_04.stl": (1, (0.76, 0.78, 0.82), "Puerto USB-C XIAO ESP32-S3", (0, 0, -52)),
}

SUBASSY_NAMES = {
    1: "1 · Base Coaxial Ø106 mm + Bóveda Lastre + Bandeja Aislante + Retén J1 (5 pzas)",
    2: "2 · Torreta J1 + Hub J2 (Mamparo Nyloc) + Separador M3 + Bayonetas (6 pzas)",
    3: "3 · Eslabón L2 en U Monolítico + Canal Dovetail + Codo J3 (7 pzas)",
    4: "4 · Antebrazo L3 en U Monolítico + Canal Dovetail + Muñeca J4 (7 pzas)",
    5: "5 · Pinza Paralela Abierta MeArm Mod 1.5 + 7 Casquillos M3 (17 pzas · TCP=53 mm)",
}


def _make_stl_actor(fpath: str, rgb):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(fpath)
    reader.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(reader.GetOutputPort())
    normals.SetFeatureAngle(35.0)
    normals.SplittingOn()
    normals.Update()

    bounds = reader.GetOutput().GetBounds()
    dims = (bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*rgb)
    prop.SetAmbient(0.24)
    prop.SetDiffuse(0.76)
    prop.SetSpecular(0.22)
    prop.SetSpecularPower(26.0)
    return actor, dims


def load_parts():
    items = []
    for folder, color_name, rgb in [
        (BLK_DIR, "Negro Mate", (0.17, 0.17, 0.19)),
        (WHT_DIR, "Blanco Mate", (0.96, 0.96, 0.95)),
    ]:
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".stl"):
                continue
            actor, dims = _make_stl_actor(os.path.join(folder, fname), rgb)
            sub_id, desc, exp_vec = PART_META.get(fname, (1, "Pieza CAD v4 Clean-DFA", (0, 0, 0)))
            items.append({
                "name": fname,
                "color_name": color_name,
                "rgb": rgb,
                "sub_id": sub_id,
                "desc": desc,
                "exp": exp_vec,
                "dims": dims,
                "actor": actor,
                "is_hw": False,
            })
    items.sort(key=lambda x: (x["sub_id"], x["name"]))
    return items


def load_hardware():
    hw = []
    if not os.path.isdir(HW_DIR):
        return hw
    for fname in sorted(os.listdir(HW_DIR)):
        if not fname.endswith(".stl"):
            continue
        default_sub = 5 if fname.startswith("hw_steel_") and int(fname.split("_")[-1].split(".")[0]) >= 5 else 1
        sub_id, rgb, desc, exp_vec = HW_META.get(fname, (default_sub, (0.74, 0.76, 0.80), "Perno pivote M3 pinza", (86, 0, 62)))
        actor, dims = _make_stl_actor(os.path.join(HW_DIR, fname), rgb)
        hw.append({
            "name": fname,
            "color_name": "Hardware",
            "rgb": rgb,
            "sub_id": sub_id,
            "desc": desc,
            "exp": exp_vec,
            "dims": dims,
            "actor": actor,
            "is_hw": True,
        })
    return hw


def _make_hud(ren, x_norm: float, y_norm: float, font_size: int, color, bold: bool = False):
    ta = vtk.vtkTextActor()
    tp = ta.GetTextProperty()
    tp.SetFontFamilyToArial()
    tp.SetFontSize(font_size)
    tp.SetBold(bold)
    tp.SetColor(*color)
    coord = ta.GetPositionCoordinate()
    coord.SetCoordinateSystemToNormalizedViewport()
    coord.SetValue(x_norm, y_norm)
    ren.AddActor2D(ta)
    return ta


class CadViewerApp:
    def __init__(self, offscreen: bool = False):
        self.items = load_parts()
        self.hw_items = load_hardware()
        self.actor_to_idx = {it["actor"]: i for i, it in enumerate(self.items)}
        self.actor_to_hw = {it["actor"]: it for it in self.hw_items}

        self.exploded = False
        self.xray = False
        self.show_hw = True
        self.ghost_others = True
        self.mode = "ALL"
        self.single_idx = 0
        self.sub_filter = 1
        self.color_filter = "Negro Mate"
        self.picked_hw_msg = ""

        self.ren = vtk.vtkRenderer()
        self.ren.SetBackground(0.93, 0.93, 0.92)
        self.ren.SetBackground2(0.84, 0.85, 0.87)
        self.ren.GradientBackgroundOn()

        for it in self.items:
            self.ren.AddActor(it["actor"])
        for it in self.hw_items:
            self.ren.AddActor(it["actor"])

        disk = vtk.vtkCylinderSource()
        disk.SetRadius(118.0)
        disk.SetHeight(1.2)
        disk.SetResolution(72)
        tf = vtk.vtkTransform()
        tf.RotateX(90.0)
        tf.Translate(30.0, 0.0, -0.7)
        tpf = vtk.vtkTransformPolyDataFilter()
        tpf.SetInputConnection(disk.GetOutputPort())
        tpf.SetTransform(tf)
        m_disk = vtk.vtkPolyDataMapper()
        m_disk.SetInputConnection(tpf.GetOutputPort())
        a_disk = vtk.vtkActor()
        a_disk.SetMapper(m_disk)
        a_disk.GetProperty().SetColor(0.86, 0.86, 0.84)
        a_disk.GetProperty().SetOpacity(0.55)
        a_disk.PickableOff()
        self.ren.AddActor(a_disk)

        self.ren.AutomaticLightCreationOff()
        for pos, inten in [((380, -340, 420), 0.92), ((-320, -240, 260), 0.48), ((0, 360, 220), 0.36)]:
            lt = vtk.vtkLight()
            lt.SetLightTypeToSceneLight()
            lt.SetPosition(*pos)
            lt.SetFocalPoint(40, 0, 95)
            lt.SetIntensity(inten)
            self.ren.AddLight(lt)

        self.hud_top  = _make_hud(self.ren, 0.018, 0.945, 17, (0.10, 0.10, 0.12), bold=True)
        self.hud_desc = _make_hud(self.ren, 0.018, 0.905, 14, (0.24, 0.24, 0.28), bold=False)
        self.hud_help = _make_hud(self.ren, 0.018, 0.022, 13, (0.30, 0.30, 0.35), bold=False)
        self.hud_help.SetInput(
            "[E] Explosionar  [X] Rayos-X  [H] Electrónica  [<-/->] Pieza a pieza  [Clic Der] Elegir pieza  "
            "[1..5] Subensambles  [K/W] Negro/Blanco  [A] Todo  [R] Centrar  [Esc] Salir"
        )

        self.win = vtk.vtkRenderWindow()
        if offscreen:
            self.win.SetOffScreenRendering(1)
        self.win.AddRenderer(self.ren)
        self.win.SetSize(1280, 760)
        self.win.SetWindowName("Visor CAD 3D Interactivo — Mini-Pro 4-DOF B2 Stealth v4 Clean-DFA (34 Piezas + Electrónica)")
        self.win.SetMultiSamples(4)

        self.iren = vtk.vtkRenderWindowInteractor()
        self.iren.SetRenderWindow(self.win)
        style = vtk.vtkInteractorStyleTrackballCamera()
        self.iren.SetInteractorStyle(style)

        self.iren.RemoveObservers("CharEvent")
        self.iren.AddObserver("KeyPressEvent", self.on_key)
        self.iren.AddObserver("RightButtonPressEvent", self.on_right_click)
        self.picker = vtk.vtkPropPicker()

        self.apply_state()
        self.reset_camera()

    def reset_camera(self):
        cam = self.ren.GetActiveCamera()
        if self.exploded:
            cam.SetFocalPoint(60.0, 0.0, 110.0)
            cam.SetPosition(355.0, -405.0, 270.0)
        else:
            cam.SetFocalPoint(48.0, 0.0, 95.0)
            cam.SetPosition(285.0, -315.0, 228.0)
        cam.SetViewUp(0.0, 0.0, 1.0)
        cam.SetViewAngle(32.0)
        self.ren.ResetCameraClippingRange()
        self.win.Render()

    def apply_state(self):
        for idx, it in enumerate(self.items):
            act = it["actor"]
            ex = it["exp"] if self.exploded else (0.0, 0.0, 0.0)
            act.SetPosition(*ex)

            is_active = True
            if self.mode == "SINGLE":
                is_active = (idx == self.single_idx)
            elif self.mode == "SUB":
                is_active = (it["sub_id"] == self.sub_filter)
            elif self.mode == "COLOR":
                is_active = (it["color_name"] == self.color_filter)

            prop = act.GetProperty()
            if is_active:
                act.SetVisibility(True)
                if self.mode == "SINGLE":
                    prop.SetColor(0.84, 0.33, 0.11) if it["color_name"] == "Negro Mate" else prop.SetColor(1.0, 1.0, 1.0)
                    prop.SetOpacity(1.0)
                else:
                    prop.SetColor(*it["rgb"])
                    prop.SetOpacity(0.32 if self.xray else 1.0)
            else:
                if self.ghost_others and self.mode in ("SINGLE", "SUB"):
                    act.SetVisibility(True)
                    prop.SetColor(0.62, 0.63, 0.66)
                    prop.SetOpacity(0.10)
                else:
                    act.SetVisibility(False)

        for it in self.hw_items:
            act = it["actor"]
            ex = it["exp"] if self.exploded else (0.0, 0.0, 0.0)
            act.SetPosition(*ex)

            vis = self.show_hw
            if self.mode == "COLOR":
                vis = False
            elif self.mode == "SUB":
                vis = self.show_hw and (it["sub_id"] == self.sub_filter)
            elif self.mode == "SINGLE":
                vis = self.show_hw and self.ghost_others and (it["sub_id"] == self.items[self.single_idx]["sub_id"])

            act.SetVisibility(vis)
            if vis:
                prop = act.GetProperty()
                prop.SetColor(*it["rgb"])
                prop.SetOpacity(0.55 if self.mode == "SINGLE" else 1.0)

        exp_tag = "EXPLOSIONADO" if self.exploded else "ENSAMBLADO"
        xr_tag = " · RAYOS-X" if self.xray else ""
        hw_tag = " · HW ON" if self.show_hw else " · HW OFF"

        if self.picked_hw_msg:
            self.hud_top.SetInput(f"COMPONENTE INTERNO SELECCIONADO · [{exp_tag}{xr_tag}]")
            self.hud_desc.SetInput(self.picked_hw_msg)
        elif self.mode == "ALL":
            self.hud_top.SetInput(f"MINI-PRO 4-DOF B2 STEALTH v4 Clean-DFA — ENSAMBLE COMPLETO ({len(self.items)} pzas) · [{exp_tag}{xr_tag}{hw_tag}]")
            self.hud_desc.SetInput("Usa [E] explosionar, [X] rayos-X para ver servos/PCBs/Dupont dentro, [H] hardware, o Clic Derecho sobre cualquier pieza.")
        elif self.mode == "SINGLE":
            it = self.items[self.single_idx]
            dx, dy, dz = it["dims"]
            self.hud_top.SetInput(
                f"PIEZA {self.single_idx + 1}/{len(self.items)}: {it['name']}  ({it['color_name']} · {dx:.1f}×{dy:.1f}×{dz:.1f} mm)"
            )
            self.hud_desc.SetInput(it["desc"])
        elif self.mode == "SUB":
            self.hud_top.SetInput(f"SUBENSAMBLE {SUBASSY_NAMES[self.sub_filter]} · [{exp_tag}{xr_tag}{hw_tag}]")
            self.hud_desc.SetInput("Usa [E] para separar piezas del subensamble, [X] para ver los bolsillos internos o [A] para volver a todo.")
        elif self.mode == "COLOR":
            cnt = sum(1 for x in self.items if x["color_name"] == self.color_filter)
            self.hud_top.SetInput(f"FILAMENTO PLA {self.color_filter.upper()} ({cnt} piezas) · [{exp_tag}]")
            self.hud_desc.SetInput("Piezas 100% separadas por color = 0% purga AMS en tu Bambu Lab A1 Combo.")

        self.win.Render()

    def on_right_click(self, obj, _evt):
        x, y = obj.GetEventPosition()
        self.picker.Pick(x, y, 0, self.ren)
        act = self.picker.GetActor()
        if act in self.actor_to_idx:
            self.picked_hw_msg = ""
            self.mode = "SINGLE"
            self.single_idx = self.actor_to_idx[act]
            self.apply_state()
        elif act in self.actor_to_hw:
            hw = self.actor_to_hw[act]
            dx, dy, dz = hw["dims"]
            self.picked_hw_msg = f"{hw['name']} ({dx:.1f}×{dy:.1f}×{dz:.1f} mm) — {hw['desc']}"
            self.apply_state()

    def on_key(self, obj, _evt):
        key = obj.GetKeySym() or ""
        low = key.lower()
        self.picked_hw_msg = ""
        if low == "escape":
            self.iren.TerminateApp()
            return
        elif low == "e":
            self.exploded = not self.exploded
            self.apply_state()
            self.reset_camera()
            return
        elif low == "x":
            self.xray = not self.xray
        elif low == "h":
            self.show_hw = not self.show_hw
        elif low == "i":
            self.ghost_others = not self.ghost_others
        elif low == "a":
            self.mode = "ALL"
        elif low in ("n", "right"):
            if self.mode != "SINGLE":
                self.mode = "SINGLE"
                self.single_idx = 0
            else:
                self.single_idx = (self.single_idx + 1) % len(self.items)
        elif low in ("p", "left"):
            if self.mode != "SINGLE":
                self.mode = "SINGLE"
                self.single_idx = len(self.items) - 1
            else:
                self.single_idx = (self.single_idx - 1) % len(self.items)
        elif low in ("1", "2", "3", "4", "5"):
            self.mode = "SUB"
            self.sub_filter = int(low)
        elif low == "k":
            self.mode = "COLOR"
            self.color_filter = "Negro Mate"
        elif low == "w":
            self.mode = "COLOR"
            self.color_filter = "Blanco Mate"
        elif low == "r":
            self.reset_camera()
            return
        else:
            return
        self.apply_state()

    def run(self):
        self.win.Render()
        self.iren.Initialize()
        self.iren.Start()


if __name__ == "__main__":
    app = CadViewerApp()
    app.run()
