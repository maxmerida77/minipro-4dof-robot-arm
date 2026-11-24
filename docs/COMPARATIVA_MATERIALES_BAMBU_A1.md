# Comparativa de Materiales de Impresión 3D — Bambu Lab A1 Combo (`Mini-Pro 4-DOF B2 Stealth`)

> **Contexto específico de fabricación:** Impresora de marco abierto **Bambu Lab A1 Combo** (`256 × 256 mm`, placa Textured PEI `65–80 °C`, hotend hasta `300 °C`, boquilla estándar `0.4 mm` acero inoxidable, sin cámara cerrada), estética monocromática mate **`B2 Stealth`**, masa móvil crítica sobre `J2` (`~95 g`), superficies deslizantes (`pista J1 Ø88 mm` + `separadores M3`) y presupuesto total del proyecto **`≤ $1,500 MXN`** en México.

---

## 1. Tabla Comparativa Técnica (Evaluada para este Brazo Robótico)

| Material | Acabado `B2 Stealth` | Rigidez (Módulo Flexión) | Tenacidad / Resistencia a Golpe | Temp. Reblandecimiento (HDT) | Fricción / Desgaste (Pista J1 y Engranes) | Imprimibilidad en Bambu A1 (abierta) | Boquilla `0.4 mm` de serie | Costo aprox. MX (1 kg) | Veredicto |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **PLA+ / PLA Pro Mate** *(eSUN ePLA-Matte / PolyLite PLA Pro / Bambu PLA Tough)* | ★★★★★ *(Mate / semi-mate)* | **Muy alta** (~3.2 GPa) | **Alta** (no quiebra en bayonetas) | ~58–62 °C | Media *(muy buena con PTFE/silicón)* | **Excelente** (0 warping) | **Sí** | \$360–\$480 MXN | **GANADOR RECOMENDADO (Mejor equilibrio global)** |
| **PLA Mate estándar** *(Bambu PLA Matte / PolyTerra)* | ★★★★★ *(El más mate)* | Alta (~2.8 GPa) | **Media-baja** *(menor adhesión entre capas)* | ~55 °C | Media-alta *(superficie ligeramente rugosa)* | **Excelente** (0 warping) | **Sí** | \$380–\$520 MXN | **Excelente estética**, pero evitar golpes o calor sostenido en `J2` |
| **PETG / PETG-HF / PETG Mate** *(Bambu PETG-HF / eSUN PETG Matte)* | ★★★☆☆ *(Brilloso salvo versión Matte)* | Media (~2.0 GPa, **flexa más en L2/L3**) | **Muy alta** (dúctil) | **~70–75 °C** *(ideal cerca de MG90S calientes)* | **Baja** *(desliza muy suave en engranes y pista)* | Muy buena *(requiere filamento seco)* | **Sí** | \$380–\$500 MXN | **Ideal para piezas móviles/fricción** (`engranes`, `separadores`, `retén J1`) |
| **PLA-CF** *(PLA con Fibra de Carbono)* | ★★★★★ *(Acabado industrial ultra-mate)* | **Extrema** (~4.5 GPa) | Media-baja *(frágil ante flexión puntual)* | ~58 °C | **Abrasivo** *(desgasta pista/pivotes)* | Muy buena | **NO** *(requiere acero endurecido)* | \$650–\$850 MXN | **No ideal sin boquilla endurecida** y sube costo/abrasión |
| **ABS / ASA** | ★★★★☆ | Alta | Muy alta | ~90–100 °C | Buena | **Mala en A1 abierta** *(warping + gases estireno)* | Sí | \$420–\$550 MXN | **DESCARTADO** para Bambu Lab A1 (sin cámara cerrada) |

---

## 2. Análisis por Zona Crítica de tu Brazo `v4 Clean-DFA`

1. **Estructura exterior (`Base Ø106`, `Torreta`, `L2`, `L3`, `Palma`, `Tapas bayoneta`):**
   * **Qué necesita:** **Máxima rigidez** para que el TCP de Peter Corke no caiga por flexión elástica, **cero deformación (*warping*)** en la base de `Ø 106 mm` y acabado **Negro Mate uniforme** sin brillos plásticos.
   * **Por qué gana PLA+ / PLA Pro (o PLA Mate de buena calidad):** El PLA tiene ~45–60% mayor módulo de elasticidad que el PETG, mantiene tolerancias de `0.22 mm` al milímetro en la A1 y logra el look `B2 Stealth` de producto comercial.
   * **Precaución con PLA Mate "puro":** Los aditivos minerales que lo vuelven ultra-mate reducen ~20–30% la adhesión entre capas; por eso en **`v4`** eliminamos los clips flexibles y pusimos **bayonetas rígidas de 32°** y **horquillas acostadas con fibra continua en XY**. Aun así, un **PLA+ / PLA Pro** (o **PLA Mate de marca confiable como Bambu / Polymaker / eSUN**) soporta mucho mejor el apriete de los tornillos `M2/M3`.
2. **Piezas con fricción y temperatura (`04b_reten_axial_j1`, `11_separador_m3_*`, `08/09_engrane_brazo_12T`, `12_biela`):**
   * Un `MG90S` trabajando continuo puede alcanzar `45–55 °C` en su carcasa; el PLA está justo en su límite térmico (`~55–60 °C`), mientras que el **PETG** aguanta `70–75 °C` sin deformarse (*creep*) y tiene menor fricción deslizante contra el PLA.
3. **10 Acentos `B2 Stealth` (`Placa 2` — solo `7.4 g`):**
   * **PLA Blanco Mate** (o Blanco Pro): prácticamente no carga esfuerzo mecánico y da el máximo contraste fotográfico/visual con **0% purga AMS**.

---

## 3. Recomendación Práctica Final (2 Estrategias Según Tu Presupuesto)

### Opción A — La Más Limpia y Económica (`100% dentro de $1,500 MXN`)
* **1 carrete Negro (1 kg): `PLA+ / PLA Pro Negro` o `PLA Negro Mate` (Bambu / eSUN / Polymaker)** para Placa 1A + Placa 1B.
* **1 carrete Blanco (250 g o 1 kg): `PLA Blanco Mate`** para Placa 2 (`7.4 g`).
* **Truco pro de $15 MXN:** Pon una tira delgada de **cinta PTFE (teflón)** o una gota mínima de **lubricante de silicón seco** en la pista `Ø 88 mm` de `J1` y en los `3×` separadores `M3` → obtienes la rigidez y estética mate del PLA con fricción bajísima.

### Opción B — Combo Híbrido "Ingeniería Pro" (si ya tienes PETG Negro en casa)
* **Placa 1A (Estructura exterior `182.5 g`) + 6 Tapas Bayoneta:** **PLA Negro Mate** *(máxima rigidez + estética `B2 Stealth` 10/10)*.
* **Piezas mecánicas de la Placa 1B (`engranes 12T`, `bielas`, `dedos`, `separadores M3`, `retén axial J1` — solo `~11 g`):** **PETG Negro (o PETG-HF Negro)** *(cero desgaste en dientes módulo `1.5`, menor fricción en pivotes y mayor resistencia térmica junto al `SG90`)*.
* **Placa 2 (`7.4 g`):** **PLA Blanco Mate**.
* *(Nota: nunca mezcles PLA y PETG en la misma pieza multicolor porque no se adhieren entre sí; aquí van en **piezas separadas acopladas mecánicamente**, lo cual es una ventaja enorme porque PLA deslizando contra PETG tiene **menor fricción** que PLA contra PLA!).*
