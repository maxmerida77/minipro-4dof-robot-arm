#pragma once
#include <Arduino.h>

// Interfaz Web Minimalista B2 Stealth (FK + IK en vivo) servida directo desde XIAO ESP32-S3
static const char WEB_UI_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mini-Pro 4-DOF · B2 Stealth (FK + IK)</title>
<style>
  :root { --bg:#0D0D0F; --card:#161619; --border:#2B2B30; --ink:#F4F4F5; --muted:#9A9AA3; --accent:#FFFFFF; --ok:#22C55E; --warn:#F97316; }
  * { box-sizing:border-box; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  body { margin:0; background:var(--bg); color:var(--ink); display:flex; justify-content:center; padding:18px 14px; }
  .wrap { width:100%; max-width:480px; }
  header { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid var(--border); padding-bottom:12px; }
  h1 { font-size:17px; letter-spacing:0.08em; margin:0; font-weight:700; text-transform:uppercase; }
  .pill { font-size:11px; padding:4px 10px; border:1px solid var(--border); border-radius:999px; color:var(--muted); }
  .pill.err { border-color:var(--warn); color:var(--warn); }
  .card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:14px 16px; margin-bottom:12px; }
  .tel { display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:12px; font-variant-numeric:tabular-nums; }
  .tel-box { background:#111114; border:1px solid #232329; border-radius:10px; padding:8px 10px; }
  .tel-k { font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:3px; }
  .tel-v { font-size:13px; font-weight:700; color:var(--ink); }
  .tabs { display:grid; grid-template-columns:1fr 1fr; gap:6px; background:#111114; padding:4px; border-radius:12px; border:1px solid var(--border); margin-bottom:12px; }
  .tab { background:transparent; color:var(--muted); border:none; border-radius:9px; padding:9px; font-size:12px; font-weight:700; cursor:pointer; }
  .tab.active { background:#FFFFFF; color:#0D0D0F; }
  .row { margin-bottom:13px; }
  .row:last-child { margin-bottom:0; }
  .lbl { display:flex; justify-content:space-between; font-size:12px; color:var(--muted); margin-bottom:5px; }
  .val { color:var(--ink); font-weight:600; font-variant-numeric:tabular-nums; }
  input[type=range] { -webkit-appearance:none; width:100%; height:4px; background:#2E2E35; border-radius:99px; outline:none; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:18px; height:18px; border-radius:50%; background:var(--accent); border:2px solid var(--bg); cursor:pointer; }
  .num-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin-top:12px; }
  .num-grid label { display:flex; flex-direction:column; font-size:10px; color:var(--muted); gap:4px; }
  .num-grid input { background:#101013; color:var(--ink); border:1px solid var(--border); border-radius:8px; padding:7px 6px; font-size:13px; font-weight:600; width:100%; text-align:center; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  button { background:#1F1F24; color:var(--ink); border:1px solid var(--border); border-radius:10px; padding:10px; font-size:12px; font-weight:600; letter-spacing:0.03em; cursor:pointer; transition:all .15s; }
  button:hover { border-color:#FFFFFF; background:#27272D; }
  button.primary { background:#FFFFFF; color:#0D0D0F; border-color:#FFFFFF; }
  button.primary:hover { background:#E4E4E7; }
  button.danger { border-color:#52525B; color:#D4D4D8; }
  .msg { font-size:11px; color:var(--muted); margin-top:8px; text-align:center; min-height:16px; }
  .msg.err { color:var(--warn); font-weight:600; }
  .hidden { display:none; }
  .foot { text-align:center; font-size:11px; color:var(--muted); margin-top:6px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Mini-Pro 4-DOF</h1>
      <div style="font-size:11px;color:var(--muted);margin-top:2px;">B2 STEALTH v4 · FK + IK ANALÍTICA</div>
    </div>
    <span class="pill" id="st">CONECTADO</span>
  </header>

  <div class="card">
    <div class="tel">
      <div class="tel-box">
        <div class="tel-k">TCP DH (a₄ = 53 mm)</div>
        <div class="tel-v" id="tel-xyz">145.5, 0.0, 125.2</div>
      </div>
      <div class="tel-box">
        <div class="tel-k">Agarre w04 (+5.8 mm)</div>
        <div class="tel-v" id="tel-grip">145.5, 0.0, 131.0</div>
      </div>
      <div class="tel-box" style="grid-column:span 2">
        <div class="tel-k">Articulaciones (J1..J4)</div>
        <div class="tel-v" id="tel-q">0°, 68°, -96°, 28°</div>
      </div>
    </div>
    <div class="msg" id="msg">Listo (Cinemática Directa e Inversa a bordo)</div>
  </div>

  <div class="tabs">
    <button class="tab active" id="tab-fk" onclick="setMode('fk')">Directa · FK (J1..J4)</button>
    <button class="tab" id="tab-ik" onclick="setMode('ik')">Inversa · IK (X, Y, Z, φ)</button>
  </div>

  <!-- PANEL CINEMÁTICA DIRECTA (FK) -->
  <div class="card" id="panel-fk">
    <div class="row">
      <div class="lbl"><span>J1 · Base Yaw</span><span class="val" id="v0">0.0°</span></div>
      <input type="range" id="s0" min="-85" max="85" step="1" value="0">
    </div>
    <div class="row">
      <div class="lbl"><span>J2 · Hombro Pitch</span><span class="val" id="v1">68.0°</span></div>
      <input type="range" id="s1" min="22" max="145" step="1" value="68">
    </div>
    <div class="row">
      <div class="lbl"><span>J3 · Codo Pitch</span><span class="val" id="v2">-96.0°</span></div>
      <input type="range" id="s2" min="-125" max="20" step="1" value="-96">
    </div>
    <div class="row">
      <div class="lbl"><span>J4 · Muñeca Pitch</span><span class="val" id="v3">28.0°</span></div>
      <input type="range" id="s3" min="-80" max="80" step="1" value="28">
    </div>
  </div>

  <!-- PANEL CINEMÁTICA INVERSA (IK) -->
  <div class="card hidden" id="panel-ik">
    <div class="tabs" style="margin-bottom:10px">
      <button class="tab active" id="ik-ref-tcp" onclick="setIkRef('tcp')">Objetivo: TCP DH (a₄=53)</button>
      <button class="tab" id="ik-ref-grip" onclick="setIkRef('grip')">Objetivo: Agarre w04 (+5.8)</button>
    </div>
    <div class="row">
      <div class="lbl"><span>X · Alcance Frontal (mm)</span><span class="val" id="vx">145.5 mm</span></div>
      <input type="range" id="sx" min="35" max="199" step="1" value="146">
    </div>
    <div class="row">
      <div class="lbl"><span>Y · Desplazamiento Lateral (mm)</span><span class="val" id="vy">0.0 mm</span></div>
      <input type="range" id="sy" min="-170" max="170" step="1" value="0">
    </div>
    <div class="row">
      <div class="lbl"><span>Z · Altura sobre Escritorio (mm)</span><span class="val" id="vz">125.2 mm</span></div>
      <input type="range" id="sz" min="12" max="260" step="1" value="125">
    </div>
    <div class="row">
      <div class="lbl"><span>φ · Inclinación Pinza (°)</span><span class="val" id="vp">0.0°</span></div>
      <input type="range" id="sp" min="-90" max="90" step="1" value="0">
    </div>
    <div class="num-grid">
      <label>X (mm)<input type="number" id="nx" value="145.5" step="1"></label>
      <label>Y (mm)<input type="number" id="ny" value="0" step="1"></label>
      <label>Z (mm)<input type="number" id="nz" value="125.2" step="1"></label>
      <label>φ (°)<input type="number" id="np" value="0" step="1"></label>
    </div>
    <button class="primary" style="width:100%;margin-top:10px" onclick="sendIKExact()">Ir suave a (X, Y, Z, φ) por IK</button>
  </div>

  <!-- PINZA PARALELA COMPARTIDA -->
  <div class="card">
    <div class="row">
      <div class="lbl"><span>Pinza Paralela MeArm 1.5 (SG90)</span><span class="val" id="v4">15 mm</span></div>
      <input type="range" id="s4" min="0" max="30" step="1" value="15">
    </div>
  </div>

  <div class="card">
    <div class="grid">
      <button class="primary" onclick="cmd('HERO')">Pose Héroe</button>
      <button onclick="cmd('HOME')">Home Vertical</button>
      <button onclick="cmd('DEMO')">Demo Pick &amp; Place</button>
      <button onclick="cmd('CENTER')">Centrar 90° (Banco)</button>
      <button class="danger" style="grid-column:span 2" onclick="cmd('RELAX')">Relajar Servos (FULL_OFF 4096)</button>
    </div>
  </div>

  <div class="foot" id="info">UDP Peter Corke activo en puerto 4210</div>
</div>
<script>
const fkIds = ['s0','s1','s2','s3','s4'];
const ikIds = ['sx','sy','sz','sp'];
let mode = 'fk';
let ikRef = 'tcp';
let lastStatus = null;
let timer = null;
let dragging = false;

function setIkRef(ref) {
  ikRef = ref;
  document.getElementById('ik-ref-tcp').classList.toggle('active', ref === 'tcp');
  document.getElementById('ik-ref-grip').classList.toggle('active', ref === 'grip');
  if (lastStatus) {
    const src = (ref === 'grip' && lastStatus.grip_xyz) ? lastStatus.grip_xyz : lastStatus.xyz;
    if (src) {
      document.getElementById('sx').value = Math.round(src[0]);
      document.getElementById('sy').value = Math.round(src[1]);
      document.getElementById('sz').value = Math.round(src[2]);
      if (lastStatus.xyz) document.getElementById('sp').value = Math.round(lastStatus.xyz[3]);
      updateIkLabels(true);
    }
  }
}

function setMode(m) {
  mode = m;
  document.getElementById('tab-fk').classList.toggle('active', m === 'fk');
  document.getElementById('tab-ik').classList.toggle('active', m === 'ik');
  document.getElementById('panel-fk').classList.toggle('hidden', m !== 'fk');
  document.getElementById('panel-ik').classList.toggle('hidden', m !== 'ik');
}

function updateFkLabels() {
  fkIds.forEach((id, i) => {
    const v = Number(document.getElementById(id).value);
    document.getElementById('v'+i).textContent = i === 4 ? `${v.toFixed(0)} mm` : `${v.toFixed(1)}°`;
  });
}

function updateIkLabels(syncInputs = true) {
  const x = Number(document.getElementById('sx').value);
  const y = Number(document.getElementById('sy').value);
  const z = Number(document.getElementById('sz').value);
  const p = Number(document.getElementById('sp').value);
  document.getElementById('vx').textContent = `${x.toFixed(1)} mm`;
  document.getElementById('vy').textContent = `${y.toFixed(1)} mm`;
  document.getElementById('vz').textContent = `${z.toFixed(1)} mm`;
  document.getElementById('vp').textContent = `${p.toFixed(1)}°`;
  if (syncInputs) {
    document.getElementById('nx').value = x.toFixed(1);
    document.getElementById('ny').value = y.toFixed(1);
    document.getElementById('nz').value = z.toFixed(1);
    document.getElementById('np').value = p.toFixed(1);
  }
}

function sendFK() {
  const q = fkIds.map(id => document.getElementById(id).value);
  fetch(`/api/move?q0=${q[0]}&q1=${q[1]}&q2=${q[2]}&q3=${q[3]}&g=${q[4]}`).then(r => r.json()).then(sync).catch(()=>{});
}

function sendIKStream() {
  const x = document.getElementById('sx').value;
  const y = document.getElementById('sy').value;
  const z = document.getElementById('sz').value;
  const p = document.getElementById('sp').value;
  const g = document.getElementById('s4').value;
  fetch(`/api/ik?x=${x}&y=${y}&z=${z}&phi=${p}&g=${g}&mode=${ikRef}&stream=1`).then(r => r.json()).then(sync).catch(()=>{});
}

function sendIKExact() {
  const x = document.getElementById('nx').value;
  const y = document.getElementById('ny').value;
  const z = document.getElementById('nz').value;
  const p = document.getElementById('np').value;
  const g = document.getElementById('s4').value;
  fetch(`/api/ik?x=${x}&y=${y}&z=${z}&phi=${p}&g=${g}&mode=${ikRef}&ms=1100`).then(r => r.json()).then(sync).catch(()=>{});
}

fkIds.forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('pointerdown', () => { dragging = true; });
  el.addEventListener('pointerup', () => { dragging = false; });
  el.addEventListener('pointercancel', () => { dragging = false; });
  el.addEventListener('input', () => {
    updateFkLabels();
    clearTimeout(timer);
    timer = setTimeout(sendFK, 35);
  });
});

ikIds.forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('pointerdown', () => { dragging = true; });
  el.addEventListener('pointerup', () => { dragging = false; });
  el.addEventListener('pointercancel', () => { dragging = false; });
  el.addEventListener('input', () => {
    updateIkLabels(true);
    clearTimeout(timer);
    timer = setTimeout(sendIKStream, 40);
  });
});

function cmd(name) {
  document.getElementById('st').textContent = name;
  fetch(`/api/cmd?c=${name}`).then(r => r.json()).then(sync).catch(()=>{});
}

function sync(d) {
  if (!d || !d.q) return;
  lastStatus = d;
  const mEl = document.getElementById('msg');
  if (d.msg) { mEl.textContent = d.msg; mEl.classList.toggle('err', d.ok === false); }
  const stEl = document.getElementById('st');
  stEl.textContent = d.relaxed ? 'RELAJADO' : (d.waking ? 'REACTIVANDO' : (d.ok === false ? 'FUERA LIM' : 'ACTIVO'));
  stEl.classList.toggle('err', d.ok === false);
  document.getElementById('tel-q').textContent = `${d.q[0].toFixed(0)}°, ${d.q[1].toFixed(0)}°, ${d.q[2].toFixed(0)}°, ${d.q[3].toFixed(0)}°`;
  if (d.xyz) {
    document.getElementById('tel-xyz').textContent = `${d.xyz[0].toFixed(1)}, ${d.xyz[1].toFixed(1)}, ${d.xyz[2].toFixed(1)} · φ=${d.xyz[3].toFixed(0)}°`;
  }
  if (d.grip_xyz) {
    document.getElementById('tel-grip').textContent = `${d.grip_xyz[0].toFixed(1)}, ${d.grip_xyz[1].toFixed(1)}, ${d.grip_xyz[2].toFixed(1)} mm`;
  }
  if (!dragging) {
    d.q.forEach((val, i) => { document.getElementById('s'+i).value = Math.round(val); });
    updateFkLabels();
    const src = (ikRef === 'grip' && d.grip_xyz) ? d.grip_xyz : d.xyz;
    if (src && mode === 'fk') {
      document.getElementById('sx').value = Math.round(src[0]);
      document.getElementById('sy').value = Math.round(src[1]);
      document.getElementById('sz').value = Math.round(src[2]);
      if (d.xyz) document.getElementById('sp').value = Math.round(d.xyz[3]);
      updateIkLabels(true);
    }
  }
  if (d.ip) document.getElementById('info').textContent = `IP: ${d.ip} · Serial/UDP: FK, G, M, IK, IKGRIP`;
}
fetch('/api/status').then(r => r.json()).then(sync).catch(()=>{});
setInterval(() => fetch('/api/status').then(r => r.json()).then(sync).catch(()=>{}), 2500);
</script>
</body>
</html>
)rawliteral";
