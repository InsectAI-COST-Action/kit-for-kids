#include "control_server.h"

#include <WiFi.h>
#include <esp_heap_caps.h>

namespace {
constexpr uint8_t kDnsPort = 53;

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
  .peek-card { background:var(--paper); border-radius:1.3rem; padding:14px; box-shadow:var(--shadow); }
  .peek-stage { border-radius:.9rem; overflow:hidden; background:#15324d; aspect-ratio:4/3; display:flex; align-items:center; justify-content:center; margin-bottom:10px; }
  .peek-stage img { width:100%; height:100%; object-fit:cover; display:block; }
  .peek-empty { color:#b9cdd6; font-size:.8rem; font-weight:700; text-align:center; padding:18px; line-height:1.6; margin:0; }
  .btn-peek { background:#fff; border:2px solid var(--teal); color:#075c63; width:100%; padding:12px 14px; font-size:.92rem; }
  .meter-card { background:var(--paper); border-radius:1.3rem; padding:14px 16px 16px; box-shadow:var(--shadow); }
  .meter-head { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:8px; }
  .meter-title { font-weight:900; font-size:.9rem; }
  .meter-verdict { font-size:.74rem; font-weight:900; color:#075c63; }
  .bars { display:flex; gap:3px; align-items:flex-end; height:38px; }
  .bars i { flex:1; background:#dfe9ec; border-radius:2px 2px 1px 1px; display:block; height:12%; font-style:normal;
    transition:height .45s ease, background .45s ease; }
  @media (prefers-reduced-motion: reduce) { .bars i { transition:none; } }
  .bars i.hot { background:var(--coral); }
  .bars i.warm { background:#f4bf38; }
  .settings-details { background:var(--paper); border-radius:1.3rem; box-shadow:var(--shadow); overflow:hidden; }
  .settings-details summary { padding:14px 16px; font-weight:900; font-size:.88rem; cursor:pointer; color:var(--purple-dark); }
  .settings-body { padding:0 16px 16px; display:grid; gap:10px; }
  .settings-hint { font-size:.76rem; color:var(--muted); margin:0; line-height:1.5; }
  .settings-details label { font-size:.82rem; font-weight:800; display:block; }
  .settings-details select { display:block; width:100%; margin-top:5px; padding:9px; border-radius:.6rem; border:2px solid #b5c8cd; font:inherit; background:#fff; color:var(--ink); }
  .settings-check { display:flex !important; align-items:center; gap:8px; font-weight:700 !important; }
  .settings-check input { width:1.1rem; height:1.1rem; margin:0; accent-color:var(--teal); }
  .btn-teal { background:#fff; border:2px solid var(--teal); color:#075c63; width:100%; padding:11px 14px; font-size:.9rem; margin-top:2px; }
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
      <div class="peek-card">
        <div class="peek-stage" id="peekStage">
          <p class="peek-empty" id="peekEmpty">Tap below to see what your camera can see right now.</p>
        </div>
        <button class="btn-peek" id="btnPeek">&#x1F441;&#xFE0F; Take a peek</button>
      </div>
      <div class="meter-card" id="meterCard" hidden>
        <div class="meter-head">
          <span class="meter-title">Is anything moving?</span>
          <span class="meter-verdict" id="meterVerdict">All quiet</span>
        </div>
        <div class="bars" id="bars" aria-hidden="true"></div>
      </div>
      <div class="note-card" id="noteCard">
        <h3>All good here</h3>
        <p>This page shows what your camera is doing right now.</p>
      </div>
      <details class="settings-details">
        <summary>Grown-up helper: camera settings</summary>
        <div class="settings-body">
          <p class="settings-hint" id="settingsCurrent">Current: checking&hellip;</p>
          <label>How often should the camera take a picture?
            <select id="cfgInterval">
              <option value="1000">1 image every 1 second</option>
              <option value="2000">1 image every 2 seconds</option>
              <option value="30000">1 image every 30 seconds</option>
              <option value="60000">1 image every 1 minute</option>
            </select>
          </label>
          <label>How clear should the pictures be?
            <select id="cfgQuality">
              <option value="high">High quality</option>
              <option value="low">Low quality</option>
            </select>
          </label>
          <label>How long should the camera keep going?
            <select id="cfgDuration">
              <option value="60">1 minute</option>
              <option value="300">5 minutes</option>
              <option value="1800">30 minutes</option>
              <option value="3600" selected>1 hour</option>
              <option value="0">Infinite &ndash; until switched off</option>
            </select>
          </label>
          <label class="settings-check"><input type="checkbox" id="cfgMotion"> Save pictures only when something moves</label>
          <button class="btn-teal" id="btnSaveConfig">Save this setting</button>
          <button class="btn-teal" id="btnRestartNow" hidden>&#x1F504; Restart now to use this setting</button>
          <p class="settings-hint" id="settingsStatus">Changing this takes effect after the board is restarted.</p>
        </div>
      </details>
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
      <p class="settings-hint" style="margin-top:14px">Leaving the battery connected?</p>
      <button class="btn-teal" id="btnStartAgain" style="max-width:19rem">&#x1F504; Start another adventure</button>
    </div>
  </div>
<script>
function fmtElapsed(ms) {
  const s = Math.floor(ms / 1000), m = Math.floor(s / 60);
  return m > 0 ? (m + (m === 1 ? ' minute' : ' minutes')) : (s + (s === 1 ? ' second' : ' seconds'));
}
const STATE_LABELS = { capturing: 'Watching', warming_up: 'Warming up', safe_to_remove: 'Finished', error: 'Needs attention' };
let finishing = false;
let awaitingRestart = false;
let awaitingStartAfterStop = false;
let peekAvailable = false;
let lastKnownState = 'starting';

const BAR_COUNT = 16;
const bars = document.getElementById('bars');
for (let i = 0; i < BAR_COUNT; i++) bars.append(document.createElement('i'));

function updateMotionMeter(scores) {
  const meterCard = document.getElementById('meterCard');
  if (!scores || !scores.length) { meterCard.hidden = true; return; }
  meterCard.hidden = false;
  const recent = scores.slice(-BAR_COUNT);
  const padded = new Array(BAR_COUNT - recent.length).fill(0).concat(recent);
  const els = bars.children;
  padded.forEach((score, i) => {
    els[i].style.height = Math.max(10, Math.min(100, (score / 12) * 100)) + '%';
    els[i].className = score >= 5 ? 'hot' : (score >= 3 ? 'warm' : '');
  });
  const latest = recent[recent.length - 1];
  const verdict = document.getElementById('meterVerdict');
  verdict.textContent = latest >= 5 ? 'Something moved!' : (latest >= 3 ? 'A little wiggle' : 'All quiet');
  verdict.style.color = latest >= 5 ? '#b34642' : (latest >= 3 ? '#8a6d0a' : '#075c63');
}

async function loadPeek() {
  const stage = document.getElementById('peekStage');
  try {
    const response = await fetch('/api/peek?' + Date.now());
    if (response.status !== 200) { stage.innerHTML = '<p class="peek-empty">No picture yet &mdash; check back in a moment.</p>'; return; }
    const blob = await response.blob();
    const img = document.createElement('img');
    img.src = URL.createObjectURL(blob);
    img.alt = 'The most recent picture your camera took';
    stage.replaceChildren(img);
  } catch (error) {
    stage.innerHTML = '<p class="peek-empty">Could not load a picture right now.</p>';
  }
}
document.getElementById('btnPeek').addEventListener('click', loadPeek);

function describeConfig(cfg) {
  const seconds = cfg.capture_interval_ms / 1000;
  const intervalText = seconds === 60 ? 'one picture every 1 minute' : ('one picture every ' + seconds + (seconds === 1 ? ' second' : ' seconds'));
  const qualityText = cfg.frame_size === 'QXGA' ? 'high quality' : 'low quality';
  const durationText = cfg.max_session_seconds === 0 ? 'until switched off' : ((cfg.max_session_seconds / 60) + ' minute' + (cfg.max_session_seconds === 60 ? '' : 's'));
  return intervalText + ', ' + qualityText + ', for ' + durationText + (cfg.motion_trigger_enabled ? '; saves only when something moves' : '');
}

async function loadConfig() {
  try {
    const response = await fetch('/api/config');
    const cfg = await response.json();
    const qualityKey = (cfg.frame_size === 'VGA' && cfg.jpeg_quality === 24) ? 'low' : 'high';
    document.getElementById('cfgInterval').value = String(cfg.capture_interval_ms);
    document.getElementById('cfgQuality').value = qualityKey;
    document.getElementById('cfgDuration').value = String(cfg.max_session_seconds);
    document.getElementById('cfgMotion').checked = Boolean(cfg.motion_trigger_enabled);
    document.getElementById('settingsCurrent').textContent = 'Current: ' + describeConfig(cfg);
  } catch (error) {
    document.getElementById('settingsCurrent').textContent = 'Could not read the current setting.';
  }
}

document.getElementById('btnSaveConfig').addEventListener('click', async () => {
  const status = document.getElementById('settingsStatus');
  status.textContent = 'Saving…';
  try {
    const body = new URLSearchParams({
      intervalMs: document.getElementById('cfgInterval').value,
      quality: document.getElementById('cfgQuality').value,
      durationSeconds: document.getElementById('cfgDuration').value,
      motionTriggerEnabled: document.getElementById('cfgMotion').checked ? 'true' : 'false',
    });
    const response = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
    if (response.status === 202) {
      status.textContent = 'Saved! Restart to start using this setting.';
      document.getElementById('btnRestartNow').hidden = false;
      loadConfig();
    } else {
      const data = await response.json().catch(() => ({}));
      status.textContent = data.error || 'Could not save this setting.';
    }
  } catch (error) {
    status.textContent = 'Could not reach the camera to save this.';
  }
});
loadConfig();

document.getElementById('btnRestartNow').addEventListener('click', async () => {
  const button = document.getElementById('btnRestartNow');
  const status = document.getElementById('settingsStatus');
  if (lastKnownState === 'capturing' || lastKnownState === 'warming_up') {
    if (!window.confirm('This will end the current picture-taking session early and restart your camera with the new setting. Continue?')) return;
    button.disabled = true;
    status.textContent = 'Finishing the current session first…';
    finishing = true;
    awaitingStartAfterStop = true;
    document.getElementById('screenMain').hidden = true;
    document.getElementById('screenFinishing').hidden = false;
    try { await fetch('/api/stop', { method: 'POST' }); } catch (error) { /* status polling will keep retrying */ }
  } else {
    button.disabled = true;
    awaitingRestart = true;
    try { await fetch('/api/start', { method: 'POST' }); } catch (error) { /* the device is rebooting; polling will recover */ }
  }
});

async function poll() {
  try {
    const response = await fetch('/api/status');
    const data = await response.json();
    document.getElementById('barSub').textContent = STATE_LABELS[data.state] || data.state;
    document.getElementById('dot').style.background = data.state === 'capturing' ? '#8ef0a8' : (data.state === 'error' ? '#ef6f61' : '#ffe179');

    if (data.state === 'safe_to_remove') {
      if (awaitingStartAfterStop) {
        // Part of "Restart now to use this setting": the session has just
        // finished safely; immediately continue into the restart rather
        // than showing the "safe to unplug" screen for a setting change.
        awaitingStartAfterStop = false;
        awaitingRestart = true;
        document.getElementById('settingsStatus').textContent = 'Restarting your camera…';
        try { await fetch('/api/start', { method: 'POST' }); } catch (error) { /* device is rebooting; polling will recover */ }
        return;
      }
      document.getElementById('screenMain').hidden = true;
      document.getElementById('screenFinishing').hidden = true;
      document.getElementById('screenSafe').hidden = false;
      document.getElementById('finalCount').textContent = data.savedCount;
      return;
    }

    if (awaitingRestart) {
      // The device answered again after rebooting - back to the main screen.
      awaitingRestart = false;
      finishing = false;
      document.getElementById('screenSafe').hidden = true;
      document.getElementById('screenFinishing').hidden = true;
      document.getElementById('screenMain').hidden = false;
      const startAgainButton = document.getElementById('btnStartAgain');
      startAgainButton.disabled = false;
      startAgainButton.textContent = '\u{1F504} Start another adventure';
      const restartNowButton = document.getElementById('btnRestartNow');
      restartNowButton.hidden = true;
      restartNowButton.disabled = false;
      document.getElementById('settingsStatus').textContent = 'Changing this takes effect after the board is restarted.';
    }
    lastKnownState = data.state;
    if (finishing) return;

    document.getElementById('shotCount').textContent = data.savedCount;
    document.getElementById('elapsed').textContent = data.state === 'error' ? 'Not watching yet' : ('Watching for ' + fmtElapsed(data.elapsedMs));
    updateMotionMeter(data.motionRecent);
    peekAvailable = Boolean(data.hasPeek);
    document.getElementById('btnPeek').disabled = !peekAvailable;
    const note = document.getElementById('noteCard');
    if (data.state === 'error') {
      note.innerHTML = '<h3>Your camera needs help</h3><p>' + (data.error || 'Something went wrong while starting up.') + '</p>';
      document.getElementById('btnFinish').disabled = true;
    } else {
      note.innerHTML = '<h3>All good here</h3><p>This page shows what your camera is doing right now.</p>';
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

document.getElementById('btnStartAgain').addEventListener('click', async () => {
  awaitingRestart = true;
  document.getElementById('btnStartAgain').disabled = true;
  document.getElementById('btnStartAgain').textContent = 'Starting again…';
  try { await fetch('/api/start', { method: 'POST' }); } catch (error) { /* the device is rebooting; polling will recover */ }
});

poll();
setInterval(poll, 1500);
</script>
</body>
</html>
)HTML";
}  // namespace

bool ControlServer::begin(String& diagnostic) {
  // Fixed and shared across every device, by deliberate owner decision: this
  // is a local-only AP for a kids' kit shipped in quantity, the SD card's
  // contents are not sensitive, and per-device credentials would only add
  // manufacturing/support burden for no real security benefit here. The
  // password still exists so a teacher can decide who joins - not for
  // confidentiality. One shared QR sticker design works for the whole
  // product line. Known trade-off, accepted: several kits running in the
  // same room broadcast the same network name, so a phone may need to
  // choose the right one manually if more than one is nearby.
  ap_ssid_ = "InsectCam";
  ap_password_ = "antcamera";

  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(ap_ssid_.c_str(), ap_password_.c_str())) {
    diagnostic = "failed to start Wi-Fi access point " + ap_ssid_;
    return false;
  }

  // Captive-portal redirect: answer every DNS query with our own address so
  // phones that probe connectivity (Android's connectivitycheck, iOS's
  // captive.apple.com) get pointed straight back here and open the control
  // app automatically instead of reporting "no internet" and stopping.
  dns_server_.start(kDnsPort, "*", WiFi.softAPIP());

  server_.on("/", HTTP_GET, [this]() { handleRoot(); });
  server_.on("/api/status", HTTP_GET, [this]() { handleStatus(); });
  server_.on("/api/stop", HTTP_POST, [this]() { handleStop(); });
  server_.on("/api/peek", HTTP_GET, [this]() { handlePeek(); });
  server_.on("/api/config", HTTP_GET, [this]() { handleConfigRead(); });
  server_.on("/api/config", HTTP_POST, [this]() { handleConfigWrite(); });
  server_.on("/api/start", HTTP_POST, [this]() { handleStart(); });
  server_.onNotFound([this]() { handleRoot(); });  // any unrecognised path also lands on the app, for captive-portal probes
  server_.begin();
  started_ = true;
  const String qr_payload = "WIFI:S:" + ap_ssid_ + ";T:WPA;P:" + ap_password_ + ";;";
  diagnostic = "control app ready at http://" + WiFi.softAPIP().toString() + " (network: " + ap_ssid_ +
               ", password: " + ap_password_ + ") - QR payload: " + qr_payload;
  return true;
}

void ControlServer::update(const ControlStatus& status) { status_ = status; }

void ControlServer::handleClient() {
  if (!started_) return;
  dns_server_.processNextRequest();
  server_.handleClient();
}

const String& ControlServer::apSsid() const { return ap_ssid_; }
const String& ControlServer::apPassword() const { return ap_password_; }

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

void ControlServer::handleStart() {
  // Deliberately a full reboot rather than reinitialising SD/camera/logger
  // state in place: reuses the exact boot sequence already proven for weeks
  // instead of a second, untested code path duplicating it. See
  // docs/device-control-app-plan.md Phase 4 for why the in-place approach
  // was rejected.
  if (status_.state == "capturing" || status_.state == "warming_up") {
    server_.send(409, "application/json", "{\"error\":\"Finish the current adventure first.\"}");
    return;
  }
  server_.send(202, "application/json", "{\"accepted\":true}");
  server_.client().flush();
  delay(300);  // let the response reach the phone before Wi-Fi drops for the reboot
  ESP.restart();
}

bool ControlServer::updatePeek(const uint8_t* data, size_t length) {
  if (data == nullptr || length == 0 || length > kPeekBufferCapacity) return false;
  const int write_index = (peek_active_index_ == 0) ? 1 : 0;
  if (peek_buffers_[write_index] == nullptr) {
    peek_buffers_[write_index] = static_cast<uint8_t*>(heap_caps_malloc(kPeekBufferCapacity, MALLOC_CAP_SPIRAM));
    if (peek_buffers_[write_index] == nullptr) return false;
  }
  memcpy(peek_buffers_[write_index], data, length);
  peek_lengths_[write_index] = length;
  peek_active_index_ = write_index;
  return true;
}

void ControlServer::setEffectiveConfig(const String& json) { effective_config_json_ = json; }

bool ControlServer::consumePendingConfigWrite(String& json_out) {
  if (!config_write_pending_) return false;
  config_write_pending_ = false;
  json_out = pending_config_write_;
  return true;
}

void ControlServer::handleConfigRead() {
  server_.send(200, "application/json", effective_config_json_);
}

void ControlServer::handleConfigWrite() {
  if (!status_.sd_mounted) {
    server_.send(409, "application/json", "{\"error\":\"No camera card is mounted right now.\"}");
    return;
  }
  if (!server_.hasArg("intervalMs") || !server_.hasArg("quality") || !server_.hasArg("durationSeconds") ||
      !server_.hasArg("motionTriggerEnabled")) {
    server_.send(400, "application/json", "{\"error\":\"Missing fields.\"}");
    return;
  }

  const uint32_t interval_ms = server_.arg("intervalMs").toInt();
  const String quality = server_.arg("quality");
  const uint32_t duration_seconds = server_.arg("durationSeconds").toInt();
  const bool motion_trigger_enabled = server_.arg("motionTriggerEnabled") == "true";

  // Only ever the same firmware-approved combinations the SD-card dashboard
  // settings tool offers - the app suggests, firmware still validates again
  // on its next boot regardless.
  const uint32_t kAllowedIntervals[] = {1000, 2000, 30000, 60000};
  const uint32_t kAllowedDurations[] = {60, 300, 1800, 3600, 0};
  bool interval_ok = false, duration_ok = false;
  for (uint32_t value : kAllowedIntervals) if (value == interval_ms) interval_ok = true;
  for (uint32_t value : kAllowedDurations) if (value == duration_seconds) duration_ok = true;
  const bool quality_ok = (quality == "high" || quality == "low");
  if (!interval_ok || !duration_ok || !quality_ok) {
    server_.send(400, "application/json", "{\"error\":\"Not a safe setting combination.\"}");
    return;
  }

  const bool pilot = !motion_trigger_enabled && interval_ms == 1000 && quality == "high" && duration_seconds == 3600;
  const String frame_size = (quality == "high") ? "QXGA" : "VGA";
  const uint8_t jpeg_quality = (quality == "high") ? 12 : 24;
  const String duration_id = (duration_seconds == 0) ? "infinite" : (String(duration_seconds) + "s");
  const String camera_preset = pilot ? "qxga_q12_1fps" :
      ("custom_" + quality + "_" + String(interval_ms) + "ms_" + duration_id + (motion_trigger_enabled ? "_motion" : ""));

  const String json =
      "{\n  \"schema_version\": 1,\n  \"capture_fps\": 1,\n  \"capture_interval_ms\": " + String(interval_ms) +
      ",\n  \"max_session_seconds\": " + String(duration_seconds) +
      ",\n  \"capture_mode\": \"" + (pilot ? "pilot" : "custom") +
      "\",\n  \"camera_preset\": \"" + camera_preset +
      "\",\n  \"motion_trigger_enabled\": " + (motion_trigger_enabled ? "true" : "false") +
      ",\n  \"motion_threshold\": 5,\n  \"frame_size\": \"" + frame_size +
      "\",\n  \"jpeg_quality\": " + String(jpeg_quality) +
      ",\n  \"model_id\": \"none\",\n  \"log_level\": \"info\"\n}\n";

  pending_config_write_ = json;
  config_write_pending_ = true;
  effective_config_json_ = json;  // optimistic: reflects the requested setting even before the write is confirmed
  server_.send(202, "application/json", "{\"accepted\":true}");
}

void ControlServer::handlePeek() {
  const int index = peek_active_index_;
  if (index < 0 || peek_buffers_[index] == nullptr) {
    server_.send(204, "text/plain", "");
    return;
  }
  server_.send_P(200, "image/jpeg", reinterpret_cast<PGM_P>(peek_buffers_[index]), peek_lengths_[index]);
}

void ControlServer::handleStatus() {
  String motion_recent = "[";
  for (uint8_t index = 0; index < status_.motion_recent_count; ++index) {
    if (index > 0) motion_recent += ',';
    motion_recent += String(status_.motion_recent[index], 2);
  }
  motion_recent += ']';

  const String json =
      "{\"state\":\"" + status_.state + "\",\"runId\":\"" + status_.run_id +
      "\",\"captureCount\":" + String(status_.capture_count) +
      ",\"savedCount\":" + String(status_.saved_count) +
      ",\"elapsedMs\":" + String(status_.elapsed_ms) +
      ",\"sdMounted\":" + String(status_.sd_mounted ? "true" : "false") +
      ",\"error\":\"" + status_.error +
      "\",\"hasPeek\":" + String(peek_active_index_ >= 0 ? "true" : "false") +
      ",\"motionRecent\":" + motion_recent +
      ",\"freeHeap\":" + String(ESP.getFreeHeap()) + "}";
  server_.send(200, "application/json", json);
}
