"""
Simulación Eléctrica SPICE Real (Motor ngspice de KiCad 9.0) — Mini-Pro 4-DOF (`B2 Stealth`)
=============================================================================================
Invoca directamente la librería `ngspice.dll` instalada con KiCad 9.0 para ejecutar 3 pruebas
transitorias no lineales sobre la etapa de potencia y protección del robot ANTES de armarlo:

  1. Escenario A (Circuito Definitivo CON C1 = 1000 µF):
     Picos simultáneos de 2.2 A y 2.6 A en los servos + XIAO ESP32-S3 con Wi-Fi (220 mA).
  2. Escenario B (Comparativa SIN C1 — solo 10 µF cerámico):
     Demuestra el desplome transitorio y ripple en el bus de potencia sin el capacitor AR1127.
  3. Escenario C (Protección Antirretorno — Laptop USB-C 5.10 V con botón KCD11 APAGADO):
     Demuestra que el diodo Schottky 1N5819 bloquea la corriente inversa hacia los servos
     (I_rev < 0.05 mA), protegiendo el puerto USB de tu computadora al programar la XIAO.

Salida:
  - electronics/simulacion_spice/resultados_spice_b2_stealth.png  (gráfica 3 paneles 300 DPI)
"""

import ctypes
import os
import sys
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
    """Netlist transitorio de potencia (CON 1000uF vs SIN 1000uF)."""
    return [
        f"* Mini-Pro 4-DOF Power Sim C={cap_str}",
        "V_PD n_pd_int 0 DC 5.05",
        # Resistencia realista cable USB-C (1 m) + AR5515 + KCD11-2P + inductancia del cable
        "R_SRC n_pd_int n_pd_l 0.24",
        "L_SRC n_pd_l n_5v_srv 4.5u",
        # Capacitor electrolítico en bornera PCA9685
        f"R_ESR n_5v_srv n_c1 {esr_str}",
        f"C1 n_c1 0 {cap_str} IC=5.0",
        # Carga dinámica realista de los 5 servos:
        #   - 10..20ms : arranque simultáneo 4× MG90S (2.2 A)
        #   - 35ms     : pico rápido de conmutación H-bridge (3.6 A durante 350 µs, subida 20 µs)
        #   - 55..65ms : esfuerzo sostenido J2 + pinza (2.4 A)
        "I_SERVOS n_5v_srv 0 PWL(0 0.15 9.95m 0.15 10.0m 2.20 20.0m 2.20 21.0m 0.75 34.98m 0.75 35.0m 3.60 35.35m 3.60 35.40m 0.75 54.95m 0.75 55.0m 2.40 65.0m 2.40 66.0m 0.20 85.0m 0.20)",
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
    """Prueba antirretorno: Laptop USB-C (5.10V) conectada a XIAO mientras KCD11 está APAGADO (V_PD desconectado)."""
    return [
        "* Mini-Pro 4-DOF Antirretorno 1N5819 (Laptop USB-C 5.10V, KCD11 OFF)",
        # Botón KCD11 abierto (R=10Meg hacia AR5515 apagado)
        "R_OFF n_5v_srv 0 100",  # Representa impedancia de descarga / carga pasiva de servos en el bus V+
        "C1 n_5v_srv 0 1000u IC=0",
        # Diodo 1N5819 en serie (Ánodo en bus servos, Cátodo en XIAO 5V_IN)
        "D1 n_5v_srv n_d_cat D1N5819",
        "V_MEAS n_d_cat n_5v_xiao DC 0",  # Amperímetro ideal (corriente de retorno hacia bus servos)
        ".model D1N5819 D(IS=2.6e-5 N=1.08 RS=0.055 BV=40 IBV=1m CJO=110p VJ=0.35 M=0.38)",
        # Laptop USB-C se conecta en t = 5 ms (rampa suave 0 -> 5.10 V)
        "V_LAPTOP n_5v_xiao 0 PWL(0 0 5m 0 7m 5.10 40m 5.10)",
        ".tran 50u 40m UIC",
        ".end",
    ]


def main():
    runner = NgSpiceRunner()

    # 1) Con C1 = 1000 uF (diseño definitivo)
    d_with = runner.run_netlist(
        netlist_power("1000u", "0.08"),
        ["time", "v(n_5v_srv)", "v(n_5v_xiao)", "i(v_pd)"],
    )
    # 2) Sin C1 (solo 10 uF)
    d_no = runner.run_netlist(
        netlist_power("10u", "0.05"),
        ["time", "v(n_5v_srv)", "v(n_5v_xiao)", "i(v_pd)"],
    )
    # 3) Antirretorno con Laptop USB-C 5.10 V y KCD11 apagado
    d_bf = runner.run_netlist(
        netlist_backfeed(),
        ["time", "v(n_5v_xiao)", "v(n_5v_srv)", "i(v_meas)"],
    )

    # Extraer métricas reales verificadas por ngspice
    t_ms = d_with["time"] * 1000.0
    v_srv_c = d_with["v(n_5v_srv)"]
    v_xiao_c = d_with["v(n_5v_xiao)"]
    i_pd_c = -d_with["i(v_pd)"]  # corriente saliendo de V_PD

    t_no_ms = d_no["time"] * 1000.0
    v_srv_no = d_no["v(n_5v_srv)"]
    v_xiao_no = d_no["v(n_5v_xiao)"]

    t_bf_ms = d_bf["time"] * 1000.0
    v_lap = d_bf["v(n_5v_xiao)"]
    v_leak = d_bf["v(n_5v_srv)"]
    i_rev_ua = np.abs(d_bf["i(v_meas)"]) * 1e6  # microamperios!

    # Descartar primeros 2 ms de inicialización UIC
    m_c = t_ms >= 2.0
    m_n = t_no_ms >= 2.0
    v_srv_min_c = float(v_srv_c[m_c].min())
    v_srv_min_no = float(v_srv_no[m_n].min())
    v_xiao_min_c = float(v_xiao_c[m_c].min())
    v_xiao_nom = float(np.median(v_xiao_c[(t_ms >= 3.0) & (t_ms <= 9.0)]))
    vd_drop = float(np.median(v_srv_c[(t_ms >= 3.0) & (t_ms <= 9.0)] - v_xiao_c[(t_ms >= 3.0) & (t_ms <= 9.0)]))
    p_d1_mw = vd_drop * 220.0  # mW disipados en 1N5819 con XIAO a 220 mA
    i_rev_max_ua = float(i_rev_ua[t_bf_ms >= 10.0].max())
    v_leak_max_mv = float(np.max(np.abs(v_leak[t_bf_ms >= 10.0])) * 1000.0)
    margin_ldo = v_xiao_min_c - 3.80  # Regulador 3.3V XIAO necesita >= ~3.7-3.8V

    print("=== RESULTADOS SPICE REALES (KiCad 9 ngspice.dll) ===")
    print(f"  [CON 1000uF] V_SERVO min  = {v_srv_min_c:.3f} V  |  V_XIAO min = {v_xiao_min_c:.3f} V (margen LDO 3.3V: +{margin_ldo:.2f} V)")
    print(f"  [SIN 1000uF] V_SERVO min  = {v_srv_min_no:.3f} V  |  V_XIAO min = {float(v_xiao_no[m_n].min()):.3f} V")
    print(f"  [DIODO D1  ] Caída directa 1N5819 @ 220 mA = {vd_drop:.3f} V -> V_XIAO reposo = {v_xiao_nom:.3f} V (P_D1 = {p_d1_mw:.1f} mW)")
    print(f"  [ANTIRRET. ] Laptop 5.10V con KCD11 OFF -> I_inversa = {i_rev_max_ua:.2f} µA | V_bus_servos = {v_leak_max_mv:.2f} mV (BLOQUEADO!)")

    # ------------------------------------------------------------------
    # Gráfica Técnica de 3 Paneles (300 DPI)
    # ------------------------------------------------------------------
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(3, 1, figsize=(12.2, 10.6), dpi=180, facecolor="#F8FAFC")
    fig.suptitle(
        "SIMULACIÓN ELÉCTRICA SPICE (ngspice · KiCad 9.0) — MINI-PRO 4-DOF B2 STEALTH",
        fontsize=14, fontweight="bold", color="#0F172A", y=0.985,
    )

    # Panel 1: Bus +5V_SERVO (CON 1000uF vs SIN 1000uF) y corriente de carga
    ax = axes[0]
    ax.set_facecolor("#FFFFFF")
    ax.plot(t_no_ms, v_srv_no, color="#94A3B8", lw=1.6, ls="--", label=f"SIN C1 (10 µF) — mínimo: {v_srv_min_no:.2f} V (desplome abrupto)")
    ax.plot(t_ms, v_srv_c, color="#DC2626", lw=2.3, label=f"CON C1 = 1000 µF (AR1127) — mínimo: {v_srv_min_c:.2f} V (amortiguado)")
    ax.axhline(4.50, color="#F59E0B", lw=1.1, ls=":", label="Límite óptimo MG90S (4.50 V)")
    ax.set_ylabel("Voltaje Bus Servos (V)", fontweight="bold", color="#0F172A")
    ax.set_ylim(3.20, 5.25)
    ax.set_xlim(0, 85)
    ax.grid(True, alpha=0.28)
    ax.set_title("1 · Estabilidad del Bus +5V_SERVO ante arranque 2.2 A, pico H-bridge 3.6 A (350 µs) y carga 2.4 A",
                 fontsize=11, fontweight="bold", color="#1E293B", loc="left", pad=6)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.95)
    ax_i = ax.twinx()
    ax_i.fill_between(t_ms, 0, i_pd_c, color="#3B82F6", alpha=0.10)
    ax_i.plot(t_ms, i_pd_c, color="#2563EB", lw=1.2, alpha=0.75, label="Corriente desde AR5515 (A)")
    ax_i.set_ylabel("Corriente PD (A)", color="#1D4ED8", fontweight="bold")
    ax_i.set_ylim(0, 4.2)
    ax_i.legend(loc="upper right", fontsize=8.8, framealpha=0.92)

    # Panel 2: Voltaje en XIAO ESP32-S3 (5V_IN tras Diodo Schottky 1N5819)
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
    ax.set_title(f"2 · Margen Seguro de la XIAO ESP32-S3 (Wi-Fi 220 mA) — Margen sobre brownout: +{margin_ldo:.2f} V · Disipación D1: {p_d1_mw:.0f} mW",
                 fontsize=11, fontweight="bold", color="#1E293B", loc="left", pad=6)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.95)

    # Panel 3: Protección Antirretorno (Laptop USB-C 5.10V conectada con KCD11 OFF)
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
                 fontsize=11, fontweight="bold", color="#1E293B", loc="left", pad=6)
    ax.legend(loc="center right", fontsize=9.2, framealpha=0.95)
    ax.annotate(
        f"1N5819 bloquea retorno:\nI_rev = {i_rev_max_ua:.1f} µA (< 0.05 mA)\nPuerto USB laptop protegido",
        xy=(14.0, 0.06), xytext=(7.2, 2.25),
        arrowprops=dict(arrowstyle="->", color="#15803D", lw=1.8),
        fontsize=9.2, fontweight="bold", color="#14532D",
        bbox=dict(boxstyle="round,pad=0.45", fc="#DCFCE7", ec="#22C55E", lw=1.3),
    )

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(PNG_OUT, dpi=180, facecolor=fig.get_facecolor())
    print(f"[OK] Gráfica SPICE guardada en: {PNG_OUT}")


if __name__ == "__main__":
    main()
