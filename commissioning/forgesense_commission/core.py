from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
import time
from typing import Protocol

from forgesense_protocol import (
    MessageType,
    SAFETY_DEVICE_IDENTITY_OK,
    SAFETY_DEVICE_TRANSPORT_ERROR,
    SAFETY_SENSORS_VALID,
    decode_sensor_snapshot,
    decode_status_snapshot,
)
from forgesense_stream import StreamDecoder


class ByteTransport(Protocol):
    def read(self, size: int = 1) -> bytes: ...
    def write(self, data: bytes) -> int: ...


STATE_NAMES = {
    0: "STARTUP",
    1: "RUN",
    2: "WARNING",
    3: "SHUTDOWN",
    4: "FAULT_LATCHED",
    5: "RECOVERY",
}


@dataclass
class SmokeMetrics:
    required_heartbeats: int
    heartbeat_count: int = 0
    echo_sent: int = 0
    echo_ok: int = 0
    echo_timeouts: int = 0
    unexpected_bytes: list[int] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def heartbeat_pass(self) -> bool:
        return self.heartbeat_count >= self.required_heartbeats

    @property
    def echo_pass(self) -> bool:
        return self.echo_sent > 0 and self.echo_ok == self.echo_sent and self.echo_timeouts == 0

    @property
    def echo_error_rate(self) -> float:
        if self.echo_sent == 0:
            return 1.0
        return (self.echo_sent - self.echo_ok) / self.echo_sent

    def latency_summary_ms(self) -> dict[str, float | None]:
        if not self.latencies_ms:
            return {"min": None, "mean": None, "max": None}
        return {
            "min": min(self.latencies_ms),
            "mean": mean(self.latencies_ms),
            "max": max(self.latencies_ms),
        }

    def as_dict(self) -> dict:
        return {
            "heartbeat_count": self.heartbeat_count,
            "required_heartbeats": self.required_heartbeats,
            "heartbeat_pass": self.heartbeat_pass,
            "echo_sent": self.echo_sent,
            "echo_ok": self.echo_ok,
            "echo_timeouts": self.echo_timeouts,
            "echo_error_rate": self.echo_error_rate,
            "unexpected_bytes": [f"0x{x:02X}" for x in self.unexpected_bytes],
            "latency_ms": self.latency_summary_ms(),
            "echo_pass": self.echo_pass,
        }


def _read_until(transport: ByteTransport, deadline: float) -> int | None:
    while time.monotonic() < deadline:
        chunk = transport.read(1)
        if chunk:
            return chunk[0]
    return None


def run_smoke_commissioning(
    transport: ByteTransport,
    *,
    required_heartbeats: int = 2,
    heartbeat_timeout_s: float = 3.0,
    echo_bytes: bytes = b"\xA6\x3C\x81\x00\xFE",
    echo_timeout_s: float = 0.5,
) -> SmokeMetrics:
    if required_heartbeats <= 0:
        raise ValueError("required_heartbeats must be positive")
    if heartbeat_timeout_s <= 0 or echo_timeout_s <= 0:
        raise ValueError("timeouts must be positive")
    if not echo_bytes:
        raise ValueError("echo_bytes must not be empty")

    result = SmokeMetrics(required_heartbeats=required_heartbeats)
    heartbeat_deadline = time.monotonic() + heartbeat_timeout_s
    while result.heartbeat_count < required_heartbeats and time.monotonic() < heartbeat_deadline:
        value = _read_until(transport, heartbeat_deadline)
        if value is None:
            break
        if value == 0x55:
            result.heartbeat_count += 1
        else:
            result.unexpected_bytes.append(value)

    for expected in echo_bytes:
        result.echo_sent += 1
        started = time.monotonic_ns()
        written = transport.write(bytes([expected]))
        if written != 1:
            result.echo_timeouts += 1
            continue
        deadline = time.monotonic() + echo_timeout_s
        matched = False
        while time.monotonic() < deadline:
            value = _read_until(transport, deadline)
            if value is None:
                break
            if value == 0x55:
                result.heartbeat_count += 1
                continue
            if value == expected:
                result.latencies_ms.append((time.monotonic_ns() - started) / 1_000_000.0)
                result.echo_ok += 1
                matched = True
                break
            result.unexpected_bytes.append(value)
        if not matched:
            result.echo_timeouts += 1
    return result


