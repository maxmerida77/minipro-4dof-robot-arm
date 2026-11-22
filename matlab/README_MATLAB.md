# Scripts MATLAB (Peter Corke Robotics Toolbox) — Mini-Pro 4-DOF B2

Estos scripts están listos para ejecutarse en **MATLAB R2024b** y comparten al milímetro las mismas dimensiones Denavit-Hartenberg que el CAD paramétrico (`cad/params.py`):

| Eslabón | `θᵢ` | `dᵢ` (mm) | `aᵢ` (mm) | `αᵢ` | Límites reales (`MG92B`) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **J1 (Base Yaw)** | `q₁` | `85` | `0` | `+90°` | `[-90°, +90°]` |
| **J2 (Hombro)** | `q₂` | `0` | `95` | `0°` | `[+15°, +165°]` |
| **J3 (Codo)** | `q₃` | `0` | `80` | `0°` | `[-135°, +45°]` |
| **J4 (Muñeca)** | `q₄` | `0` | `60` | `0°` | `[-90°, +90°]` |

---

## Paso 1 — Verificar Peter Corke Robotics Toolbox (RTB10) en MATLAB R2024b
Abre MATLAB y ejecuta en la *Command Window*:
```matlab
exist('SerialLink', 'class')
```
* Si devuelve **`8`**: ¡ya la tienes lista!
* Si devuelve **`0`**:
  1. Abre **Home → Add-Ons → Get Add-Ons** en MATLAB y busca **"Robotics Toolbox for MATLAB"** (de *Peter Corke*), o descarga `RTB-10.4.mltbx` desde https://petercorke.com/toolboxes/robotics-toolbox/ y haz doble clic sobre el archivo `.mltbx` para instalarlo en 1 paso.
  2. Si la instalaste manualmente como carpeta `rvctools`, ejecuta `startup_rvc` antes de correr los scripts.

---

## Paso 2 — Ejecutar la Demo Completa de Cinemática y Proyecciones
```matlab
cd('<ruta-al-repositorio>/matlab')
demo_cinematica_y_proyecciones
```
Esto imprime la tabla DH, valida FK vs. IK (error `< 1e-12`), abre las **4 figuras** (Modelo 3D, Workspace + Proyecciones `XY/XZ/YZ`, Trayectoria `jtraj` con `q / q̇ / q̈` y Trayectoria Cartesiana Rectilínea + Manipulabilidad) y las guarda automáticamente en `docs/graficas_matlab/`.

---

## Paso 3 — Probar el Gemelo Digital Sincronizado (`MATLAB → ESP32`)
```matlab
control_serial_esp32
```
* Con `DRY_RUN = true` (valor por defecto): corre la animación 3D en vivo en MATLAB sin necesitar el ESP32 conectado.
* En la **Semana 3–4**, al conectar tu ESP32 por USB, cambia `DRY_RUN = false` y pon tu puerto `COM` real (`COM3`, `COM5`, etc.) para mover el brazo físico sincronizado al milisegundo con Peter Corke.
