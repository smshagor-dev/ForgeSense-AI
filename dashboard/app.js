const byId = (id) => document.getElementById(id);
let revision = -1;

function boolText(el, value, dangerWhenTrue = false) {
  if (value === undefined || value === null) { el.textContent = "--"; el.className = ""; return; }
  el.textContent = value ? "YES" : "NO";
  el.className = dangerWhenTrue && value ? "bad" : "";
}
function flag(el, label, value, badWhenTrue = false) {
  el.textContent = `${label} ${value ? "ON" : "OFF"}`;
  el.className = `flag ${badWhenTrue ? (value ? "bad" : "ok") : (value ? "ok" : "")}`;
}
function n(value, digits=2) { return Number.isFinite(value) ? value.toFixed(digits) : "--"; }

function render(snapshot) {
  revision = snapshot.revision;
  byId("revision").textContent = `rev ${revision}`;
  const system = snapshot.system;
  const status = snapshot.fpga_status;
  const sensor = snapshot.sensor;
  const ml = snapshot.ml;
  byId("state").textContent = system.state;
  byId("authority").textContent = system.authority === "fpga_status" ? "FPGA AUTHORITY" : "UNKNOWN";
  byId("stateNote").textContent = system.status_fresh ? "Authoritative FPGA state is fresh." : "Authoritative status is missing or stale.";

  if (status) {
    flag(byId("loadFlag"), "LOAD", status.load_enable);
    flag(byId("readyFlag"), "READY", status.operational_ready);
    flag(byId("faultFlag"), "FAULT", status.fault_latched, true);
    boolText(byId("hardWarning"), status.hard_warning, true);
    boolText(byId("hardCritical"), status.hard_critical, true);
    boolText(byId("commTimeout"), status.comm_timeout, true);
    boolText(byId("emergency"), status.emergency, true);
    boolText(byId("mlWarning"), status.ml_warning, true);
    boolText(byId("mlCritical"), status.ml_critical, true);
    byId("statusAge").textContent = `${status.received_age_ms} ms · seq ${status.sequence}`;
  }
  if (sensor) {
    byId("temperature").textContent = n(sensor.temperature_c,1);
    byId("vibration").textContent = n(sensor.vibration_rms_g,3);
    byId("current").textContent = n(sensor.current_a,2);
    byId("sensorValidity").textContent = sensor.all_valid ? "VALID" : "INVALID";
    byId("sensorSeq").textContent = `sequence ${sensor.sequence}`;
  }
  if (ml) {
    const risk = Math.max(0, Math.min(100, ml.anomaly_score * 100));
    byId("riskValue").textContent = risk.toFixed(1);
    byId("riskBar").style.width = `${risk}%`;
    byId("mlClass").textContent = ml.health_class;
    byId("confidence").textContent = `confidence ${(ml.confidence * 100).toFixed(0)}%`;
  }
  byId("linkDot").className = `dot ${system.status_fresh ? "online" : "offline"}`;
  byId("linkText").textContent = system.status_fresh ? "FPGA status online" : "Status stale";
}

async function loadEvents() {
  const response = await fetch("/api/v1/events?limit=18", {cache:"no-store"});
  if (!response.ok) return;
  const data = await response.json();
  const root = byId("events");
  root.innerHTML = "";
  if (!data.events.length) { root.innerHTML = '<p class="muted">No events yet.</p>'; return; }
  [...data.events].reverse().forEach((event) => {
    const item = document.createElement("div");
    item.className = `event ${event.severity}`;
    const code = document.createElement("code");
    code.textContent = event.code;
    const text = document.createElement("p");
    text.textContent = event.message;
    item.append(code, text);
    root.append(item);
  });
}

async function poll() {
  try {
    const response = await fetch(`/api/v1/stream?after=${revision}`, {cache:"no-store"});
    if (!response.ok) throw new Error("HTTP " + response.status);
    render(await response.json());
    await loadEvents();
  } catch (_) {
    byId("linkDot").className = "dot offline";
    byId("linkText").textContent = "Monitor disconnected";
  } finally {
    setTimeout(poll, 250);
  }
}
poll();
