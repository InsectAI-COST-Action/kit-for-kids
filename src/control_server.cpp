#include "control_server.h"

#include <WiFi.h>

namespace {
// Placeholder only. docs/device-control-app-plan.md Phase 5 replaces this
// with a per-device password (e.g. printed on the enclosure's QR code).
constexpr const char* kApPasswordPlaceholder = "antcamera";

const char kControlAppHtml[] PROGMEM = R"HTML(<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your insect camera</title>
<style>
  :root { color-scheme: light; font-family: "Trebuchet MS", "Segoe UI", system-ui, sans-serif;
    --ink:#17324d; --muted:#557084; --cream:#fff8ed; --paper:#fff;
    --purple:#7356c7; --purple-dark:#4b318f; --teal:#087f82; --coral:#ef6f61; --coral-dark:#b34642;
    --green:#0f9d58; --green-dark:#0b7742; --shadow:0 10px 26px rgb(33 58 83/.12); }
  * { box-sizing:border-box; }
  body { margin:0; background:#e8eef0; color:var(--ink); display:flex; justify-content:center; padding:20px 12px 40px; }
  .phone { background:var(--cream); border-radius:26px; box-shadow:var(--shadow); overflow:hidden; width:100%; max-width:420px; }
  .bar { background:var(--purple); color:#fff; padding:16px 18px 14px; display:flex; align-items:center; gap:10px; }
  .bar-dot { width:.6rem; height:.6rem; border-radius:50%; background:#8ef0a8; flex:none; }
  .bar-title { font-weight:900; font-size:.98rem; }
  .bar-sub { font-size:.74rem; opacity:.85; margin-left:auto; font-weight:700; }
  .screen { padding:16px; display:grid; gap:12px; }
  .hero-card { background:linear-gradient(150deg,#7356c7,#5a3fae); color:#fff; border-radius:1.3rem; padding:18px; }
  .hero-eyebrow { font-size:.68rem; font-weight:900; letter-spacing:.14em; text-transform:uppercase; color:#f0e2ff; margin:0 0 6px; }
  .hero-count { font-size:2.9rem; font-weight:900; line-height:1; margin:0; }
  .hero-count small { font-size:.95rem; font-weight:800; opacity:.9; }
  .hero-time { margin:8px 0 0; font-size:.84rem; opacity:.92; }
  .note-card { background:var(--paper); border-radius:1.3rem; padding:15px 16px; box-shadow:var(--shadow); }
  .note-card h3 { margin:0 0 5px; font-size:.92rem; }
  .note-card p { margin:0; font-size:.8rem; color:var(--muted); line-height:1.55; }
  .offline-note { text-align:center; font-size:.72rem; color:#7a8b96; margin:4px 0 0; }
  button { font:inherit; cursor:pointer; border-radius:999px; font-weight:900; border:2px solid transparent;
    width:100%; padding:15px 18px; font-size:1rem; transition:transform .16s ease; }
  button:active { transform:translateY(2px); }
  button:disabled { opacity:.55; cursor:default; box-shadow:none; }
  .btn-finish { background:var(--coral); color:#fff; box-shadow:0 5px 0 var(--coral-dark); }
  .btn-again { background:var(--green); color:#fff; box-shadow:0 5px 0 var(--green-dark); max-width:19rem; margin:16px auto 0; }
  .finish-note { font-size:.74rem; color:var(--muted); text-align:center; margin:-4px 0 0; line-height:1.5; }
  .center-screen { flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center;
    text-align:center; padding:34px 22px; gap:6px; }
  .big-emoji { font-size:3.4rem; line-height:1; margin-bottom:4px; }
  .center-screen h2 { margin:0; font-size:1.5rem; letter-spacing:-.02em; }
  .center-screen p { margin:0; color:var(--muted); font-size:.88rem; line-height:1.6; max-width:28ch; }
  .safe-banner { background:var(--green); color:#fff; border-radius:1.2rem; padding:16px 18px; width:100%; max-width:19rem; margin-top:10px; }
  .safe-banner strong { display:block; font-size:1rem; margin-bottom:3px; }
  .safe-banner span { font-size:.8rem; opacity:.95; line-height:1.5; display:block; }
  .spinner { width:2.6rem; height:2.6rem; border-radius:50%; margin:6px 0 4px;
    border:.32rem solid #e3d9f5; border-top-color:var(--purple); animation:spin 0.9s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .spinner { animation:none; border-top-color:#e3d9f5; } }
  [hidden] { display:none !important; }
</style>
</head>
<body>
  <div class="phone">
    <div class="bar">
      <span class="bar-dot" id="dot" aria-hidden="true"></span>
      <span class="bar-title">Your insect camera</span>
      <span class="bar-sub" id="barSub">Connecting&hellip;</span>
    </div>

    <div class="screen" id="screenMain">
      <div class="hero-card">
        <p class="hero-eyebrow">Camera adventure</p>
        <p class="hero-count"><span id="shotCount">-</span> <small>pictures</small></p>
        <p class="hero-time" id="elapsed">Getting ready&hellip;</p>
      </div>
      <div class="note-card" id="noteCard">
        <h3>More coming soon</h3>
        <p>Taking a peek and changing settings from here are on the way. For now, this page shows what your camera is doing right now.</p>
      </div>
      <button class="btn-finish" id="btnFinish">&#x1F3C1; Finish my adventure</button>
      <p class="finish-note">Always finish here before you unplug &mdash; it makes sure every picture is saved properly.</p>
      <p class="offline-note">You're connected directly to the camera. There's no internet here &mdash; that's normal.</p>
    </div>

    <div class="center-screen" id="screenFinishing" hidden>
      <div class="big-emoji">&#x1F4E6;</div>
      <div class="spinner" role="status" aria-label="Working"></div>
      <h2>Packing up&hellip;</h2>
      <p>Making sure every picture is safely stored on the card. This can take a little while &mdash; please wait for the safe-to-unplug message before you disconnect the battery.</p>
    </div>

    <div class="center-screen" id="screenSafe" hidden>
      <div class="big-emoji">&#x1F389;</div>
      <h2>All done!</h2>
      <p>Your camera saved <b id="finalCount">-</b> pictures. They are all stored safely.</p>
      <div class="safe-banner">
        <strong>&#x1F50C; Safe to unplug now</strong>
        <span>You can disconnect the battery and take the memory card to a computer.</span>
      </div>
    </div>
  </div>
<script>
function fmtElapsed(ms) {
  const s = Math.floor(ms / 1000), m = Math.floor(s / 60);
  return m > 0 ? (m + (m === 1 ? ' minute' : ' minutes')) : (s + (s === 1 ? ' second' : ' seconds'));
}
const STATE_LABELS = { capturing: 'Watching', warming_up: 'Warming up', safe_to_remove: 'Finished', error: 'Needs attention' };
let finishing = false;

async function poll() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    document.getElementById('barSub').textContent = STATE_LABELS[data.state] || data.state;
    document.getElementById('dot').style.background = data.state === 'capturing' ? '#8ef0a8' : (data.state === 'error' ? '#ef6f61' : '#ffe179');

    if (data.state === 'safe_to_remove') {
      document.getElementById('screenMain').hidden = true;
      document.getElementById('screenFinishing').hidden = true;
      document.getElementById('screenSafe').hidden = false;
      document.getElementById('finalCount').textContent = data.savedCount;
      return;
    }
    if (finishing) return;

    document.getElementById('shotCount').textContent = data.savedCount;
    document.getElementById('elapsed').textContent = data.state === 'error' ? 'Not watching yet' : ('Watching for ' + fmtElapsed(data.elapsedMs));
    const note = document.getElementById('noteCard');
    if (data.state === 'error') {
      note.innerHTML = '<h3>Your camera needs help</h3><p>' + (data.error || 'Something went wrong while starting up.') + '</p>';
      document.getElementById('btnFinish').disabled = true;
    } else {
      note.innerHTML = '<h3>More coming soon</h3><p>Taking a peek and changing settings from here are on the way. For now, this page shows what your camera is doing right now.</p>';
      document.getElementById('btnFinish').disabled = false;
    }
  } catch (error) {
    document.getElementById('barSub').textContent = 'Reconnecting…';
  }
}

document.getElementById('btnFinish').addEventListener('click', async () => {
  finishing = true;
  document.getElementById('screenMain').hidden = true;
  document.getElementById('screenFinishing').hidden = false;
  try { await fetch('/api/stop', { method: 'POST' }); } catch (error) { /* status polling will keep retrying */ }
});

poll();
setInterval(poll, 1500);
</script>
</body>
</html>
)HTML";
}  // namespace

bool ControlServer::begin(String& diagnostic) {
  uint8_t mac[6];
  WiFi.macAddress(mac);
  char suffix[5];
  snprintf(suffix, sizeof(suffix), "%02X%02X", mac[4], mac[5]);
  ap_ssid_ = String("InsectCam-") + suffix;

  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(ap_ssid_.c_str(), kApPasswordPlaceholder)) {
    diagnostic = "failed to start Wi-Fi access point " + ap_ssid_;
    return false;
  }

  server_.on("/", HTTP_GET, [this]() { handleRoot(); });
  server_.on("/api/status", HTTP_GET, [this]() { handleStatus(); });
  server_.on("/api/stop", HTTP_POST, [this]() { handleStop(); });
  server_.begin();
  started_ = true;
  diagnostic = "control app ready at http://" + WiFi.softAPIP().toString() + " (network: " + ap_ssid_ + ")";
  return true;
}

void ControlServer::update(const ControlStatus& status) { status_ = status; }

void ControlServer::handleClient() {
  if (started_) server_.handleClient();
}

const String& ControlServer::apSsid() const { return ap_ssid_; }

void ControlServer::handleRoot() {
  server_.send_P(200, "text/html", kControlAppHtml);
}

void ControlServer::handleStop() {
  stop_requested_ = true;
  server_.send(202, "application/json", "{\"accepted\":true}");
}

bool ControlServer::consumeStopRequest() {
  if (!stop_requested_) return false;
  stop_requested_ = false;
  return true;
}

void ControlServer::handleStatus() {
  const String json =
      "{\"state\":\"" + status_.state + "\",\"runId\":\"" + status_.run_id +
      "\",\"captureCount\":" + String(status_.capture_count) +
      ",\"savedCount\":" + String(status_.saved_count) +
      ",\"elapsedMs\":" + String(status_.elapsed_ms) +
      ",\"sdMounted\":" + String(status_.sd_mounted ? "true" : "false") +
      ",\"error\":\"" + status_.error +
      "\",\"freeHeap\":" + String(ESP.getFreeHeap()) + "}";
  server_.send(200, "application/json", json);
}
