# Ruta Iterativa del Proyecto — Brazo Robótico Mini-Pro 4-DOF (`B2 Stealth`)

> **Meta:** Entregar un proyecto escolar sobresaliente con **Peter Corke (`roboticstoolbox-python 1.5.0`)** y un brazo minimalista de escritorio acabado como producto comercial, dentro de **\$1,500 MXN todo incluido** (logrado: **~\$1,155–\$1,355 MXN** comprando 100% local en México).

---

## Arquitectura Bloqueada (Single Source of Truth: `cad/params.py`)
* **4 DOF + Pinza:** `4× MG90S` 180° metálicos (`AR1240`, huella compatible con futuro upgrade `MG92B`) + `1× SG90` (ya disponible).
* **Control y energía (1 solo cable USB-C negro):** `XIAO ESP32-S3` (ó `C3`) + `PCA9685` (`AR0389`) + Cargador **UGREEN 50W** → Módulo USB-C PD **`AR5515` (5V)** + botón ON/OFF **`KCD11-2P`** (`AR0243`) + diodo Schottky **`1N5819`** (`AR0195`) + capacitor **`1000 µF 16V`** (`AR1127`).
* **Geometría DH:** `d₁ = 82 mm`, `a₂ = 82 mm`, `a₃ = 70 mm`, `a₄ = 53 mm` (alcance horizontal `205 mm`, base `Ø 94 mm`, `4×` rodamientos `608ZZ-7`, `16×` insertos M3 `AR2811`).
* **Acabado:** **`B2 Stealth`** en PLA Negro Mate (95%) + Blanco Mate (5% en piezas separadas = **0% purga AMS**).

---

## Mapa de Iteraciones

### Iteración 0 — Envolvente 3D, Parámetros Maestros y Concepto Estético *(COMPLETADA)*
* `cad/params.py`, concepto `B2 Stealth` seleccionado, envolvente paramétrica 3D.

### Iteración 1 — Cinemática Oficial Peter Corke (Python) + BOM Verificado *(COMPLETADA)*
* `python/robot_minipro_rtb.py`, `python/demo_peter_corke.py`, gráficas en `docs/graficas_peter_corke/` (`error FK-IK = 1.27e-14°`, `error Z ctraj = 6.39e-14 mm`).
* Carrito 100% verificado en vivo en **UNIT Electronics México**: `docs/BOM_UNIT_ELECTRONICS.md` (`\$566 MXN` subtotal).

### Iteración 2C — Refinamiento Mecánico DFM `CAD v3` (Revisiones A + B + C) *(COMPLETADA)*
* `cad/mini_pro_b2_stealth_v3.py` → `mini_pro_b2_stealth_v3.step` + **35/35 STLs estancos** (`23` Negro Mate + `12` Blanco Mate):
  * **Revisión A:** acceso trasero `+Y` para `MG90S` con escalón de orejas + pilotos M2, bujes centradores `11_buje_608zz_*` + tornillo M3×10 hacia insertos `AR2811`, bolsillos empotrados de *horn*, ductos continuos de cables `10 × 8 mm` y tapas Stealth con ceja centradora + 2 barrenos M3.
  * **Revisión B:** pinza paralela real de 4 barras (`SG90` coaxial bajo engrane-brazo `14T` izq, `2×` bielas traseras `12_biela_pinza_*`, pila Z libre de colisiones y dedos con doble pivote M3).
  * **Revisión C:** corte plano en D en `04_torreta` + `04b_engrane_torreta_22t` (cero patinaje en J1), bolsillo *horn* en `02_pinon_base_22t`, 4 postes barrenados para `PCA9685`, retenedores `XIAO`/`AR5515` y huecos de gomitas antideslizantes.
* Tablero DFM (`docs/renders/renders_iter3_dfm_v3.png`), catálogo de 35 piezas (`docs/renders/catalogo_piezas_b2_stealth.png`), Visor 3D y Gemelo Digital 3D (con paralelogramo 4 barras animado) 100% sincronizados.

### Iteración 4 — Circuito Eléctrico 1-Cable + Firmware `XIAO ESP32-S3` + Puente Wi-Fi *(COMPLETADA)*
* Esquema eléctrico de potencia y lógica: `electronics/esquema_cableado_b2_stealth.png` + `electronics/DIAGRAMA_CABLEADO.md`.
* Firmware completo: `firmware/minipro_b2_stealth/` (`minipro_b2_stealth.ino`, `config.h`, `web_ui.h`) + `firmware/platformio.ini` + `firmware/README_FIRMWARE.md`.
  * Interpolador quíntico mínimo-jerk a `100 Hz` (idéntico a `rtb.jtraj`).
  * Control triple simultáneo: **USB Serial (`115200`)**, **Wi-Fi UDP (`4210`)** para Peter Corke con 1 solo cable, y **Web UI `B2 Stealth`** integrada en la XIAO.
* Gemelo digital actualizado (`python/gemelo_digital_esp32.py`) con `--wifi <IP>`, `--port COMx` y `DRY_RUN`.

### Iteración 3 — DFM, Platos de Impresión Bambu Lab A1 Combo y Prueba de Tolerancias *(POSPUESTA PARA CUANDO LLEGUEN FILAMENTO / PIEZAS)*
* Acomodar automáticamente las 29 piezas planas sobre `Z = 0` en 2 platos `256 × 256 mm` (Negro Mate y Blanco Mate) con orientación óptima de capas y cero/mínimos soportes.
* Imprimir el **Kit de Tolerancias de 20 min**, ajustar `CLEARANCE_FIT` si hace falta e imprimir el juego definitivo.

### Iteración 5 — Pruebas en Banco, Ensamble Físico y Entrega Escolar *(FINAL)*
* Verificación `5.0 V` del `AR5515` con multímetro, centrado `CENTER` (`1500 µs`) de los `4× MG90S` antes de atornillar los *horns*, ensamble mecánico completo y ajuste fino de `offset_deg` en `config.h`.
* Validación del Gemelo Digital sincronizado (`Peter Corke Python ↔ XIAO ESP32-S3`) por Wi-Fi UDP y grabación/presentación de las 3 demos en clase.
