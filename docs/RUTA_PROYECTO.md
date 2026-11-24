# Ruta Iterativa del Proyecto — Brazo Robótico Mini-Pro 4-DOF (`B2 Stealth` · `v4 Clean-DFA`)

> **Meta:** Entregar un proyecto escolar sobresaliente con **Peter Corke (`roboticstoolbox-python 1.5.0`)** y un brazo minimalista de escritorio acabado como producto comercial, dentro de **\$1,500 MXN todo incluido** (logrado: **~\$1,120–\$1,320 MXN** comprando 100% local en México).

---

## Arquitectura Bloqueada (Single Source of Truth: `cad/params.py`)
* **4 DOF + Pinza:** `4× MG90S` 180° metálicos (`AR1240`, huella compatible `drop-in` con futuro `MG92B` en `J2`) + `1× SG90` (ya disponible).
* **Control y energía (1 solo cable USB-C negro):** `XIAO ESP32-S3` + `PCA9685` (`AR0389`, `VCC` estrictamente a `3V3`) + Cargador **UGREEN 50W** → Módulo USB-C PD **`AR5515` (DIP 5V)** + botón ON/OFF **`KCD11-2P`** (`AR0243`) + diodo Schottky **`1N5819`** (`AR0195`) + capacitor **`1000 µF 16V`** (`AR1127`).
* **Geometría DH (Innegociable):** `d₁ = 82 mm`, `a₂ = 82 mm`, `a₃ = 70 mm`, `a₄ = 53 mm` (alcance horizontal `205 mm`; base coaxial `Ø 106 mm` con 6 patas perimetrales `r = 45.5 mm`, 0 rodamientos `608ZZ`, 0 insertos con cautín).
* **Acabado:** **`B2 Stealth`** en PLA Negro Mate (~95%) + **10 piezas Blanco Mate separadas** (`0%` purga AMS).

---

## Mapa de Iteraciones

### Iteración 0 — Envolvente 3D, Parámetros Maestros y Concepto Estético *(COMPLETADA)*
* `cad/params.py`, estética `B2 Stealth` monocromática seleccionada.

### Iteración 1 — Cinemática Oficial Peter Corke (Python) + BOM Verificado *(COMPLETADA)*
* `python/robot_minipro_rtb.py`, `python/demo_peter_corke.py`, gráficas en `docs/graficas_peter_corke/` (`error FK-IK = 1.27e-14°`, `error Z ctraj = 6.39e-14 mm`).

### Iteración 2 & 3 — `CAD v3.1` + KiCad 9.0 + Fritzing 4K + SPICE + Wokwi *(COMPLETADA)*
* Esquema nativo KiCad 9.0 (`0 Errores, 0 Avisos` ERC), diagrama pictórico Fritzing 4K, simulación SPICE real en `ngspice.dll`, simulador Wokwi (`ESP32-S3 + PCA9685 custom chip + 5 servos`).

### Iteración 4 — Auditoría Cruzada (Codex + DFA) → `CAD v4 Clean-DFA` *(COMPLETADA Y VERIFICADA 8/8)*
Resuelve íntegramente los 8 hallazgos técnicos detectados en la auditoría independiente antes de fabricar:
1. **Sólido único conectado (`34/34` STLs `len(split()) == 1`):** Horquillas en U monolíticas `L2/L3` (`05_eslabon_l2_v4`, `06_antebrazo_l3_v4`) y base `01_base_fija_v4` con jefes fusionados.
2. **Despeje multipose (`0.00 mm³` en 6 escenarios) + Guarda Anti-Mesa:** Eliminada la colisión `198.44 mm³` en `J3=-135°` y el contacto con la mesa (`Z_tcp ≥ 8 mm`, `Z_j3/j4 ≥ 22 mm` bloqueados en firmware, Wokwi, Peter Corke y Gemelo Digital).
3. **Pinza Paralela Abierta MeArm Módulo `1.5` (`12T`):** 1 solo sólido rígido engrane+brazo+horn, centro de almohadillas calibrado exacto en **`53.000 mm`** (`err = 0.0000 mm`), ecuación trigonométrica exacta compartida (`asin/cos`) eliminando la aproximación lineal `3°/mm`.
4. **Base Coaxial `Ø 106 mm` sin colisiones (`0.00 mm³`):** `MG90S J1` centrado + `PCA9685` desplazado a `+X` con volumen real de conectores Dupont (`23 mm`), `KCD11` con terminales faston (`19 mm`), `XIAO`, `AR5515`, `1000 µF` y aro de lastre.
5. **Balance de masa y carga útil realista:** Masa móvil reducida a **`~95.1 g`** (`49.3 g` PLA); arranque protocolizado **sin carga externa** con rampas suaves de `1100 ms` hasta medir corriente y temperatura real.
6. **Estabilidad y retención axial `J1`:** 6 patas perimetrales (`r = 45.5 mm`, radio efectivo `39.4 mm`) + retén axial independiente **`04b_reten_axial_j1`** (`3× M3`) liberando al *horn* de cargas axiales.
7. **Pivotes con separador M3 + Bayonetas `32°` + Cupones progresivos:** Casquillos `11_separador_m3_*` (rosca fuera del giro, `Nyloc` no frena la horquilla), tapas Stealth de bayoneta (`0` flexión PLA), tapas de cables `dovetail` y **3 cupones `.3mf`** (`cupon_1`, `cupon_2` articulación piloto, `cupon_3` pinza independiente).
8. **Potencia y seguridad de firmware:** `FULL_OFF` real (`4096`) desde `setup()`, resincronización tras `CENTER`/`RAW`, rampa de despertar (`≥ 1200 ms`), simulación SPICE con modelo OCP `3.0 A` (`I_PD máx = 2.53 A < 3.0 A`), y `2×` tiras Dupont `20 cm` en el BOM para bucles articulados holgados.

### Iteración 5 — Prototipado Progresivo, Pruebas en Banco y Entrega Escolar *(SIGUIENTE PASO FÍSICO)*
1. Imprimir **Cupón 1 → Cupón 2 (1 articulación con servo real) → Cupón 3 (pinza independiente con SG90)**.
2. Imprimir las **3 placas `v4` (`223.2 g` PLA, `0%` purga AMS)** en Bambu Lab A1 Combo.
3. Verificar `5.0 V` del `AR5515` y caída real bajo carga con multímetro; ejecutar `CENTER` antes de fijar *horns*.
4. Ejecutar demostración final sincronizada **Peter Corke Python ↔ Gemelo Digital 3D ↔ XIAO ESP32-S3 (Wi-Fi UDP)**.
