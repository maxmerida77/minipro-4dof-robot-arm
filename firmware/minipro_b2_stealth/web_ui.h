#pragma once
#include <Arduino.h>

// Interfaz Web Minimalista B2 Stealth (Blanco y Negro) servida directo desde XIAO ESP32-S3
static const char WEB_UI_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mini-Pro 4-DOF · B2 Stealth</title>
<style>
  :root { --bg:#0D0D0F; --card:#161619; --border:#2B2B30; --ink:#F4F4F5; --muted:#9A9AA3; --accent:#FFFFFF; }
  * { box-sizing:border-box; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  body { margin:0; background:var(--bg); color:var(--ink); display:flex; justify-content:center; padding:22px 14px; }
  .wrap { width:100%; max-width:460px; }
  header { display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; border-bottom:1px solid var(--border); padding-bottom:12px; }
  h1 { font-size:17px; letter-spacing:0.08em; margin:0; font-weight:700; text-transform:uppercase; }
  .pill { font-size:11px; padding:4px 10px; border:1px solid var(--border); border-radius:999px; color:var(--muted); }
  .card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:16px; margin-bottom:14px; }
  .row { margin-bottom:14px; }
  .row:last-child { margin-bottom:0; }
  .lbl { display:flex; justify-content:space-between; font-size:12px; color:var(--muted); margin-bottom:6px; }
  .val { color:var(--ink); font-weight:600; font-variant-numeric:tabular-nums; }
  input[type=range] { -webkit-appearance:none; width:100%; height:4px; background:#2E2E35; border-radius:99px; outline:none; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:18px; height:18px; border-radius:50%; background:var(--accent); border:2px solid var(--bg); cursor:pointer; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:9px; }
  button { background:#1F1F24; color:var(--ink); border:1px solid var(--border); border-radius:10px; padding:11px 10px; font-size:12px; font-weight:600; letter-spacing:0.03em; cursor:pointer; transition:all .15s; }
  button:hover { border-color:#FFFFFF; background:#27272D; }
  button.primary { background:#FFFFFF; color:#0D0D0F; border-color:#FFFFFF; }
  button.primary:hover { background:#E4E4E7; }
  button.danger { border-color:#52525B; color:#D4D4D8; }
  .foot { text-align:center; font-size:11px; color:var(--muted); margin-top:8px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Mini-Pro 4-DOF</h1>
      <div style="font-size:11px;color:var(--muted);margin-top:2px;">B2 STEALTH · XIAO ESP32 + PCA9685</div>
    </div>
    <span class="pill" id="st">CONECTADO</span>
  </header>

  <div class="card">
    <div class="row">
      <div class="lbl"><span>J1 · Base Yaw</span><span class="val" id="v0">0.0°</span></div>
      <input type="range" id="s0" min="-90" max="90" step="1" value="0">
    </div>
    <div class="row">
      <div class="lbl"><span>J2 · Hombro Pitch</span><span class="val" id="v1">68.0°</span></div>
      <input type="range" id="s1" min="15" max="165" step="1" value="68">
    </div>
    <div class="row">
      <div class="lbl"><span>J3 · Codo Pitch</span><span class="val" id="v2">-96.0°</span></div>
      <input type="range" id="s2" min="-135" max="45" step="1" value="-96">
    </div>
    <div class="row">
      <div class="lbl"><span>J4 · Muñeca 4.º Eje</span><span class="val" id="v3">28.0°</span></div>
      <input type="range" id="s3" min="-90" max="90" step="1" value="28">
    </div>
    <div class="row">
      <div class="lbl"><span>Pinza Paralela (SG90)</span><span class="val" id="v4">16 mm</span></div>
      <input type="range" id="s4" min="0" max="30" step="1" value="16">
    </div>
  </div>

  <div class="card">
    <div class="grid">
      <button class="primary" onclick="cmd('HERO')">Pose Héroe</button>
      <button onclick="cmd('HOME')">Home Vertical</button>
      <button onclick="cmd('DEMO')">Demo Pick &amp; Place</button>
      <button onclick="cmd('CENTER')">Centrar 90° (Banco)</button>
      <button class="danger" style="grid-column:span 2" onclick="cmd('RELAX')">Relajar Servos (Sin Torque)</button>
    </div>
  </div>

  <div class="foot" id="info">UDP Peter Corke activo en puerto 4210</div>
</div>
<script>
const ids = ['s0','s1','s2','s3','s4'];
let timer = null;
let dragging = false;
function fmt(i, v) { return i === 4 ? `${v} mm` : `${Number(v).toFixed(1)}°`; }
function updateLabels() {
  ids.forEach((id, i) => document.getElementById('v'+i).textContent = fmt(i, document.getElementById(id).value));
}
function sendMove() {
  const q = ids.map(id => document.getElementById(id).value);
  fetch(`/api/move?q0=${q[0]}&q1=${q[1]}&q2=${q[2]}&q3=${q[3]}&g=${q[4]}`).catch(()=>{});
}
ids.forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('pointerdown', () => { dragging = true; });
  el.addEventListener('pointerup', () => { dragging = false; });
  el.addEventListener('pointercancel', () => { dragging = false; });
  el.addEventListener('input', () => {
    updateLabels();
    clearTimeout(timer);
    timer = setTimeout(sendMove, 35);
  });
});
function cmd(name) {
  document.getElementById('st').textContent = name;
  fetch(`/api/cmd?c=${name}`).then(r => r.json()).then(sync).catch(()=>{});
}
function sync(d) {
  if (!d || !d.q || dragging) return;
  d.q.forEach((val, i) => { document.getElementById('s'+i).value = Math.round(val); });
  updateLabels();
  document.getElementById('st').textContent = d.relaxed ? 'RELAJADO' : 'ACTIVO';
  if (d.ip) document.getElementById('info').textContent = `IP: ${d.ip} · UDP Peter Corke puerto 4210`;
}
fetch('/api/status').then(r => r.json()).then(sync).catch(()=>{});
setInterval(() => fetch('/api/status').then(r => r.json()).then(sync).catch(()=>{}), 2500);
</script>
</body>
</html>
)rawliteral";
