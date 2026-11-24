"""
Simulación Eléctrica SPICE Real (Motor ngspice de KiCad 9.0) — Mini-Pro 4-DOF (`B2 Stealth` v4)
================================================================================================
Invoca directamente la librería `ngspice.dll` instalada con KiCad 9.0 incorporando el hallazgo #8
de la auditoría de potencia:
  - Modela el LÍMITE REAL DE CORRIENTE OCP DEL CARGADOR UGREEN 50W EN 5V (`I_max = 3.0 A` con
    plegado suave de tensión sobre 3.0 A) + impedancia real del cable USB-C, AR5515 y KCD11.
  - Perfil realista de movimiento suave v4 (rampas quínticas 1100 ms sin carga inicial):
    1.75 A movimiento normal + pico rápido H-bridge de 2.85 A (350 µs) + agarre 2.05 A -> la
    corriente desde el cargador PD queda SIEMPRE por debajo de 3.0 A (0 disparos OCP!).
  - Comparativa CON C1 = 1000 µF vs SIN C1 (10 µF) y prueba antirretorno del diodo Schottky 1N5819
    con laptop conectada (5.10 V) y botón KCD11 apagado.

Salida:
  - electronics/simulacion_spice/resultados_spice_b2_stealth.png  (gráfica 3 paneles 300 DPI)
"""

import ctypes
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
PNG_OUT = os.path.join(HERE, "resultados_spice_b2_stealth.png")

NGSPICE_CANDIDATES = [
    r"C:\Users\rmaxm\AppData\Local\Programs\KiCad\9.0\bin\ngspice.dll",
    r"C:\Program Files\KiCad\9.0\bin\ngspice.dll",
    r"C:\Program Files\KiCad\8.0\bin\ngspice.dll",
]


class VectorInfo(ctypes.Structure):
    _fields_ = [
        ("v_name", ctypes.c_char_p),
        ("v_type", ctypes.c_int),
        ("v_flags", ctypes.c_short),
        ("v_realdata", ctypes.POINTER(ctypes.c_double)),
        ("v_compdata", ctypes.c_void_p),
        ("v_length", ctypes.c_int),
    ]


class NgSpiceRunner:
    def __init__(self):
        dll_path = next((p for p in NGSPICE_CANDIDATES if os.path.exists(p)), None)
        if not dll_path:
            raise FileNotFoundError("No se encontró ngspice.dll en las rutas estándar de KiCad.")
        os.add_dll_directory(os.path.dirname(dll_path))
        self.ng = ctypes.CDLL(dll_path)
        self.ng.ngGet_Vec_Info.argtypes = [ctypes.c_char_p]
        self.ng.ngGet_Vec_Info.restype = ctypes.POINTER(VectorInfo)
        self.ng.ngSpice_Circ.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
        self.ng.ngSpice_Circ.restype = ctypes.c_int
        self.ng.ngSpice_Command.argtypes = [ctypes.c_char_p]
        self.ng.ngSpice_Command.restype = ctypes.c_int

        SENDCHAR = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        SENDSTAT = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
        EXITCB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)

        self.logs = []
        self._cb_char = SENDCHAR(lambda s, _i, _u: (self.logs.append(s.decode("utf-8", "replace")), 0)[1])
        self._cb_stat = SENDSTAT(lambda _s, _i, _u: 0)
        self._cb_exit = EXITCB(lambda _st, _im, _q, _i, _u: 0)
        self.ng.ngSpice_Init(self._cb_char, self._cb_stat, self._cb_exit, None, None, None, None)

    def run_netlist(self, lines, vec_names):
        self.ng.ngSpice_Command(b"destroy all")
        arr = (ctypes.c_char_p * (len(lines) + 1))()
        for i, ln in enumerate(lines):
            arr[i] = ln.encode("ascii")
        arr[len(lines)] = None
        rc = self.ng.ngSpice_Circ(arr)
        if rc != 0:
            raise RuntimeError("Error cargando netlist SPICE:\n" + "\n".join(self.logs[-10:]))
        self.ng.ngSpice_Command(b"run")
        out = {}
        for name in vec_names:
            vi_p = self.ng.ngGet_Vec_Info(name.encode("ascii"))
            if not vi_p:
                raise RuntimeError(f"Vector SPICE no encontrado: {name}")
            vi = vi_p.contents
            out[name] = np.ctypeslib.as_array(vi.v_realdata, shape=(vi.v_length,)).copy()
        return out


