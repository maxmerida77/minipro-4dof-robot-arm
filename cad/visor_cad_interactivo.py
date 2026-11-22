"""
Visor 3D Interactivo de Piezas, Electrónica y Ensamble — Mini-Pro 4-DOF (`B2 Stealth` v2)
=========================================================================================
Abre una ventana 3D interactiva (VTK) con las 30 piezas `.STL` imprimibles + los
componentes reales internos (servos MG90S/SG90, 4× rodamientos 608ZZ, PCA9685, XIAO,
AR5515, botón KCD11-2P y capacitor 1000 µF):

    python cad/visor_cad_interactivo.py

Controles dentro de la ventana 3D:
    Mouse izquierdo     : Rotar 360°
    Rueda del mouse     : Zoom
    Shift + Izquierdo   : Mover (Pan)
    Clic derecho        : Seleccionar / identificar cualquier pieza directamente en 3D
    [E]                 : Alternar Ensamblado <-> Vista Explosionada
    [X]                 : Alternar Sólido <-> Rayos-X (ver servos y bolsillos internos)
    [H]                 : Mostrar / ocultar Electrónica, Servos y Rodamientos internos
    [→] / [←] o [N]/[P] : Recorrer las 30 piezas imprimibles una por una
    [I]                 : Alternar fantasma ON/OFF al aislar una pieza o subensamble
    [1]..[5]            : Filtrar por subensamble (1=Base, 2=Hombro, 3=Codo, 4=Muñeca, 5=Pinza)
    [K] / [W]           : Ver solo Negro Mate (18 pzas) / solo Blanco Mate (12 pzas)
    [A]                 : Mostrar ensamble completo (todas las piezas)
    [R]                 : Recentrar cámara
    [Esc]               : Cerrar visor
"""

import os
import vtk

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, "exports")
BLK_DIR = os.path.join(EXP, "stl_negro_mate")
WHT_DIR = os.path.join(EXP, "stl_blanco_mate")
HW_DIR  = os.path.join(EXP, "hardware_ref")