@dataclass
class CommissioningObserver:
    decoder: StreamDecoder = field(default_factory=lambda: StreamDecoder(max_payload=256))
    status_frames: int = 0
    sensor_frames: int = 0
    unknown_frames: int = 0
    latest_status: object | None = None
    latest_sensor: object | None = None
    latest_status_sequence: int | None = None
    latest_sensor_sequence: int | None = None

    def feed(self, chunk: bytes) -> None:
        for frame in self.decoder.feed(chunk):
            if frame.message_type == MessageType.STATUS:
                self.latest_status = decode_status_snapshot(frame)
                self.latest_status_sequence = frame.sequence
                self.status_frames += 1
            elif frame.message_type == MessageType.SENSOR_SNAPSHOT:
                self.latest_sensor = decode_sensor_snapshot(frame)
                self.latest_sensor_sequence = frame.sequence
                self.sensor_frames += 1
            else:
                self.unknown_frames += 1

    @property
    def device_identity_ok(self) -> bool | None:
        if self.latest_status is None:
            return None
        return bool(self.latest_status.safety_flags & SAFETY_DEVICE_IDENTITY_OK)

    @property
    def device_transport_error(self) -> bool | None:
        if self.latest_status is None:
            return None
        return bool(self.latest_status.safety_flags & SAFETY_DEVICE_TRANSPORT_ERROR)

    @property
    def commissioning_pass(self) -> bool:
        if self.latest_status is None or self.latest_sensor is None:
            return False
        return (
            self.status_frames > 0
            and self.sensor_frames > 0
            and self.latest_sensor.all_valid
            and self.device_identity_ok is True
            and self.device_transport_error is False
            and self.decoder.stats.crc_or_frame_errors == 0
        )

    def as_dict(self) -> dict:
        status = self.latest_status
        sensor = self.latest_sensor
        return {
            "commissioning_pass": self.commissioning_pass,
            "frames": {
                "status": self.status_frames,
                "sensor": self.sensor_frames,
                "unknown": self.unknown_frames,
                "crc_or_frame_errors": self.decoder.stats.crc_or_frame_errors,
                "discarded_bytes": self.decoder.stats.discarded_bytes,
            },
            "status": None if status is None else {
                "sequence": self.latest_status_sequence,
                "state_code": status.state_code,
                "state": STATE_NAMES.get(status.state_code, "UNKNOWN"),
                "load_enable": status.load_enable,
                "warning_active": status.warning_active,
                "fault_latched": status.fault_latched,
                "operational_ready": status.operational_ready,
                "sensors_valid": bool(status.safety_flags & SAFETY_SENSORS_VALID),
                "device_identity_ok": self.device_identity_ok,
                "device_transport_error": self.device_transport_error,
                "safety_flags": f"0x{status.safety_flags:04X}",
            },
            "sensor": None if sensor is None else {
                "sequence": self.latest_sensor_sequence,
                "temperature_c": sensor.temperature_c,
                "vibration_rms_g": sensor.vibration_rms_g,
                "current_a": sensor.current_a,
                "all_valid": sensor.all_valid,
                "flags": f"0x{sensor.flags:04X}",
            },
        }


def observe_production_stream(
    transport: ByteTransport,
    *,
    duration_s: float = 3.0,
    chunk_size: int = 128,
) -> CommissioningObserver:
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    observer = CommissioningObserver()
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        chunk = transport.read(chunk_size)
        if chunk:
            observer.feed(chunk)
    return observer


def _find_check(record: dict, check_id: str) -> dict | None:
    for check in record.get("checks", []):
        if check.get("check_id") == check_id:
            return check
    return None


def _upsert_check(record: dict, *, check_id: str, expected: str, observed: str, units: str, passed: bool) -> None:
    check = _find_check(record, check_id)
    if check is None:
        check = {
            "check_id": check_id,
            "result": "NOT_RUN",
            "expected": expected,
            "observed": "",
            "units": units,
            "evidence": [],
        }
        record.setdefault("checks", []).append(check)
    check["expected"] = expected
    check["observed"] = observed
    check["units"] = units
    check["result"] = "PASS" if passed else "FAIL"


def _refresh_overall(record: dict) -> None:
    results = [check.get("result") for check in record.get("checks", [])]
    if any(result == "FAIL" for result in results):
        record["overall_result"] = "FAIL"
    elif results and all(result == "PASS" for result in results):
        record["overall_result"] = "PASS"
    else:
        record["overall_result"] = "INCOMPLETE"


def apply_smoke_to_record(record: dict, metrics: SmokeMetrics) -> dict:
    latency = metrics.latency_summary_ms()
    _upsert_check(
        record,
        check_id="BRINGUP-UART-HEARTBEAT",
        expected="At least the required idle 0x55 heartbeat count is observed",
        observed=f"heartbeats={metrics.heartbeat_count}, required={metrics.required_heartbeats}",
        units="bytes",
        passed=metrics.heartbeat_pass,
    )
    _upsert_check(
        record,
        check_id="BRINGUP-UART-ECHO",
        expected="Every stop-and-wait UART probe byte is echoed correctly",
        observed=(
            f"sent={metrics.echo_sent}, ok={metrics.echo_ok}, timeouts={metrics.echo_timeouts}, "
            f"error_rate={metrics.echo_error_rate:.6f}, mean_latency_ms={latency['mean']}"
        ),
        units="serial",
        passed=metrics.echo_pass,
    )
    _refresh_overall(record)
    return record


def apply_observation_to_record(record: dict, observer: CommissioningObserver) -> dict:
    summary = observer.as_dict()
    status = summary["status"]
    sensor = summary["sensor"]
    frame_errors = observer.decoder.stats.crc_or_frame_errors
    _upsert_check(
        record,
        check_id="COMMISSION-STATUS-STREAM",
        expected="At least one valid FPGA STATUS frame is received",
        observed=f"status_frames={observer.status_frames}, frame_errors={frame_errors}",
        units="frames",
        passed=observer.status_frames > 0,
    )
    sensor_pass = bool(sensor and sensor["all_valid"] and observer.sensor_frames > 0)
    _upsert_check(
        record,
        check_id="COMMISSION-SENSOR-STREAM",
        expected="At least one latest FPGA sensor snapshot is received with all required sensor-valid bits set",
        observed=f"sensor_frames={observer.sensor_frames}, latest={sensor}",
        units="frames",
        passed=sensor_pass,
    )
    identity_pass = bool(status and status["device_identity_ok"] and not status["device_transport_error"])
    _upsert_check(
        record,
        check_id="COMMISSION-DEVICE-IDENTITY",
        expected="Selected sensor identity/configuration checks are good and no device transport error is reported",
        observed=f"status={status}",
        units="status",
        passed=identity_pass,
    )
    _upsert_check(
        record,
        check_id="COMMISSION-LINK-INTEGRITY",
        expected="No complete-frame CRC/framing error is observed during the commissioning window",
        observed=f"crc_or_frame_errors={frame_errors}, discarded_prefix_bytes={observer.decoder.stats.discarded_bytes}",
        units="frames",
        passed=frame_errors == 0,
    )
    _refresh_overall(record)
    return record
