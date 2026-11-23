# Brief de Revisión de Arquitectura y Física — `CAD v3.1` → Propuesta `v4 Clean-DFA` (`Mini-Pro 4-DOF B2 Stealth`)

> **Objetivo de este documento:** Entregar a un segundo agente revisor (ej. **Codex**) todos los datos medidos, ecuaciones físicas, riesgos detectados y decisiones abiertas para una **segunda opinión independiente y rigurosa** antes de modelar `CAD v4` o imprimir piezas.

---

## 1. Restricciones Fijas del Proyecto (No Modificar)
* **Cinemática DH estándar 4R serial (Peter Corke):** `d1 = 82 mm`, `a2 = 82 mm`, `a3 = 70 mm`, `a4 = 53 mm` (`r_max = 205 mm`).
  * `J1 ∈ [-90°, +90°]`, `J2 ∈ [+15°, +165°]`, `J3 ∈ [-135°, +45°]`, `J4 ∈ [-90°, +90°]`, `Pinza ∈ [0, 30 mm]`.
* **Actuadores:** `4× MG90S` (`1.85 kg·cm` stall @ `5.0V`, `~1.25 kg·cm` continuo cómodo, `13.4 g`, `22.8 × 12.2 × 28.5 mm`; huella compatible con `1× MG92B` `3.1 kg·cm` en `J2`) + `1× SG90` (`9.0 g`, `~1.2–1.5 kg·cm`, pinza).
* **Electrónica (ya validada en KiCad 9 `0 ERC` + `ngspice` SPICE):** `UGREEN 50W` → `AR5515` (`5V/3A`) → `KCD11-2P` → `C1 = 1000 µF` (`V_SERVO min = 4.29 V` ante pico `3.6 A / 350 µs`) + `1N5819` (`V_drop = 0.265 V`, fuga inversa `26 µA` con laptop USB-C) → `XIAO ESP32-S3` ↔ `PCA9685` (`I2C 3.3V`).
* **Impresora y material:** **Bambu Lab A1 Combo** (`256 × 256 mm`, boquilla `0.4 mm`), **PLA Mate Negro (~95%) + PLA Mate Blanco (~5%, piezas separadas = 0% purga AMS)**.
* **Estética obligatoria `B2 Stealth`:** Silueta negra mate limpia + `10` detalles en blanco mate (`w01` aro base, `6×` aros `J2/J3/J4`, `w02` collar muñeca, `2×` almohadillas pinza `w04`).
* **Pinza elegida por el usuario:** **Pinza Paralela Abierta de 2 dedos simétricos (estilo MeArm, engranes módulo `1.5`)** para mantener el objeto centrado en el `TCP` de Peter Corke (sin cámara).

---

## 2. Datos Físicos Medidos en `CAD v3.1` Actual (`cad/mini_pro_b2_stealth_v3.py`)

### A) Masas reales de la parte móvil (`J2..TCP`) y cuello de botella en `J2`
* `05_eslabon_l2_codo` (PLA): `37.1 g` @ `x = 4.1 cm`
* Hardware `J3` (`MG90S` `13.4 g` + `608ZZ` `12.0 g` + buje/tapas/tornillos `5.0 g`): `30.4 g` @ `x = 8.2 cm`
* `06_antebrazo_l3_muneca` (PLA): `22.2 g` @ `x = 11.7 cm`
* Hardware `J4` (`MG90S` `13.4 g` + `608ZZ` `12.0 g` + buje/tapas/tornillos `4.0 g`): `29.4 g` @ `x = 15.2 cm`
* Pinza completa (`07_palma` + 4 barras + `SG90` `9.0 g` + 6 pines M3): `25.2 g` @ `x ≈ 18.6 cm`
* **Masa móvil total `v3.1`:** **`144.3 g`**
* **Torque estático en vacío (brazo 100% horizontal a `205 mm`):**
  * **`J2` Hombro:** **`1.578 kg·cm`** (**`85%` del límite *stall* `1.85 kg·cm` del `MG90S`!** → margen seguro en extensión total ≈ `0–13 g`).
  * **`J3` Codo:** `0.547 kg·cm` (`30%` del *stall*).
  * **`J4` Muñeca:** `0.087 kg·cm` (`5%` del *stall*).