# Metadatos por pieza imprimible: (subensamble 1..5, descripción de ensamble, vector de explosión [dx, dy, dz] mm)
PART_META = {
    "01_base_fija_hueca.stl": (1, "Base fija Ø94 mm: aloja rodamiento 608ZZ arriba, MG90S J1 interno y 3 puertos traseros (XIAO, AR5515, KCD11).", (0, 0, 0)),
    "02_pinon_base_22t.stl": (1, "Piñón motriz 22T: entra al eje del MG90S J1 y engrana 1:1 con 04b_engrane_torreta_22t.", (26, 0, -10)),
    "03_tapa_inferior_electronica.stl": (1, "Tapa inferior: sujeta PCA9685 en 4 postes y XIAO ESP32-S3 en su cuna; se cierra con 4× M3 en insertos AR2811.", (0, 0, -52)),
    "w01_aro_base_blanco.stl": (1, "Aro estético blanco base: separa visualmente la base fija de la torreta giratoria.", (0, 0, 26)),
    "04_torreta_j1_hombro.stl": (2, "Torreta giratoria J1 + tambor Hombro J2: su eje entra al 608ZZ central y arriba aloja MG90S J2 + 608ZZ.", (0, 0, 50)),
    "04b_engrane_torreta_22t.stl": (2, "Engrane conducido 22T (separado): entra por debajo del 608ZZ al eje de la torreta y se fija con tornillo M3×8.", (0, 0, -18)),
    "tapa_j2_izq.stl": (2, "Tapa lateral izquierda J2 (lado rodamiento 608ZZ).", (0, -30, 50)),
    "tapa_j2_der.stl": (2, "Tapa lateral derecha J2 (cubre cola del MG90S J2).", (0, 30, 50)),
    "w_aro_j2_izq.stl": (2, "Aro blanco incrustado B2 Stealth — J2 izquierda.", (0, -38, 50)),
    "w_aro_j2_der.stl": (2, "Aro blanco incrustado B2 Stealth — J2 derecha.", (0, 38, 50)),
    "05_eslabon_l2_codo.stl": (3, "Eslabón inferior L2 (a2=82 mm): viga octagonal hueca pasa-cables + tambor Codo J3 (MG90S J3 + 608ZZ).", (16, 0, 76)),
    "tapa_j3_izq.stl": (3, "Tapa lateral izquierda J3 (lado rodamiento 608ZZ).", (16, -30, 76)),
    "tapa_j3_der.stl": (3, "Tapa lateral derecha J3 (cubre MG90S J3).", (16, 30, 76)),
    "w_aro_j3_izq.stl": (3, "Aro blanco incrustado B2 Stealth — J3 izquierda.", (16, -38, 76)),
    "w_aro_j3_der.stl": (3, "Aro blanco incrustado B2 Stealth — J3 derecha.", (16, 38, 76)),
    "06_antebrazo_l3_muneca.stl": (4, "Antebrazo L3 (a3=70 mm): viga hueca pasa-cables + tambor Muñeca J4 (MG90S J4 + 608ZZ).", (52, 0, 62)),
    "tapa_j4_izq.stl": (4, "Tapa lateral izquierda J4 (lado rodamiento 608ZZ).", (52, -28, 62)),
    "tapa_j4_der.stl": (4, "Tapa lateral derecha J4 (cubre MG90S J4).", (52, 28, 62)),
    "w_aro_j4_izq.stl": (4, "Aro blanco incrustado B2 Stealth — J4 izquierda.", (52, -36, 62)),
    "w_aro_j4_der.stl": (4, "Aro blanco incrustado B2 Stealth — J4 derecha.", (52, 36, 62)),
    "07_palma_pinza_sg90.stl": (5, "Palma de pinza con carenado inferior biselado: oculta 100% tu SG90 y sostiene los 2 engranes 14T.", (88, 0, 62)),
    "w02_collar_muneca_blanco.stl": (5, "Collar blanco de muñeca: acento minimalista en la entrada de la pinza.", (78, 0, 62)),
    "08_engrane_pinza_izq.stl": (5, "Engrane 14T izquierdo de pinza (se acopla directo al eje/horn del SG90).", (96, 10, 76)),
    "09_engrane_pinza_der.stl": (5, "Engrane 14T derecho de pinza (engranado 1:1 en espejo con el izquierdo).", (96, -10, 76)),
    "w03_aro_engrane_0.stl": (5, "Aro blanco central de engrane derecho.", (96, -10, 84)),
    "w03_aro_engrane_1.stl": (5, "Aro blanco central de engrane izquierdo.", (96, 10, 84)),
    "10_dedo_pinza_izq.stl": (5, "Dedo paralelo izquierdo biselado (TCP a a4 = 53 mm desde J4).", (116, 16, 62)),
    "10_dedo_pinza_der.stl": (5, "Dedo paralelo derecho biselado (apertura total 0–30 mm).", (116, -16, 62)),
    "w04_almohadilla_izq.stl": (5, "Almohadilla blanca interior dedo izquierdo.", (120, 8, 62)),
    "w04_almohadilla_der.stl": (5, "Almohadilla blanca interior dedo derecho.", (120, -8, 62)),
}

# Metadatos para hardware interno (servos, PCBs, rodamientos): (subensamble, rgb, descripción, explosión)
HW_META = {
    "hw_mg90s_j1_base.stl":       (1, (0.14, 0.44, 0.78), "Servo MG90S J1 Base (UNIT AR1240)", (26, 0, -2)),
    "hw_rodamiento_608zz_base.stl":(1, (0.72, 0.74, 0.78), "Rodamiento 608ZZ Base (UNIT AR4602)", (0, 0, 14)),
    "hw_ar5515_usbc_pd_pcb.stl":  (1, (0.12, 0.56, 0.30), "Módulo USB-C PD AR5515 (5V UGREEN 50W)", (-22, 0, 0)),
    "hw_ar5515_bornera.stl":      (1, (0.10, 0.48, 0.24), "Bornera 5V del módulo AR5515", (-22, 0, 0)),
    "hw_ar5515_puerto_usbc.stl":  (1, (0.74, 0.76, 0.80), "Puerto USB-C de potencia AR5515", (-22, 0, 0)),
    "hw_switch_kcd11_cuerpo.stl": (1, (0.28, 0.28, 0.32), "Interruptor ON/OFF KCD11-2P (UNIT AR0243)", (-22, 0, 0)),
    "hw_switch_kcd11_bisel.stl":  (1, (0.22, 0.22, 0.25), "Bisel trasero KCD11-2P", (-22, 0, 0)),
    "hw_pca9685_pcb.stl":         (1, (0.12, 0.56, 0.30), "Driver PWM 16-ch PCA9685 (UNIT AR0389)", (0, 0, -52)),
    "hw_pca9685_pines.stl":       (1, (0.74, 0.76, 0.80), "Pines de servos PCA9685", (0, 0, -52)),
    "hw_xiao_esp32_pcb.stl":      (1, (0.10, 0.46, 0.28), "XIAO ESP32-S3 / C3", (0, 0, -52)),
    "hw_xiao_puerto_usbc.stl":    (1, (0.76, 0.78, 0.82), "Puerto USB-C XIAO ESP32-S3", (0, 0, -52)),
    "hw_capacitor_1000uf.stl":    (1, (0.14, 0.34, 0.54), "Capacitor 1000 µF 16V (UNIT AR1127)", (0, 0, -52)),
    "hw_mg90s_j2_hombro.stl":     (2, (0.14, 0.44, 0.78), "Servo MG90S J2 Hombro (UNIT AR1240)", (0, 12, 50)),
    "hw_rodamiento_608zz_j2.stl": (2, (0.72, 0.74, 0.78), "Rodamiento 608ZZ apoyo J2", (0, -14, 50)),
    "hw_mg90s_j3_codo.stl":       (3, (0.14, 0.44, 0.78), "Servo MG90S J3 Codo (UNIT AR1240)", (16, 12, 76)),
    "hw_rodamiento_608zz_j3.stl": (3, (0.72, 0.74, 0.78), "Rodamiento 608ZZ apoyo J3", (16, -14, 76)),
    "hw_mg90s_j4_muneca.stl":     (4, (0.14, 0.44, 0.78), "Servo MG90S J4 Muñeca (UNIT AR1240)", (52, 12, 62)),
    "hw_rodamiento_608zz_j4.stl": (4, (0.72, 0.74, 0.78), "Rodamiento 608ZZ apoyo J4", (52, -14, 62)),
    "hw_sg90_pinza.stl":          (5, (0.18, 0.54, 0.88), "Microservo SG90 en Pinza Paralela", (88, 0, 44)),
}

