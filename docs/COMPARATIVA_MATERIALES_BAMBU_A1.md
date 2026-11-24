# Investigación de Materiales de Impresión 3D — Bambu Lab A1 Combo (`Mini-Pro 4-DOF B2 Stealth`)

> **Basado en hojas técnicas oficiales (TDS ISO 527 / ISO 178 / ISO 179)** de **Bambu Lab** y **Polymaker**, y pruebas empíricas de mecanismos/engranes (rigidez, impacto con muesca, *creep*, temperatura HDT y tribología) aplicadas específicamente a tu **Bambu Lab A1 Combo** (marco abierto, boquilla `0.4 mm` de serie, sin cámara cerrada).

---

## 1. El Mito del PETG vs Datos Reales de Laboratorio (TDS Oficiales)

Es muy común escuchar que *"el PETG es más resistente que el PLA para mecanismos"*, pero la palabra *"resistente"* mezcla **5 propiedades distintas**. Al revisar los datos reales de laboratorio:

| Propiedad (ISO) | Bambu PLA Matte | Bambu PLA Basic | Polymaker PolyLite PLA Pro | Bambu PETG-HF | Polymaker PolyLite PETG | Qué significa para tu brazo `v4` |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Módulo de Flexión (Rigidez)** | `2,360 MPa` | **`2,750 MPa`** | **`2,700–2,933 MPa`** | `2,050 MPa` | `1,898 MPa` | **Gana PLA Pro (+45% más rígido):** menos pandeo en `L2/L3`, menos vibración en el TCP y dientes `12T` que no ceden. |
| **Resistencia a Flexión (XY)** | `53 MPa` | **`76 MPa`** | **`68–78 MPa`** | `64 MPa` | `69.6 MPa` | **PLA Basic/Pro superan a PETG-HF**; ojo: **PLA Matte sí es ~30% más débil** que PLA Basic/Pro. |
| **Tracción en eje Z (unión entre capas)** | `22 MPa` | **`31 MPa`** | Alta (~35+ MPa) | `23 MPa` | ~28 MPa | En Bambu Lab, `PLA Basic` tiene **mejor adhesión entre capas** que `PLA Matte` y `PETG-HF`. |
| **Impacto Charpy con muesca (XY)** | `6.3 kJ/m²` | `7.9 kJ/m²` | **`13.4–17.1 kJ/m²`** | `~6.2 kJ/m²` | `2.6 kJ/m²` | **Gana PLA Pro (2–5× sobre PETG):** en esquinas, bayonetas y raíz de dientes de engrane resiste mucho mejor grietas. |
| **Elongación a rotura (ductilidad)** | Media-baja | Baja | `6.3%` | Alta | **`8.4%`** | **Gana PETG:** antes de romper se dobla visiblemente (útil para clips flexibles, pero en `v4` ya usamos bayonetas rígidas). |
| **Temp. deflexión térmica (HDT @ 0.45 MPa)** | `58 °C` | `57 °C` | `62 °C` | **`69 °C`** | **`78 °C`** | **Gana PETG (+12 a +20 °C):** mejor resistencia al calor si un `MG90S` se calienta a >50 °C bajo carga sostenida. |
| **Fricción / Desgaste (Tribología)** | Rugoso (aditivos mate) | Duro y limpio | **Duro y limpio** | **Blando / pegajoso (*galling*)** | **Blando / pegajoso (*galling*)** | **PETG contra PETG se "traba" más** bajo carga por desgaste adhesivo; PLA duro en baja velocidad (<60 RPM) va más limpio (y aún mejor con cinta PTFE). |
| **Soportes Árbol y Tolerancias (`0.22 mm`)** | Excelente | Excelente | **Excelente** | Soportes difíciles + hilillos si absorbe humedad | Soportes difíciles + *stringing* | En Placa 1A (con Árbol) y dientes `12T`, PLA Pro sale limpio a la primera sin secar carrete. |