### B) Problemas reales de ensamble (DFA) detectados en `CAD v3.1`
1. **Bloqueo del tornillo del *horn* (`J2/J3/J4`):** El disco del eslabón entra en una ranura cerrada de `5.6 mm` con el inserto `AR2811` justo detrás del eje del `MG90S` → impide meter un desarmador Phillips para atornillar el *horn* al eje metálico del servo.
2. **Riesgo de trabamiento (*binding*) y sobrepeso de `3× 608ZZ` en `J2/J3/J4`:** Un balero `608ZZ` (`Ø 22 × 7 mm`, `12 g`) enfrentado rígidamente a un microservo `MG90S` (`13.4 g`) en un tambor de `48 mm` se traba ante `~0.3 mm` de error FDM y añade `~35 g` en `J3/J4`.
3. **Transmisión `22T:22T` (1:1) a ciegas en `J1`:** No multiplica torque, introduce `2–4°` de *backlash* en la base (amplificado ×205 mm en el TCP), obliga a alinear dientes a ciegas dentro del cilindro y un solo `608ZZ` de `7 mm` de altura puede cabecear (*wobble*).
4. **Pinza `v3.1` de 11 piezas con engranes módulo `1.0`:** Dientes demasiado finos para boquilla `0.4 mm`, puente superior cerrado dificulta alinear fase de dientes + 4 pines + 2 micro-aros `w03` de `0.6 mm`.
5. **Túneles internos cerrados (`10 × 8 mm`) e insertos en discos finos (`5 mm`):** Difícil pasar conectores Dupont 3-pin y alto riesgo de desalinear/derretir al meter insertos con cautín en espesores de `5 mm`.

---

## 3. Arquitectura Propuesta para `v4 Clean-DFA` (Sujeta a Validación de Segunda Opinión)

| # | Subsistema | Propuesta `v4 Clean-DFA` (`30 piezas`, 100% estética `B2 Stealth`) | Mejora esperada |
| :-: | :--- | :--- | :--- |
| 1 | **Base `J1`** | `MG90S` centrado coaxial directo al *horn* en torreta + **pista anular amplia (`Ø 78 mm`)** de apoyo axial/vuelco (anillo liso PTFE o bolas de acero `4.5 mm`). | `−2` engranes `22T`, `0°` backlash, `0` cabeceo, armado directo. |
| 2 | **Articulaciones `J2, J3, J4`** | **Horquilla en U abierta** abrazando al `MG90S`: lado motriz con bolsillo *horn* `2.0 mm` + **barreno frontal `Ø 4.5 mm`** para desarmador + 2 tornillos en brazo *horn*; lado pasivo con **pivote `M3 + tuerca Nyloc`** (o micro-balero `623ZZ`/`683ZZ` — **evaluar en revisión!**). | Acceso 100% libre, `0%` *binding*, **`−35 g`** en brazo → esfuerzo `J2` baja de `85%` a **`~55%`**. |
| 3 | **Estética `B2 Stealth`** | Se conservan las **`6×` tapas laterales + `6×` aros blancos + aro base + collar muñeca + `2×` almohadillas (`10` pzas blancas, `0%` purga AMS)**. Las `6×` tapas pasan a **cierre *snap-fit* (o imán / encaje)** sin 12 tornillos extra. | Aspecto exterior 100% idéntico al `B2 Stealth`, sin tornillos a la vista. |
| 4 | **Pinza (`SG90`)** | **Pinza Paralela Abierta `MeArm` módulo `1.5`** (`7` piezas negras + `2` almohadillas blancas): 2 engranes-brazo `10T–12T` mod `1.5` visibles arriba, 2 bielas, 2 dedos paralelos, pivotes `M3 Nyloc`. Se eliminan los 2 micro-aros `0.6 mm`. | Cierre paralelo centrado en `TCP`, dientes gruesos fiables en boquilla `0.4 mm`, fácil de alinear. |
| 5 | **Tornillería** | Unificar a **`M3` (tuercas hexagonales cautivas + tuercas `Nyloc`)** + **`M2`** incluidos en los servos. Insertos `AR2811` opcionales solo en la base fija gruesa. | Sin cautín en piezas delgadas, `$25 MXN` ferretería local, ahorra `~$100 MXN`. |
| 6 | **Cables** | **Canal longitudinal en la espalda** de `L2` y `L3` cerrado con **`2×` clips negros *snap-fit*** (invisible de frente/costado). | Cableado en 2 min, reemplazo de servo en 10 s. |

---

## 4. Preguntas Críticas para la Segunda Opinión Técnica (Checklist para Codex)

Por favor, valida y cuestiona **con números y física real** (no opiniones genéricas) los siguientes 7 puntos críticos antes de construir `CAD v4`:

1. **Estabilidad anti-vuelco de la base (`Ø 94 mm`):** Con el brazo extendido a `205 mm` sosteniendo `40–60 g` (peso propio base + electrónica ≈ `120 g`), ¿vuelca la base o conviene agregar un hueco para lastre económico (tuercas/monedas/arandelas M10 de `~150–200 g`) en la cavidad inferior?
2. **Fricción y retención axial en `J1` (pista anular `Ø 78 mm`):**
   * Si la torreta solo "apoya" sobre la pista `Ø 78 mm` y el *horn* del `MG90S` la sujeta en el centro, ¿qué evita que la torreta se levante/incline bajo momento de vuelco (`M ≈ 0.25 N·m`)? ¿Conviene una **pista con labio retenedor / balines en canal en V**, un **`608ZZ` central SOLO en `J1` + pista plana de apoyo en `Ø 78 mm`**, o **3 tornillos guía en ranura curva**?
   * Calcular fricción de deslizamiento PLA-PLA (`μ ≈ 0.2–0.3`) vs bolas de acero (`μ ≈ 0.02`) para confirmar que el `MG90S J1` no pierda torque por roce.
