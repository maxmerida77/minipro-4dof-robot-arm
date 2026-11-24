# Mini-Pro 4-DOF B2 Stealth · Auditoría de prefabricación, Ronda 2

**Fecha:** 24 de noviembre de 2026  
**Destinatario:** Antigravity, responsable de CAD, firmware e integración.

## Dictamen

**CONDITIONAL GO para comprar los componentes electrónicos y los filamentos y avanzar por cupones. NO-GO para imprimir el brazo completo.** Validar el presupuesto de $1,500 MXN con la tornillería corregida antes de cerrar el carrito.

| Etapa | Decisión |
|---|---|
| Cupón 1 · Ajustes | Corregir el corte de cola de milano y regenerar el archivo. |
| Cupón 2 · Articulación J2 | Detener hasta corregir el apoyo pasivo. La Nyloc invade el MG90S. |
| Cupón 3 · Pinza | Apto para ensayo mecánico manual una vez elegida la tornillería para cada unión. |
| Placas completas | Esperar al cierre de los bloqueos mecánicos y a la prueba de los cupones. |
| Movimiento del brazo armado | Completar compilación, corregir la reactivación y ensayar sin carga externa. |

Conservar DH serial 4R `82/82/70/53 mm`, límites v4, acabado B2 Stealth con diez piezas blancas separadas, pinza abierta módulo 1.5 de 12 dientes con SG90, cuatro MG90S, un USB-C y PCA9685 VCC a 3.3 V.

## Correcciones antes de fabricar

