from __future__ import annotations

from http.client import HTTPConnection
from pathlib import Path
import threading
import time

from forgesense_protocol import (
    HealthClass,
    MlObservation,
    SAFETY_ML_CRITICAL,
    SAFETY_SENSORS_VALID,
    SENSOR_ALL_VALID,
    STATUS_LOAD_ENABLE,
    STATUS_OPERATIONAL_READY,
    SensorSnapshotWire,
    StatusSnapshotWire,
    VALID_OBSERVATION,
)
from forgesense_telemetry.server import TelemetryHttpServer
from forgesense_telemetry.store import TelemetryStore


def _sensor(valid: bool = True) -> SensorSnapshotWire:
    return SensorSnapshotWire(420, 210, 1250, SENSOR_ALL_VALID if valid else 0)


def _normal_ml() -> MlObservation:
    return MlObservation(1, 1, 1, VALID_OBSERVATION, 0.12, HealthClass.NORMAL, 0.94, 8)


def test_fpga_status_remains_authoritative_over_ml() -> None:
    store = TelemetryStore()
    store.ingest_sensor(_sensor(), sequence=1, source_timestamp_ms=100)
    critical_ml = MlObservation(1, 1, 1, VALID_OBSERVATION, 0.97, HealthClass.CRITICAL, 0.98, 5)
    store.ingest_ml(critical_ml, sequence=4, source_timestamp_ms=105)
    status = StatusSnapshotWire(
        state_code=1,
        control_flags=STATUS_LOAD_ENABLE | STATUS_OPERATIONAL_READY,
        safety_flags=SAFETY_ML_CRITICAL | SAFETY_SENSORS_VALID,
    )
    store.ingest_status(status, sequence=9, source_timestamp_ms=110)
    snapshot = store.snapshot()
    assert snapshot["system"]["authority"] == "fpga_status"
    assert snapshot["system"]["state"] == "RUN"
    assert snapshot["fpga_status"]["ml_critical"] is True
    assert snapshot["ml"]["health_class"] == "CRITICAL"


def test_stale_or_missing_status_never_claims_machine_state() -> None:
    store = TelemetryStore(stale_after_ms=5)
    assert store.snapshot()["system"]["state"] == "UNKNOWN"
    store.ingest_status(StatusSnapshotWire(1, STATUS_LOAD_ENABLE, SAFETY_SENSORS_VALID), sequence=1, source_timestamp_ms=1)
    assert store.snapshot()["system"]["state"] == "RUN"
    time.sleep(0.012)
    snapshot = store.snapshot()
    assert snapshot["system"]["state"] == "UNKNOWN"
    assert snapshot["system"]["status_fresh"] is False


def test_transition_events_are_sparse_and_bounded() -> None:
    store = TelemetryStore(event_capacity=3)
    run = StatusSnapshotWire(1, STATUS_LOAD_ENABLE | STATUS_OPERATIONAL_READY, SAFETY_SENSORS_VALID)
    warning = StatusSnapshotWire(2, STATUS_LOAD_ENABLE | STATUS_OPERATIONAL_READY, SAFETY_SENSORS_VALID)
    store.ingest_status(run, sequence=1, source_timestamp_ms=1)
    first_count = len(store.events())
    store.ingest_status(run, sequence=2, source_timestamp_ms=2)
    assert len(store.events()) == first_count
    store.ingest_status(warning, sequence=3, source_timestamp_ms=3)
    store.ingest_sensor(_sensor(False), sequence=1, source_timestamp_ms=4)
    store.ingest_sensor(_sensor(True), sequence=2, source_timestamp_ms=5)
    events = store.events(limit=3)
    assert len(events) == 3
    assert events[-1]["code"] == "SENSORS_VALID"


def test_monitoring_http_api_is_read_only() -> None:
    store = TelemetryStore()
    store.ingest_sensor(_sensor(), sequence=1, source_timestamp_ms=100)
    store.ingest_ml(_normal_ml(), sequence=1, source_timestamp_ms=101)
    store.ingest_status(
        StatusSnapshotWire(1, STATUS_LOAD_ENABLE | STATUS_OPERATIONAL_READY, SAFETY_SENSORS_VALID),
        sequence=1,
        source_timestamp_ms=102,
    )
    dashboard = Path(__file__).resolve().parents[1] / "dashboard"
    server = TelemetryHttpServer(("127.0.0.1", 0), store, dashboard)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        connection.request("GET", "/api/v1/snapshot")
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        assert response.status == 200
        assert '"authority":"fpga_status"' in body
        connection.close()

        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        connection.request("POST", "/api/v1/control", body=b"{}")
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        assert response.status == 405
        assert "read-only monitoring API" in body
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