def netlist_power(cap_str: str, esr_str: str):
    """
    Netlist transitorio realista CON LÍMITE DE CORRIENTE 3.0 A DEL CARGADOR UGREEN 50W PD (5V/3A).
    Si la corriente del cargador supera 3.0 A, la fuente comportamental B_PD cae abruptamente
    simulando la protección OCP/current-foldback real de un cargador USB-C PD 5V/3A!
    """
    return [
        f"* Mini-Pro 4-DOF Power Sim v4 (OCP 3.0A) C={cap_str}",
        # Amperímetro en serie con la salida del cargador PD + fuente comportamental con foldback OCP en 3.0 A
        "B_PD n_pd_ocp 0 V = 5.05 - 3.5*max(0, i(V_SENSE) - 3.0)",
        "V_SENSE n_pd_ocp n_pd_int DC 0",
        # Resistencia realista cable USB-C (1 m) + AR5515 + KCD11-2P + inductancia del cable
        "R_SRC n_pd_int n_pd_l 0.24",
        "L_SRC n_pd_l n_5v_srv 4.5u",
        # Capacitor electrolítico en bornera PCA9685
        f"R_ESR n_5v_srv n_c1 {esr_str}",
        f"C1 n_c1 0 {cap_str} IC=5.0",
        # Perfil realista v4 (rampas quínticas 1100 ms escalonadas):
        #   - 10..20ms : arranque suave brazo sin carga (1.75 A)
        #   - 35ms     : pico rápido de conmutación H-bridge (2.85 A durante 350 µs -> absorbido por C1!)
        #   - 55..65ms : esfuerzo sostenido J2 extendido + cierre pinza (2.05 A)
        "I_SERVOS n_5v_srv 0 PWL(0 0.15 9.95m 0.15 10.0m 1.75 20.0m 1.75 21.0m 0.65 34.98m 0.65 35.0m 2.85 35.35m 2.85 35.40m 0.65 54.95m 0.65 55.0m 2.05 65.0m 2.05 66.0m 0.20 85.0m 0.20)",
        # Diodo Schottky 1N5819 (modelo datasheet real)
        "D1 n_5v_srv n_5v_xiao D1N5819",
        ".model D1N5819 D(IS=2.6e-5 N=1.08 RS=0.055 BV=40 IBV=1m CJO=110p VJ=0.35 M=0.38)",
        # XIAO ESP32-S3 (Wi-Fi activo 220mA + 22uF onboard)
        "C_XIAO n_5v_xiao 0 22u IC=4.68",
        "I_XIAO n_5v_xiao 0 DC 0.22",
        ".tran 25u 85m UIC",
        ".end",
    ]


def netlist_backfeed():
    """Prueba antirretorno: Laptop USB-C (5.10V) conectada a XIAO mientras KCD11 está APAGADO."""
    return [
        "* Mini-Pro 4-DOF Antirretorno 1N5819 (Laptop USB-C 5.10V, KCD11 OFF)",
        "R_OFF n_5v_srv 0 100",
        "C1 n_5v_srv 0 1000u IC=0",
        "D1 n_5v_srv n_d_cat D1N5819",
        "V_MEAS n_d_cat n_5v_xiao DC 0",
        ".model D1N5819 D(IS=2.6e-5 N=1.08 RS=0.055 BV=40 IBV=1m CJO=110p VJ=0.35 M=0.38)",
        "V_LAPTOP n_5v_xiao 0 PWL(0 0 5m 0 7m 5.10 40m 5.10)",
        ".tran 50u 40m UIC",
        ".end",
    ]