*(ABS/ASA descartados por ser impresora abierta sin cámara cerrada; PLA-CF descartado porque exige boquilla de acero endurecido y es abrasivo en pivotes/pista).*

---

## 2. Conclusión Honesta para Mecanismos del Brazo `Mini-Pro 4-DOF v4`

1. **¿Cuándo SÍ conviene PETG en mecanismos?**
   * Cuando el mecanismo trabaja **cerca de motores muy calientes (>50–55 °C)** (ej. motores paso a paso NEMA 17 en una impresora 3D o un auto al sol),
   * Cuando hay **clips que deben flexionarse repetidamente** (*snap-fits*), o
   * Cuando hay **tensión constante permanente** (un resorte plástico o tornillo apretado sin casquillo donde el PLA sufre *creep* lento).
2. **Por qué en ESTE brazo `v4 Clean-DFA` gana un buen `PLA+ / PLA Pro` (y pierde el PETG completo):**
   * **Rigidez del brazo:** Con `205 mm` de alcance y solo `~95 g`, imprimir `L2/L3` en PETG reduce la rigidez ~35–45%, haciendo que el brazo rebote al frenar y pierda precisión en el TCP de Peter Corke.
   * **Sin clips flexibles ni cargas térmicas de NEMA 17:** En `v4` eliminamos los clips flexibles (bayonetas `32°` rígidas) y los pivotes tienen casquillos lisos `M3` + tuercas `Nyloc` (no aprietan el plástico). Los `MG90S` con rampas suaves de `1100 ms` sin sobrecarga trabajan a ~30–40 °C (muy debajo de `60–62 °C`).
   * **Engranes `12T` mod `1.5` y pista `J1`:** PETG contra PETG es blando y tiene tendencia a pegarse (*galling*) bajo presión, además de producir hilillos que ensucian los flancos de los dientes. El **PLA Pro** mantiene el perfil rígido y preciso del diente con **5× más resistencia a grieta con muesca** que el PETG estándar.
   * **OJO con el "PLA Mate" puro:** Los datos de Bambu Lab muestran que **PLA Matte (`53 MPa` flexión, `22 MPa` en Z)** sí es claramente más frágil que **PLA Basic (`76 MPa`, `31 MPa` en Z)** y **PolyLite PLA Pro (`70+ MPa`, `13–17 kJ/m²`)**.

---

## 3. Veredicto Final Recomendado (Ordenado de Mejor a Peor para Tu Caso)

1. **#1 RECOMENDADO (Mecanismos + Estética): `PLA+ / PLA Pro Negro` (acabado mate o satinado bajo, ej. Polymaker PolyLite PLA Pro / eSUN PLA+ / Bambu PLA Tough)** + `PLA Blanco Mate` para los 10 acentos (`7.4 g`).
   * Combina la **máxima rigidez** (~2,800 MPa), **máxima resistencia a impacto en dientes y bayonetas** (`13–17 kJ/m²`), tolerancias exactas en `0.22 mm`, cero problemas de soportes árbol en Placa 1A y cero *warping* en tu A1.
   * Añade cinta **PTFE (teflón)** o una gota mínima de silicón seco en la pista `Ø 88 mm` de `J1` y los `3×` separadores `M3`.
2. **#2 Alternativa si priorizas 100% el acabado ultra-mate de estudio:** **PLA Negro Mate** de marca (Bambu / PolyTerra / eSUN ePLA-Matte) **SOLO en carcasas exteriores**, y **PLA+ / PLA Pro** (o **PETG** únicamente si ves que el `SG90` de la pinza o `J2` se calientan >48 °C en pruebas reales) en `11_separador_m3`, `04b_reten_axial_j1` y `08/09_engrane_brazo`.
3. **#3 Todo en PETG (o PETG-HF Mate):** **Funciona** si ya tienes el carrete y secas bien el filamento, pero espera **más flexión en `L2/L3`**, **soportes árbol más difíciles de quitar en Placa 1A**, posibles hilillos en los dientes `12T` y **mayor fricción pegajosa** en la pista `J1` si no pones cinta PTFE.
