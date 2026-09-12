const byId = (id) => document.getElementById(id);

let revision = -1;
let lastSensorSequence = null;
const historyLimit = 120;
const history = {
  temperature: [],
  current: [],
  vibration: [],
};

function finite(value) {
  return Number.isFinite(value);
}

function numberText(value, digits = 2) {
  return finite(value) ? value.toFixed(digits) : "--";
}

function setText(id, value) {
  const el = byId(id);
  if (el) el.textContent = value;
}

function setClassedText(id, text, state = "") {
  const el = byId(id);
  if (!el) return;
  el.textContent = text;
  el.className = state;
}

function setDot(id, state) {
  const el = byId(id);
  if (!el) return;
  el.className = `mini-dot ${state || "neutral"}`;
}

function statusCell(id, text, state = "") {
  const el = byId(id);
  if (!el) return;
  el.className = state;
  el.innerHTML = "";
  const dot = document.createElement("i");
  dot.className = `mini-dot ${state || "neutral"}`;
  el.append(dot, document.createTextNode(text));
}

function gaugeState(value, warn, critical) {
  if (!finite(value)) return { label: "No data", state: "" };
  if (value >= critical) return { label: "Critical", state: "bad" };
  if (value >= warn) return { label: "Warning", state: "warn" };
  return { label: "Normal", state: "good" };
}

function updateGauge(pathId, stateId, value, maxValue, warn, critical) {
  const path = byId(pathId);
  const stateEl = byId(stateId);
  if (!path || !stateEl) return;
  const length = path.getTotalLength();
  path.style.strokeDasharray = `${length}`;
  const pct = finite(value) ? Math.max(0, Math.min(1, value / maxValue)) : 0;
  path.style.strokeDashoffset = `${length * (1 - pct)}`;
  const condition = gaugeState(value, warn, critical);
  stateEl.textContent = condition.label;
  stateEl.className = `gauge-state ${condition.state}`;
}

function pushHistory(sensor) {
  if (!sensor || sensor.sequence === lastSensorSequence) return;
  lastSensorSequence = sensor.sequence;
  history.temperature.push(sensor.temperature_c);
  history.current.push(sensor.current_a);
  history.vibration.push(sensor.vibration_rms_g);
  for (const series of Object.values(history)) {
    if (series.length > historyLimit) series.splice(0, series.length - historyLimit);
  }
}