SUBASSY_NAMES = {
    1: "1 · Base Fija + Electrónica (4 pzas + PCBs/MG90S J1)",
    2: "2 · Torreta J1 + Engrane 22T + Hombro J2 (6 pzas)",
    3: "3 · Eslabón L2 + Codo J3 (5 pzas)",
    4: "4 · Antebrazo L3 + Muñeca J4 (5 pzas)",
    5: "5 · Pinza Paralela SG90 (10 pzas)",
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
            sub_id, desc, exp_vec = PART_META.get(fname, (1, "Pieza CAD B2 Stealth", (0, 0, 0)))
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
        sub_id, rgb, desc, exp_vec = HW_META.get(fname, (1, (0.5, 0.5, 0.5), "Hardware interno", (0, 0, 0)))
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
        self.mode = "ALL"        # ALL | SINGLE | SUB | COLOR
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

        # Plano de escritorio de referencia (Z = 0)
        disk = vtk.vtkCylinderSource()
        disk.SetRadius(112.0)
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

        # Iluminación de estudio 3 puntos
        self.ren.AutomaticLightCreationOff()
        for pos, inten in [((380, -340, 420), 0.92), ((-320, -240, 260), 0.48), ((0, 360, 220), 0.36)]:
            lt = vtk.vtkLight()
            lt.SetLightTypeToSceneLight()
            lt.SetPosition(*pos)
            lt.SetFocalPoint(40, 0, 95)
            lt.SetIntensity(inten)
            self.ren.AddLight(lt)

        # HUD adaptable a cualquier tamaño de ventana / DPI de Windows
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
        self.win.SetWindowName("Visor CAD 3D Interactivo — Mini-Pro 4-DOF B2 Stealth (30 Piezas + Electrónica)")
        self.win.SetMultiSamples(4)

        self.iren = vtk.vtkRenderWindowInteractor()
        self.iren.SetRenderWindow(self.win)
        style = vtk.vtkInteractorStyleTrackballCamera()
        self.iren.SetInteractorStyle(style)

        # CRÍTICO: Desactivar CharEvent por defecto de VTK (evita que 'e'/'q' cierren la ventana o 'w' ponga wireframe!)
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
            cam.SetPosition(350.0, -400.0, 265.0)
        else:
            cam.SetFocalPoint(48.0, 0.0, 95.0)
            cam.SetPosition(280.0, -310.0, 225.0)
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

        # Hardware interno (servos MG90S/SG90, 608ZZ, PCA9685, XIAO, AR5515, KCD11)
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
            self.hud_top.SetInput(f"MINI-PRO 4-DOF B2 STEALTH — ENSAMBLE COMPLETO ({len(self.items)} pzas) · [{exp_tag}{xr_tag}{hw_tag}]")
            self.hud_desc.SetInput("Usa [E] explosionar, [X] rayos-X para ver servos/PCBs dentro, [H] hardware, o Clic Derecho sobre cualquier pieza.")
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
