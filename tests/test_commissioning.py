from __future__ import annotations

from copy import deepcopy

from forgesense_commission import (
    CommissioningObserver,
    apply_observation_to_record,
    apply_smoke_to_record,
    run_smoke_commissioning,
)
from forgesense_protocol import (
    SAFETY_DEVICE_IDENTITY_OK,
    SAFETY_DEVICE_TRANSPORT_ERROR,
    SAFETY_SENSORS_VALID,
    STATUS_OPERATIONAL_READY,
    SensorSnapshotWire,
    StatusSnapshotWire,
    encode_sensor_snapshot,
    encode_status_snapshot,
)


class FakeSmokeTransport:
    def __init__(self) -> None:
        self.rx = bytearray([0x55, 0x55])
        self.writes: list[int] = []

    def read(self, size: int = 1) -> bytes:
        if not self.rx:
            return b""
        count = min(size, len(self.rx))
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data

    def write(self, data: bytes) -> int:
        self.writes.extend(data)
        self.rx.extend(data)
        return len(data)


BASE_RECORD = {
    "schema": "forgesense.bench_record.v1",
    "checks": [
        {
            "check_id": "BRINGUP-LOAD-OFF",
            "result": "NOT_RUN",
            "expected": "manual electrical check",
            "observed": "",
            "units": "logic",
            "evidence": [],
        },
        {
            "check_id": "BRINGUP-UART-ECHO",
            "result": "NOT_RUN",
            "expected": "",
            "observed": "",
            "units": "bytes",
            "evidence": [],
        },
        {
            "check_id": "BRINGUP-UART-HEARTBEAT",
            "result": "NOT_RUN",
            "expected": "",
            "observed": "",
            "units": "bytes",
            "evidence": [],
        },
    ],
    "overall_result": "INCOMPLETE",
}


def test_smoke_commissioning_detects_heartbeat_and_echo() -> None:
    transport = FakeSmokeTransport()
    metrics = run_smoke_commissioning(
        transport,
        required_heartbeats=2,
        heartbeat_timeout_s=0.1,
        echo_bytes=b"\xA6\x3C\x81",
        echo_timeout_s=0.1,
    )
    assert metrics.heartbeat_pass
    assert metrics.echo_pass
    assert metrics.echo_ok == 3
    assert metrics.echo_error_rate == 0.0
    assert transport.writes == [0xA6, 0x3C, 0x81]


def test_smoke_record_only_marks_serial_evidence() -> None:
    metrics = run_smoke_commissioning(
        FakeSmokeTransport(),
        required_heartbeats=2,
        heartbeat_timeout_s=0.1,
        echo_bytes=b"\xA6",
        echo_timeout_s=0.1,
    )
    record = apply_smoke_to_record(deepcopy(BASE_RECORD), metrics)
    by_id = {item["check_id"]: item for item in record["checks"]}
    assert by_id["BRINGUP-UART-HEARTBEAT"]["result"] == "PASS"
    assert by_id["BRINGUP-UART-ECHO"]["result"] == "PASS"
    assert by_id["BRINGUP-LOAD-OFF"]["result"] == "NOT_RUN"
    assert record["overall_result"] == "INCOMPLETE"


def test_production_observer_reports_device_diagnostics() -> None:
    status = StatusSnapshotWire(
        state_code=1,
        control_flags=STATUS_OPERATIONAL_READY,
        safety_flags=SAFETY_SENSORS_VALID | SAFETY_DEVICE_IDENTITY_OK,
    )
    sensor = SensorSnapshotWire(
        temperature_deci_c=253,
        vibration_milli_g=410,
        current_milli_a=1200,
    )
    stream = (
        encode_status_snapshot(status, sequence=7, timestamp_ms=1000)
        + encode_sensor_snapshot(sensor, sequence=9, timestamp_ms=1010)
    )

    observer = CommissioningObserver()
    observer.feed(stream[:11])
    observer.feed(stream[11:])
    summary = observer.as_dict()

    assert observer.status_frames == 1
    assert observer.sensor_frames == 1
    assert observer.commissioning_pass
    assert summary["commissioning_pass"] is True
    assert summary["status"]["state"] == "RUN"
    assert summary["status"]["device_identity_ok"] is True
    assert summary["status"]["device_transport_error"] is False
    assert summary["sensor"]["temperature_c"] == 25.3
    assert summary["sensor"]["current_a"] == 1.2


def test_production_observation_updates_record_without_inventing_manual_checks() -> None:
    status = StatusSnapshotWire(
        state_code=1,
        control_flags=STATUS_OPERATIONAL_READY,
        safety_flags=SAFETY_SENSORS_VALID | SAFETY_DEVICE_IDENTITY_OK,
    )
    sensor = SensorSnapshotWire(250, 300, 900)
    observer = CommissioningObserver()
    observer.feed(encode_status_snapshot(status, sequence=1, timestamp_ms=10))
    observer.feed(encode_sensor_snapshot(sensor, sequence=1, timestamp_ms=20))

    record = apply_observation_to_record(deepcopy(BASE_RECORD), observer)
    by_id = {item["check_id"]: item for item in record["checks"]}
    assert by_id["COMMISSION-STATUS-STREAM"]["result"] == "PASS"
    assert by_id["COMMISSION-SENSOR-STREAM"]["result"] == "PASS"
    assert by_id["COMMISSION-DEVICE-IDENTITY"]["result"] == "PASS"
    assert by_id["COMMISSION-LINK-INTEGRITY"]["result"] == "PASS"
    assert by_id["BRINGUP-LOAD-OFF"]["result"] == "NOT_RUN"
    assert record["overall_result"] == "INCOMPLETE"


def test_production_transport_error_fails_commissioning() -> None:
    status = StatusSnapshotWire(
        state_code=1,
        control_flags=STATUS_OPERATIONAL_READY,
        safety_flags=(
            SAFETY_SENSORS_VALID
            | SAFETY_DEVICE_IDENTITY_OK
            | SAFETY_DEVICE_TRANSPORT_ERROR
        ),
    )
    observer = CommissioningObserver()
    observer.feed(encode_status_snapshot(status, sequence=2, timestamp_ms=30))
    observer.feed(encode_sensor_snapshot(SensorSnapshotWire(250, 300, 900), sequence=2, timestamp_ms=40))

    assert observer.commissioning_pass is False
    record = apply_observation_to_record(deepcopy(BASE_RECORD), observer)
    by_id = {item["check_id"]: item for item in record["checks"]}
    assert by_id["COMMISSION-DEVICE-IDENTITY"]["result"] == "FAIL"
    assert record["overall_result"] == "FAIL"