| Prioridad | Evidencia y ubicación | Corrección y prueba de aceptación |
|---|---|---|
| **P0 · Pivote pasivo J2/J3/J4** | El [bolsillo Nyloc](../cad/mini_pro_b2_stealth_v4.py#L327) ocupa Y = −12.40 a −8.15 mm y el cuerpo del MG90S ocupa Y = −13.70 a +14.80 mm. En J2 se reprodujeron **83.55 mm³** de intersección B-Rep con una tuerca M3 modelada con 5.5 mm entre caras, 4 mm de altura y agujero central. El mismo constructor se reutiliza en J3/J4 y en el piloto. | Colocar el anclaje pasivo fuera del cuerpo del servo, con material suficiente para retener la tuerca. Redimensionar el separador, el tornillo y la tapa. Verificar la secuencia de inserción, acceso de herramienta y giro libre al apretar. Auditar con la tuerca y el tornillo completos, incluida su cabeza. |
| **P0 · Cupón 1** | El [corte dovetail](../cad/cupones_prototipo_v4.py#L118) ocupa Y = 21 a 63 mm, fuera del bloque de Y = −20 a +20 mm. | Invertir el sentido del corte a `extrude(+42)` en esa construcción. Regenerar y comprobar físicamente que la tapa entra y desliza sin forzar. |
| **P0 · Tornillería de la pinza** | El [BOM](BOM_UNIT_ELECTRONICS.md#L48) agrupa cuatro M3×10 y tres M3×14/16. Dos pivotes delanteros atraviesan **11.8 mm**; dos traseros, **6.4 mm**; dos de las bielas sobre palma, **12.0 mm**; el del engrane pasivo, **8.6 mm**. Añadir **4 mm** de Nyloc, arandelas y salida de rosca. | Cerrar una fila de BOM por unión y verificar que el tornillo atraviese el nylon con al menos un paso libre de rosca (0.5 mm). Usar separadores donde el apriete pueda trabar el giro. Comprobar también que ninguna punta invada el SG90 o el recorrido. Completar longitudes para los M2 de orejas y horns. Los postes del PCA tienen piloto Ø2.6 mm, por lo que M2.5 no agarra directamente. |
| **P0 · Base y lastre** | La [cavidad de lastre](../cad/mini_pro_b2_stealth_v4.py#L645) tiene Ø24 mm. Incluso usando 36.4 mm de altura libre ideal, un cilindro macizo de acero pesaría **129 g como máximo**. Los 200–300 g del BOM no caben en ese alojamiento. | Distribuir el lastre o definir anclaje. Incluir la masa, ubicación y fijación del lastre en CAD. Verificar estabilidad con piezas pesadas y la orientación menos favorable de J1. |
| **P0 · Compilación y reactivación** | En [el endpoint IK](../firmware/minipro_b2_stealth/minipro_b2_stealth.ino#L369), `max(150, server.arg("ms").toInt())` mezcla `int` con `long` en el core ESP32 3.1.3. El [streaming](../firmware/minipro_b2_stealth/minipro_b2_stealth.ino#L178) evita la rampa de 1200 ms al salir de `RELAX`. | Igualar los tipos, compilar para XIAO ESP32-S3 y aplicar un procedimiento común de reactivación. Ensayar desde postura física conocida y apoyada. Validar cada consigna interpolada o la trayectoria completa: actualmente el firmware comprueba el destino antes de interpolar. |
| **P1 · TCP de agarre** | A g=15 mm el centro entre las [almohadillas](../cad/mini_pro_b2_stealth_v4.py#L1057) está en **(53, 0, +5.8) mm** en el marco local CAD. X vale **54.773 mm** a g=2 y **47.035 mm** a g=28. El auditor verifica únicamente X a apertura nominal. | Conservar el TCP DH académico y explicitar la transformación al punto de agarre, incluida altura y apertura. Aplicarla a los objetivos cartesianos de agarre y a su telemetría. |
| **P1 · Auditoría B-Rep** | El [auditor](../cad/auditoria_ensamble_v4.py#L51) usa umbral de 0.05 mm³, convierte excepciones en cero, conserva tres poses con límites antiguos y omite herrajes en varios casos. | Fallar ante errores booleanos. Reportar el umbral y ensayar límites vigentes, apertura 0/2/15/28/30 mm, trayectorias representativas, tornillería, herramientas, cables y conectores. Regenerar los entregables afectados. |

## Resultados comprobados y límites de la evidencia

- **Mallas:** 34/34 STL estancos y de un componente conectado. Los tres cupones y tres placas `.3mf` tienen sus componentes en Z=0 y sin solape de envolventes XY. El script oficial pasó sus seis escenarios. También pasaron, bajo su criterio, las poses J2/J3/J4 `145/20/80`, `22/20/−80` y `145/−125/−80`, con J1=85° y g=28 mm. La penetración Nyloc–servo apareció al añadir ese herraje en una prueba independiente.
- **Mecánica:** los rebajes de bayoneta reducen la sección útil de la horquilla nominal de 4.6 mm. Probarla bajo carga de banco. El casquillo Ø5.0 sobre barreno Ø5.4 tiene **0.20 mm radial**. Hay cortes con holguras literales que no usan `PIVOT_CLEARANCE` o `BAYONET_CLEARANCE`. El par de engranes usa flancos poligonales y pasó un barrido sin penetración a pasos de 1 mm de apertura. Quedan por demostrar el contacto continuo, el juego bajo inversión y el par transmitido.
- **Masa y torque:** el auditor estima 95.1 g móviles. El manifiesto de placas arroja **63.27 g de plástico móvil**, o **109.1 g** con servos y la asignación de 10 g de herrajes. Estimación de **1.02 kgf·cm en J2** en `22/−22/0`, sin objeto, cables ni tornillería. Pesar las piezas y medir consumo y temperatura antes de declarar capacidad.
- **Control:** `DEMO_SEQ` y `SWEEP_SEQ`, con sus segmentos muestreados, pasaron la guarda compartida. También pasaron los cuatro vértices del rectángulo. La IK rechaza la pose legal `(0,145,20,80)` al producir X=−157.18 mm, porque usa radio siempre positivo. Resolver el radio firmado y conservar yaw de referencia cuando r≈0. Se reprodujo que la guarda Python acepta `NaN`. Rechazar entradas no finitas antes de IK, guarda y PWM. El JavaScript pasó comprobación sintáctica. El compilador Xtensa del equipo abortó con `Illegal System DLL Relocation`, por lo que falta verificar compilación completa de los dos sketches.
- **Potencia:** el netlist KiCad confirma VCC a 3V3, D4/GPIO5 SDA, D5/GPIO6 SCL, CH0–CH4, capacitor y cátodo del 1N5819 hacia XIAO. El script SPICE reprodujo **4.434 V en servos, 4.171 V en XIAO y 2.534 A de pico** con el perfil supuesto. El `.cir` sigue sin OCP y produjo **4.317 V, 4.052 V y 2.820 A**. La simulación Wokwi usa 5 V del DevKit para los servos y sirve para comprobar señales. Verificar en banco el límite real, el reinicio con PCA aún alimentado y la conexión USB simultánea en la revisión física de la XIAO.

## Secuencia de aceptación en banco

1. **Cupón 1 corregido.** Usar la A1 y los filamentos finales. Medir encaje y holgura y hacer diez ciclos de apertura de bayoneta.
2. **Cupón 2 corregido.** Montar el MG90S y la tornillería completa. Verificar con las herramientas reales el acceso al horn y orejas, el agarre de la Nyloc, el giro al apretar y la rigidez sin cabeceo apreciable.
3. **Cupón 3.** Barrer 0–30 mm a mano. Confirmar engrane continuo, paralelismo, sujeción de las almohadillas y ausencia de roce con cabezas y puntas. Medir el centro de agarre a 2/15/28 mm.
4. **Base.** Montar lastre y cableado reales. Comprobar alcance de cables con bucles, retención axial independiente del horn de J1 y par de arranque de la pista cargada.
5. **Integración sin carga externa.** Verificar sentido y pulsos de cada servo con movimientos cortos, `RELAX` y reactivación con apoyo. Medir tensión mínima de servos y XIAO con osciloscopio, pico de corriente, comportamiento ante reinicio y temperatura de J2 tras varios minutos.