function drawTrendChart() {
  const canvas = byId("trendCanvas");
  const empty = byId("chartEmpty");
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const width = Math.max(1, Math.round(rect.width * dpr));
  const height = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.scale(dpr, dpr);
  const w = rect.width;
  const h = rect.height;
  const pad = { left: 20, right: 10, top: 8, bottom: 18 };
  const innerW = Math.max(1, w - pad.left - pad.right);
  const innerH = Math.max(1, h - pad.top - pad.bottom);

  ctx.strokeStyle = "rgba(73,108,134,.22)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i += 1) {
    const y = pad.top + (innerH * i) / 5;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();
  }
  for (let i = 0; i <= 7; i += 1) {
    const x = pad.left + (innerW * i) / 7;
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, h - pad.bottom);
    ctx.stroke();
  }

  const count = Math.max(history.temperature.length, history.current.length, history.vibration.length);
  if (!count) {
    if (empty) empty.classList.remove("hidden");
    ctx.restore();
    return;
  }
  if (empty) empty.classList.add("hidden");

  const seriesConfig = [
    { data: history.temperature, max: 100, color: "#ff5f63" },
    { data: history.current, max: 4.5, color: "#1d9bf0" },
    { data: history.vibration, max: 1.2, color: "#35d98b" },
  ];
  for (const series of seriesConfig) {
    if (!series.data.length) continue;
    ctx.beginPath();
    ctx.strokeStyle = series.color;
    ctx.lineWidth = 1.6;
    series.data.forEach((value, index) => {
      const x = pad.left + (series.data.length === 1 ? innerW : (index * innerW) / (historyLimit - 1));
      const normalized = finite(value) ? Math.max(0, Math.min(1, value / series.max)) : 0;
      const y = pad.top + innerH * (1 - normalized);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  ctx.fillStyle = "#536f84";
  ctx.font = "8px ui-monospace, SFMono-Regular, Menlo, monospace";
  ctx.textAlign = "left";
  ctx.fillText("oldest", pad.left, h - 4);
  ctx.textAlign = "right";
  ctx.fillText("latest", w - pad.right, h - 4);
  ctx.restore();
}

function updateSummary(system, status, sensor, ml) {
  const fresh = Boolean(system?.status_fresh);
  const critical = Boolean(status?.hard_critical || status?.fault_latched || status?.emergency);
  const warning = Boolean(status?.hard_warning || status?.ml_warning);

  if (!fresh) {
    setClassedText("systemHealth", "Stale", "warn");
    setText("systemHealthNote", "Authoritative status unavailable");
  } else if (critical) {
    setClassedText("systemHealth", "Critical", "bad");
    setText("systemHealthNote", "Fail-safe condition active");
  } else if (warning) {
    setClassedText("systemHealth", "Attention", "warn");
    setText("systemHealthNote", "Warning condition active");
  } else {
    setClassedText("systemHealth", "Healthy", "good");
    setText("systemHealthNote", "Deterministic status nominal");
  }

  const safetyState = system?.state || "Unknown";
  setClassedText("summarySafety", safetyState, critical ? "bad" : warning ? "warn" : fresh ? "good" : "");
  setText("summarySafetyNote", fresh ? "FPGA authoritative state" : "Authoritative state pending");

  if (ml) {
    const health = String(ml.health_class ?? "Unknown");
    const healthLower = health.toLowerCase();
    const mlState = healthLower.includes("critical") ? "bad" : healthLower.includes("warning") ? "warn" : "good";
    setClassedText("summaryMl", health, mlState);
    setText("summaryMlNote", finite(ml.confidence) ? `Confidence ${(ml.confidence * 100).toFixed(0)}%` : "Inference available");
  } else {
    setClassedText("summaryMl", "No data", "");
    setText("summaryMlNote", "Inference pending");
  }

  setClassedText("summaryComm", fresh ? "Connected" : "Stale", fresh ? "good" : "warn");
  setText("summaryCommNote", fresh ? "FPGA status link fresh" : "Waiting for fresh FPGA status");

  setText("summaryTemperature", sensor ? numberText(sensor.temperature_c, 1) : "--");
  setText("summaryCurrent", sensor ? numberText(sensor.current_a, 2) : "--");
  setText("summaryTemperatureNote", sensor ? (sensor.valid_temperature ? "Sensor valid" : "Sensor invalid") : "No sensor data");
  setText("summaryCurrentNote", sensor ? (sensor.valid_current ? "Sensor valid" : "Sensor invalid") : "No sensor data");
}

function updateMachine(system, status, sensor) {
  const fresh = Boolean(system?.status_fresh);
  const fault = Boolean(status?.fault_latched || status?.hard_critical || status?.emergency);
  const loadEnabled = Boolean(status?.load_enable);
  setText("machineState", system?.state || "UNKNOWN");
  setDot("machineStateDot", !fresh ? "neutral" : fault ? "bad" : status?.hard_warning ? "warn" : "good");
  setText("machineTemp", sensor ? numberText(sensor.temperature_c, 1) : "--");
  setText("machineCurrent", sensor ? numberText(sensor.current_a, 2) : "--");
  setText("machineVibration", sensor ? numberText(sensor.vibration_rms_g, 3) : "--");
  setText("machineLoad", status ? (loadEnabled ? "ENABLED" : "DISABLED") : "--");
  setDot("tagTempDot", !sensor ? "neutral" : sensor.valid_temperature ? "good" : "bad");
  setDot("tagCurrentDot", !sensor ? "neutral" : sensor.valid_current ? "good" : "bad");
  setDot("tagVibrationDot", !sensor ? "neutral" : sensor.valid_vibration ? "good" : "bad");
  setDot("tagLoadDot", !status ? "neutral" : loadEnabled ? "good" : fault ? "bad" : "warn");
  const glow = byId("loadGlow");
  if (glow) glow.style.opacity = loadEnabled ? ".85" : ".18";

  setDot("driveDot", !fresh ? "neutral" : fault ? "bad" : "good");
  setText("driveStatus", !fresh ? "No data" : fault ? "Faulted" : "Monitored");
  setDot("sensorDot", !sensor ? "neutral" : sensor.all_valid ? "good" : "bad");
  setText("sensorSubsystemStatus", !sensor ? "No data" : sensor.all_valid ? "All valid" : "Invalid channel");
  setDot("linkSubsystemDot", fresh ? "good" : "bad");
  setText("linkSubsystemStatus", fresh ? "Connected" : "Stale");
  setDot("enclosureDot", !fresh ? "neutral" : fault ? "bad" : "good");
  setText("enclosureStatus", !fresh ? "Unknown" : fault ? "Protective state" : "Deterministic");
}

function updateLiveValues(sensor) {
  if (!sensor) return;
  setText("temperature", numberText(sensor.temperature_c, 1));
  setText("current", numberText(sensor.current_a, 2));
  setText("vibration", numberText(sensor.vibration_rms_g, 3));
  updateGauge("tempGauge", "tempGaugeState", sensor.temperature_c, 100, 65, 80);
  updateGauge("currentGauge", "currentGaugeState", sensor.current_a, 4.5, 2.5, 3.2);
  updateGauge("vibrationGauge", "vibrationGaugeState", sensor.vibration_rms_g, 1.2, .6, 1.0);
  setText("sensorAgeBadge", finite(sensor.received_age_ms) ? `${sensor.received_age_ms} ms` : `seq ${sensor.sequence}`);
}

function updateSafetyAndTelemetry(system, status, sensor) {
  const fresh = Boolean(system?.status_fresh);
  if (status) {
    statusCell("emergency", status.emergency ? "ACTIVE" : "Normal", status.emergency ? "bad" : "good");
    const hardCritical = Boolean(status.hard_critical);
    const hardWarning = Boolean(status.hard_warning);
    statusCell("hardLimitStatus", hardCritical ? "Critical" : hardWarning ? "Warning" : "Normal", hardCritical ? "bad" : hardWarning ? "warn" : "good");
    statusCell("commTimeout", status.comm_timeout ? "Timeout" : "Active", status.comm_timeout ? "bad" : "good");
    statusCell("loadOutputStatus", status.load_enable ? "Enabled" : "Disabled", status.load_enable ? "good" : status.fault_latched ? "bad" : "warn");
    statusCell("safetyFsmStatus", system?.state || "Unknown", status.fault_latched ? "bad" : hardWarning ? "warn" : "good");
    setText("statusSequence", `#${status.sequence}`);
    setText("statusAge", finite(status.received_age_ms) ? `status age ${status.received_age_ms} ms` : `status seq ${status.sequence}`);
    setText("packetFreshness", finite(status.received_age_ms) ? `${status.received_age_ms} ms` : fresh ? "Fresh" : "Stale");
  } else {
    statusCell("emergency", "--", "neutral");
    statusCell("hardLimitStatus", "--", "neutral");
    statusCell("commTimeout", "--", "neutral");
    statusCell("loadOutputStatus", "--", "neutral");
    statusCell("safetyFsmStatus", "--", "neutral");
    setText("statusSequence", "--");
    setText("statusAge", "status age --");
    setText("packetFreshness", "--");
  }

  statusCell("telemetryLink", fresh ? "Connected" : "Stale", fresh ? "good" : "bad");
  if (sensor) {
    statusCell("sensorValidity", sensor.all_valid ? "Valid" : "Invalid", sensor.all_valid ? "good" : "bad");
    setText("sensorSeq", `#${sensor.sequence}`);
  } else {
    statusCell("sensorValidity", "--", "neutral");
    setText("sensorSeq", "--");
  }
}

function render(snapshot) {
  revision = snapshot.revision;
  setText("revision", `rev ${revision}`);
  const system = snapshot.system || {};
  const status = snapshot.fpga_status;
  const sensor = snapshot.sensor;
  const ml = snapshot.ml;

  pushHistory(sensor);
  updateSummary(system, status, sensor, ml);
  updateMachine(system, status, sensor);
  updateLiveValues(sensor);
  updateSafetyAndTelemetry(system, status, sensor);
  drawTrendChart();

  const linkDot = byId("linkDot");
  if (linkDot) linkDot.className = `status-dot ${system.status_fresh ? "online" : "warning"}`;
  setText("linkText", system.status_fresh ? "Device Connected" : "Status Stale");
}

function eventTime(event) {
  const raw = event.timestamp_ms ?? event.time_ms ?? event.received_at_ms;
  if (!finite(raw)) return "--:--";
  const date = new Date(raw > 10_000_000_000 ? raw : Date.now() - raw);
  return Number.isNaN(date.getTime()) ? "--:--" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

async function loadEvents() {
  const response = await fetch("/api/v1/events?limit=18", { cache: "no-store" });
  if (!response.ok) return;
  const data = await response.json();
  const root = byId("events");
  if (!root) return;
  root.innerHTML = "";
  if (!data.events?.length) {
    root.innerHTML = '<p class="empty-copy">No events yet.</p>';
    return;
  }
  [...data.events].reverse().slice(0, 8).forEach((event) => {
    const row = document.createElement("div");
    const severity = String(event.severity || "info").toLowerCase();
    row.className = "event-row";
    const time = document.createElement("time");
    time.textContent = eventTime(event);
    const text = document.createElement("p");
    text.textContent = event.message || event.code || "Telemetry event";
    const badge = document.createElement("span");
    badge.className = `event-severity ${severity}`;
    badge.textContent = severity;
    row.append(time, text, badge);
    root.append(row);
  });
}

function markDisconnected() {
  const linkDot = byId("linkDot");
  if (linkDot) linkDot.className = "status-dot offline";
  setText("linkText", "Monitor Disconnected");
  setClassedText("systemHealth", "Offline", "bad");
  setText("systemHealthNote", "Local telemetry service unavailable");
  setClassedText("summaryComm", "Disconnected", "bad");
  setText("summaryCommNote", "Waiting for local monitor service");
  setDot("linkSubsystemDot", "bad");
  setText("linkSubsystemStatus", "Disconnected");
}

async function poll() {
  try {
    const response = await fetch(`/api/v1/stream?after=${revision}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
    await loadEvents();
  } catch (_) {
    markDisconnected();
  } finally {
    setTimeout(poll, 250);
  }
}

function updateClock() {
  const now = new Date();
  setText("clockValue", now.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }));
}

function setupNavigation() {
  const sidebar = document.querySelector(".sidebar");
  const menu = byId("mobileMenu");
  if (menu && sidebar) {
    menu.addEventListener("click", () => sidebar.classList.toggle("open"));
  }
  const links = [...document.querySelectorAll(".nav-link")];
  links.forEach((link) => link.addEventListener("click", () => sidebar?.classList.remove("open")));
  const sections = links
    .map((link) => ({ link, section: document.getElementById(link.dataset.section) }))
    .filter((item) => item.section);
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      links.forEach((link) => link.classList.toggle("active", link.dataset.section === visible.target.id));
    }, { rootMargin: "-18% 0px -65% 0px", threshold: [0, .1, .3] });
    sections.forEach(({ section }) => observer.observe(section));
  }
}

window.addEventListener("resize", drawTrendChart);
setupNavigation();
updateClock();
setInterval(updateClock, 1000);
poll();
