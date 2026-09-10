import json

import pytest

from forgesense_telemetry.device_stream import decode_device_line, ingest_device_packet
from forgesense_telemetry.store import TelemetryStore


def record(*, sensor_age=10, status_age=8, ml_age=4, state_code=1, anomaly=1200):
    return "@FS1 " + json.dumps({
        "schema": "forgesense.edge.telemetry.v1",
        "revision": 4,
        "device_ms": 1020,
        "sensor": {"sequence": 10, "source_timestamp_ms": 1000, "received_age_ms": sensor_age, "temperature_deci_c": 421, "vibration_milli_g": 220, "current_milli_a": 1300, "flags": 7},
        "fpga_status": {"sequence": 11, "source_timestamp_ms": 1005, "received_age_ms": status_age, "state_code": state_code, "control_flags": 9, "safety_flags": 64},
        "ml": {"sequence": 12, "source_timestamp_ms": 1015, "received_age_ms": ml_age, "model_id": 1, "model_version": 1, "feature_schema_version": 1, "flags": 1, "anomaly_q15": anomaly, "health_class": 0, "confidence_q8": 240, "inference_age_ms": 12},
        "link": {"accepted_fpga_frames": 9, "rejected_fpga_frames": 1, "stale_sensor_frames": 2, "stale_status_frames": 3, "dropped_pending_messages": 0},
    }, separators=(",", ":"))


def test_fresh_device_record_populates_read_only_store():
    store = TelemetryStore()
    packet = decode_device_line(record())
    ingest_device_packet(store, packet)
    snapshot = store.snapshot()
    assert snapshot["system"]["state"] == "RUN"
    assert snapshot["system"]["authority"] == "fpga_status"
    assert snapshot["system"]["monitoring_only"] is True
    assert snapshot["sensor"]["temperature_c"] == pytest.approx(42.1)
    assert snapshot["ml"]["health_class"] == "NORMAL"


def test_device_reported_stale_status_is_not_reclassified_fresh():
    store = TelemetryStore()
    packet = decode_device_line(record(status_age=5000))
    ingest_device_packet(store, packet, max_source_age_ms=2000)
    snapshot = store.snapshot()
    assert snapshot["system"]["state"] == "UNKNOWN"
    assert snapshot["fpga_status"] is None
    assert snapshot["sensor"] is not None
    assert snapshot["ml"] is not None


@pytest.mark.parametrize("mutator", [
    lambda p: p.update(schema="wrong"),
    lambda p: p["fpga_status"].update(state_code=6),
    lambda p: p["ml"].update(anomaly_q15=32768),
])
def test_invalid_device_records_are_rejected(mutator):
    packet = json.loads(record()[5:])
    mutator(packet)
    with pytest.raises(ValueError):
        decode_device_line("@FS1 " + json.dumps(packet))


def test_non_telemetry_console_log_is_ignored_by_parser():
    with pytest.raises(ValueError):
        decode_device_line("I (1234) forgesense: edge runtime started")