3. **Pivote pasivo en `J2/J3/J4` (`M3 + Nyloc` en PLA vs micro-balero `623ZZ`/`683ZZ` vs `608ZZ` solo en `J2`):**
   * ¿Es suficiente un tornillo `M3` girando directo en PLA con tuerca `Nyloc` para `J2` (soporta `~1.1 kg·cm` + carga radial de `~1 N`), o conviene dejar un rodamiento (ej. `608ZZ` flotante o `623ZZ`) en `J2` y pivote `M3 Nyloc` en `J3/J4`?
   * ¿Qué espesor mínimo de pared de horquilla en PLA Mate (`4 paredes`) evita deflexión lateral cuando el `MG90S` aplica `1.85 kg·cm`?
4. **Fatiga de pestañas *snap-fit* en PLA Mate:**
   * El PLA Mate es más frágil que el PLA+ o PETG. ¿Qué longitud mínima de viga *cantilever* (`L`), espesor (`t`) y saliente (*undercut*) son seguros para que las 6 tapas laterales y los 2 clips de cables no se rompan al abrir/cerrar 5–10 veces? ¿O conviene cierre por **bayoneta (giro 15°)** / **ajuste por fricción con pestaña larga**?
5. **Pinza Paralela Abierta `MeArm` módulo `1.5` con `SG90`:**
   * Validar geometría exacta: número de dientes (`Z = 10` ó `12`, módulo `1.5`), distancia entre centros (`a = m·Z + backlash`), longitud de biela `L` para lograr `0–30 mm` sin singularidad ni choque con el `SG90`, y verificar que el torque del `SG90` (`~1.2 kg·cm`) genere suficiente fuerza normal en las mordazas (`≥ 1.5–2 N`) para levantar cubos de `40–60 g`.
6. **Torque dinámico y margen real en `J2` (`MG90S` vs `1× MG92B`):**
   * Verificar si reduciendo la masa móvil a `~100 g` (con pinza `MeArm` mod `1.5` y sin `608ZZ` en `J3/J4`), un `MG90S` en `J2` realmente opera sin vibración en trayectorias quínticas de `0.9 s` (`a_max`), o si sigue siendo altamente recomendable invertir en `1× MG92B` solo para `J2`.
7. **Verificación rápida de electrónica y tolerancias FDM:**
   * Revisar `electronics/kicad/minipro_b2_stealth.kicad_sch` y `electronics/simulacion_spice/minipro_b2_stealth_power.cir` para confirmar que no existe ningún punto ciego eléctrico antes de comprar el carrito en UNIT Electronics.

---

## 5. Prompt Listo para Copiar y Pegar a Codex

```text
Lee primero `AGENTS.md` y `docs/BRIEF_REVISION_ARQUITECTURA_V4.md`, e inspecciona `cad/params.py`, `cad/mini_pro_b2_stealth_v3.py`, `cad/auditoria_ensamble_v3.py` y `electronics/kicad/minipro_b2_stealth.kicad_sch`.

Actúa como un ingeniero mecánico senior especializado en robótica impresa en 3D (FDM, Bambu Lab A1, PLA Mate) y Design for Assembly (DFA). NO modifiques todavía ningún archivo del repositorio; necesito una segunda opinión técnica crítica y honesta antes de diseñar `CAD v4` o comprar piezas.

Evalúa con cálculos físicos concretos (números, no generalidades):
1. Las 7 preguntas críticas listadas en la Sección 4 de `docs/BRIEF_REVISION_ARQUITECTURA_V4.md` (estabilidad anti-vuelco de la base Ø94 mm, retención y fricción en J1, pivote pasivo M3 Nyloc vs rodamiento en J2/J3/J4, durabilidad de tapas snap-fit/bayoneta en PLA Mate, geometría y fuerza de la pinza paralela abierta MeArm módulo 1.5 con SG90, torque estático + dinámico real en J2, y revisión de la etapa de potencia/protección).
2. Señala cualquier otro fallo potencial de ensamble, colisión en movimiento, tolerancia FDM (boquilla 0.4 mm) o debilidad estructural que no hayamos visto todavía.
3. Entrega una lista final concreta y priorizada de las especificaciones exactas que recomiendas congelar para construir `CAD v4` sin errores (respetando TODAS las reglas innegociables de `AGENTS.md`, incluyendo cinemática DH 4R de Peter Corke y estética B2 Stealth con detalles en blanco).
```
