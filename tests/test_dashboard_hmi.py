from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_industrial_hmi_layout_contract() -> None:
    html = (ROOT / "dashboard/index.html").read_text(encoding="utf-8")
    css = (ROOT / "dashboard/styles.css").read_text(encoding="utf-8")

    for token in (
        'class="sidebar"',
        'id="overview"',
        'id="telemetry"',
        'id="sensors"',
        'id="safety"',
        'id="events-section"',
        'id="calibration"',
        'id="security"',
        'id="trendCanvas"',
        'id="tempGauge"',
        'id="currentGauge"',
        'id="vibrationGauge"',
        'Protected Drive Train',
        'Calibration & Maintenance',
        'Security & Compliance',
        'READ ONLY',
    ):
        assert token in html, token

    for token in (
        ".summary-strip",
        ".overview-grid",
        ".machine-panel",
        ".trend-panel",
        ".gauge-grid",
        ".operations-grid",
        "@media (max-width: 760px)",
    ):
        assert token in css, token


def test_dashboard_runtime_uses_read_only_monitoring_routes_only() -> None:
    app = (ROOT / "dashboard/app.js").read_text(encoding="utf-8")
    runner = (ROOT / "tools/run_dashboard.py").read_text(encoding="utf-8")

    assert 'fetch(`/api/v1/stream?after=${revision}`' in app
    assert 'fetch("/api/v1/events?limit=18"' in app
    assert "cache: \"no-store\"" in app
    assert "TelemetryHttpServer" in runner
    assert 'default="127.0.0.1"' in runner
    assert "API is read-only; no actuator/control routes are exposed." in runner

    for forbidden in (
        'method: "POST"',
        "method: 'POST'",
        'method: "PUT"',
        "method: 'PUT'",
        'method: "PATCH"',
        "method: 'PATCH'",
        'method: "DELETE"',
        "method: 'DELETE'",
        "CALIBRATION-WRITE",
        "PrepareRecord",
        "CommitRecord",
        "set_hard_limit",
        "update_safety_limit",
        "RotateAuthorityKey",
    ):
        assert forbidden not in app


def test_dashboard_never_claims_unavailable_security_or_calibration_state() -> None:
    html = (ROOT / "dashboard/index.html").read_text(encoding="utf-8")

    for truthful_boundary in (
        "Not exposed live",
        "Separate image",
        "Host evidence",
        "Offline workflow",
        "Build evidence",
        "Maintenance only",
    ):
        assert truthful_boundary in html

    for fabricated_claim in (
        "Secure boot policy Enforced",
        "Flash encryption policy Enabled",
        "Provisioning status Complete",
        "Calibration record Valid",
    ):
        assert fabricated_claim not in html