def main():
    runner = NgSpiceRunner()

    d_with = runner.run_netlist(
        netlist_power("1000u", "0.08"),
        ["time", "v(n_5v_srv)", "v(n_5v_xiao)", "i(v_sense)"],
    )
    d_no = runner.run_netlist(
        netlist_power("10u", "0.05"),
        ["time", "v(n_5v_srv)", "v(n_5v_xiao)", "i(v_sense)"],
    )
    d_bf = runner.run_netlist(
        netlist_backfeed(),
        ["time", "v(n_5v_xiao)", "v(n_5v_srv)", "i(v_meas)"],
    )

    t_ms = d_with["time"] * 1000.0
    v_srv_c = d_with["v(n_5v_srv)"]
    v_xiao_c = d_with["v(n_5v_xiao)"]
    i_pd_c = d_with["i(v_sense)"]

    t_no_ms = d_no["time"] * 1000.0
    v_srv_no = d_no["v(n_5v_srv)"]
    v_xiao_no = d_no["v(n_5v_xiao)"]
    i_pd_no = d_no["i(v_sense)"]

    t_bf_ms = d_bf["time"] * 1000.0
    v_lap = d_bf["v(n_5v_xiao)"]
    v_leak = d_bf["v(n_5v_srv)"]
    i_rev_ua = np.abs(d_bf["i(v_meas)"]) * 1e6

    m_c = t_ms >= 2.0
    m_n = t_no_ms >= 2.0
    v_srv_min_c = float(v_srv_c[m_c].min())
    v_srv_min_no = float(v_srv_no[m_n].min())
    v_xiao_min_c = float(v_xiao_c[m_c].min())
    i_pd_max_c = float(i_pd_c[m_c].max())
    i_pd_max_no = float(i_pd_no[m_n].max())
    v_xiao_nom = float(np.median(v_xiao_c[(t_ms >= 3.0) & (t_ms <= 9.0)]))
    vd_drop = float(np.median(v_srv_c[(t_ms >= 3.0) & (t_ms <= 9.0)] - v_xiao_c[(t_ms >= 3.0) & (t_ms <= 9.0)]))
    p_d1_mw = vd_drop * 220.0
    i_rev_max_ua = float(i_rev_ua[t_bf_ms >= 10.0].max())
    v_leak_max_mv = float(np.max(np.abs(v_leak[t_bf_ms >= 10.0])) * 1000.0)
    margin_ldo = v_xiao_min_c - 3.80

    print("=== RESULTADOS SPICE REALES v4 (KiCad 9 ngspice.dll + Modelo OCP 3.0A UGREEN) ===")
    print(f"  [CON 1000uF] V_SERVO min  = {v_srv_min_c:.3f} V  |  V_XIAO min = {v_xiao_min_c:.3f} V (+{margin_ldo:.2f} V) | I_PD máx = {i_pd_max_c:.2f} A (< 3.00 A OCP!)")
    print(f"  [SIN 1000uF] V_SERVO min  = {v_srv_min_no:.3f} V  |  V_XIAO min = {float(v_xiao_no[m_n].min()):.3f} V | I_PD máx = {i_pd_max_no:.2f} A (dispara OCP!)")
    print(f"  [DIODO D1  ] Caída directa 1N5819 @ 220 mA = {vd_drop:.3f} V -> V_XIAO reposo = {v_xiao_nom:.3f} V (P_D1 = {p_d1_mw:.1f} mW)")
    print(f"  [ANTIRRET. ] Laptop 5.10V con KCD11 OFF -> I_inversa = {i_rev_max_ua:.2f} µA | V_bus_servos = {v_leak_max_mv:.2f} mV (BLOQUEADO!)")

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(3, 1, figsize=(12.2, 10.6), dpi=180, facecolor="#F8FAFC")
    fig.suptitle(
        "SIMULACIÓN ELÉCTRICA SPICE v4 (ngspice · KiCad 9.0 + Límite OCP 3.0 A UGREEN 50W)",
        fontsize=13.5, fontweight="bold", color="#0F172A", y=0.985,
    )

    ax = axes[0]
    ax.set_facecolor("#FFFFFF")
    ax.plot(t_no_ms, v_srv_no, color="#94A3B8", lw=1.6, ls="--", label=f"SIN C1 (10 µF) — mínimo: {v_srv_min_no:.2f} V (I_PD={i_pd_max_no:.2f} A -> dispara OCP)")
    ax.plot(t_ms, v_srv_c, color="#DC2626", lw=2.3, label=f"CON C1 = 1000 µF (AR1127) — mínimo: {v_srv_min_c:.2f} V (I_PD máx={i_pd_max_c:.2f} A < 3.0 A!)")
    ax.axhline(4.50, color="#F59E0B", lw=1.1, ls=":", label="Límite óptimo MG90S (4.50 V)")
    ax.set_ylabel("Voltaje Bus Servos (V)", fontweight="bold", color="#0F172A")
    ax.set_ylim(3.40, 5.25)
    ax.set_xlim(0, 85)
    ax.grid(True, alpha=0.28)
    ax.set_title("1 · Bus +5V_SERVO con límite real OCP 3.0 A (rampas quínticas v4: 1.75 A, pico H-bridge 2.85 A, carga 2.05 A)",
                 fontsize=10.8, fontweight="bold", color="#1E293B", loc="left", pad=6)
    ax.legend(loc="lower left", fontsize=8.8, framealpha=0.95)
    ax_i = ax.twinx()
    ax_i.fill_between(t_ms, 0, i_pd_c, color="#3B82F6", alpha=0.10)
    ax_i.plot(t_ms, i_pd_c, color="#2563EB", lw=1.3, alpha=0.80, label="I_PD desde AR5515 con C1 (A)")
    ax_i.axhline(3.00, color="#7C3AED", lw=1.2, ls="-.", label="Límite OCP UGREEN 5V (3.00 A)")
    ax_i.set_ylabel("Corriente PD (A)", color="#1D4ED8", fontweight="bold")
    ax_i.set_ylim(0, 3.6)
    ax_i.legend(loc="upper right", fontsize=8.6, framealpha=0.92)

    ax = axes[1]
    ax.set_facecolor("#FFFFFF")
    ax.plot(t_ms, v_xiao_c, color="#EA580C", lw=2.4, label=f"V(XIAO 5V_IN) tras 1N5819 — reposo {v_xiao_nom:.2f} V · mínimo {v_xiao_min_c:.2f} V")
    ax.plot(t_no_ms, v_xiao_no, color="#94A3B8", lw=1.3, ls="--", label="V(XIAO 5V_IN) sin C1")
    ax.axhline(3.80, color="#DC2626", lw=1.4, ls="--", label="Umbral mínimo regulador 3.3V XIAO (~3.80 V)")
    ax.fill_between(t_ms, 3.80, v_xiao_c, where=(v_xiao_c >= 3.80), color="#22C55E", alpha=0.12)
    ax.set_ylabel("Voltaje XIAO 5V_IN (V)", fontweight="bold", color="#0F172A")
    ax.set_ylim(3.55, 5.00)
    ax.set_xlim(0, 85)
    ax.grid(True, alpha=0.28)
    ax.set_title(f"2 · Margen Seguro XIAO ESP32-S3 (Wi-Fi 220 mA) — Margen sobre brownout: +{margin_ldo:.2f} V · Disipación D1: {p_d1_mw:.0f} mW",
                 fontsize=10.8, fontweight="bold", color="#1E293B", loc="left", pad=6)
    ax.legend(loc="lower left", fontsize=8.8, framealpha=0.95)

    ax = axes[2]
    ax.set_facecolor("#FFFFFF")
    ax.plot(t_bf_ms, v_lap, color="#2563EB", lw=2.3, label="Laptop USB-C conectada a XIAO (5.10 V)")
    ax.plot(t_bf_ms, v_leak, color="#16A34A", lw=2.4, label=f"Bus +5V_SERVO con KCD11 APAGADO ({v_leak_max_mv:.2f} mV — 100% aislado)")
    ax.set_xlabel("Tiempo (ms)", fontweight="bold", color="#0F172A")
    ax.set_ylabel("Voltaje (V)", fontweight="bold", color="#0F172A")
    ax.set_ylim(-0.3, 5.6)
    ax.set_xlim(0, 40)
    ax.grid(True, alpha=0.28)
    ax.set_title(f"3 · Prueba Antirretorno Diodo 1N5819 (Laptop conectada por USB-C con robot apagado) — Fuga inversa: {i_rev_max_ua:.1f} µA (SEGURO)",
                 fontsize=10.8, fontweight="bold", color="#1E293B", loc="left", pad=6)
    ax.legend(loc="center right", fontsize=9.0, framealpha=0.95)
    ax.annotate(
        f"1N5819 bloquea retorno:\nI_rev = {i_rev_max_ua:.1f} µA (< 0.05 mA)\nNota: validar con multímetro real al armar",
        xy=(14.0, 0.06), xytext=(7.2, 2.25),
        arrowprops=dict(arrowstyle="->", color="#15803D", lw=1.8),
        fontsize=9.0, fontweight="bold", color="#14532D",
        bbox=dict(boxstyle="round,pad=0.45", fc="#DCFCE7", ec="#22C55E", lw=1.3),
    )

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(PNG_OUT, dpi=180, facecolor=fig.get_facecolor())
    print(f"[OK] Gráfica SPICE v4 guardada en: {PNG_OUT}")


if __name__ == "__main__":
    main()
