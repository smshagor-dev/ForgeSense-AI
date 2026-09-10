from __future__ import annotations

import json
from typing import Any

PREFIX = "@FS1 "
SCHEMA = "forgesense.edge.telemetry.v1"
MAX_LINE_BYTES = 4096


def _require_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} out of range")
    return value


def _object_or_none(value: Any, name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object or null")
    return value


def decode_device_line(line: bytes | str) -> dict[str, Any]:
    if isinstance(line, bytes):
        if len(line) > MAX_LINE_BYTES:
            raise ValueError("device telemetry line too large")
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("device telemetry is not valid UTF-8") from exc
    elif isinstance(line, str):
        text = line
        if len(text.encode("utf-8")) > MAX_LINE_BYTES:
            raise ValueError("device telemetry line too large")
    else:
        raise TypeError("line must be bytes or str")

    text = text.strip()
    if not text.startswith(PREFIX):
        raise ValueError("not a ForgeSense device telemetry record")
    try:
        payload = json.loads(text[len(PREFIX) :])
    except json.JSONDecodeError as exc:
        raise ValueError("invalid device telemetry JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("device telemetry payload must be an object")
    if payload.get("schema") != SCHEMA:
        raise ValueError("unsupported device telemetry schema")

    _require_int(payload.get("revision"), "revision", 0, 0xFFFFFFFF)
    _require_int(payload.get("device_ms"), "device_ms", 0, 0xFFFFFFFF)

    sensor = _object_or_none(payload.get("sensor"), "sensor")
    if sensor is not None:
        _require_int(sensor.get("sequence"), "sensor.sequence", 0, 0xFFFF)
        _require_int(sensor.get("source_timestamp_ms"), "sensor.source_timestamp_ms", 0, 0xFFFFFFFF)
        _require_int(sensor.get("received_age_ms"), "sensor.received_age_ms", 0, 0xFFFFFFFF)
        _require_int(sensor.get("temperature_deci_c"), "sensor.temperature_deci_c", -32768, 32767)
        _require_int(sensor.get("vibration_milli_g"), "sensor.vibration_milli_g", 0, 0xFFFF)
        _require_int(sensor.get("current_milli_a"), "sensor.current_milli_a", 0, 0xFFFF)
        _require_int(sensor.get("flags"), "sensor.flags", 0, 0xFFFF)

    status = _object_or_none(payload.get("fpga_status"), "fpga_status")
    if status is not None:
        _require_int(status.get("sequence"), "fpga_status.sequence", 0, 0xFFFF)
        _require_int(status.get("source_timestamp_ms"), "fpga_status.source_timestamp_ms", 0, 0xFFFFFFFF)
        _require_int(status.get("received_age_ms"), "fpga_status.received_age_ms", 0, 0xFFFFFFFF)
        _require_int(status.get("state_code"), "fpga_status.state_code", 0, 5)
        _require_int(status.get("control_flags"), "fpga_status.control_flags", 0, 0xFF)
        _require_int(status.get("safety_flags"), "fpga_status.safety_flags", 0, 0xFFFF)

    ml = _object_or_none(payload.get("ml"), "ml")
    if ml is not None:
        _require_int(ml.get("sequence"), "ml.sequence", 0, 0xFFFF)
        _require_int(ml.get("source_timestamp_ms"), "ml.source_timestamp_ms", 0, 0xFFFFFFFF)
        _require_int(ml.get("received_age_ms"), "ml.received_age_ms", 0, 0xFFFFFFFF)
        _require_int(ml.get("model_id"), "ml.model_id", 0, 0xFFFF)
        _require_int(ml.get("model_version"), "ml.model_version", 0, 0xFFFF)
        _require_int(ml.get("feature_schema_version"), "ml.feature_schema_version", 0, 0xFFFF)
        _require_int(ml.get("flags"), "ml.flags", 0, 0xFFFF)
        _require_int(ml.get("anomaly_q15"), "ml.anomaly_q15", 0, 32767)
        _require_int(ml.get("health_class"), "ml.health_class", 0, 3)
        _require_int(ml.get("confidence_q8"), "ml.confidence_q8", 0, 0xFF)
        _require_int(ml.get("inference_age_ms"), "ml.inference_age_ms", 0, 0xFFFF)

    link = payload.get("link")
    if not isinstance(link, dict):
        raise ValueError("link must be an object")
    for key in (
        "accepted_fpga_frames",
        "rejected_fpga_frames",
        "stale_sensor_frames",
        "stale_status_frames",
        "dropped_pending_messages",
    ):
        _require_int(link.get(key), f"link.{key}", 0, 0xFFFFFFFF)
    return payload


def ingest_device_packet(store, packet: dict[str, Any], *, max_source_age_ms: int = 2000) -> None:
    if max_source_age_ms < 1:
        raise ValueError("max_source_age_ms must be positive")

    from forgesense_protocol import (
        HealthClass,
        MlObservation,
        SensorSnapshotWire,
        StatusSnapshotWire,
    )

    sensor = packet.get("sensor")
    if sensor is not None and sensor["received_age_ms"] <= max_source_age_ms:
        store.ingest_sensor(
            SensorSnapshotWire(
                temperature_deci_c=sensor["temperature_deci_c"],
                vibration_milli_g=sensor["vibration_milli_g"],
                current_milli_a=sensor["current_milli_a"],
                flags=sensor["flags"],
            ),
            sequence=sensor["sequence"],
            source_timestamp_ms=sensor["source_timestamp_ms"],
        )

    status = packet.get("fpga_status")
    if status is not None and status["received_age_ms"] <= max_source_age_ms:
        store.ingest_status(
            StatusSnapshotWire(
                state_code=status["state_code"],
                control_flags=status["control_flags"],
                safety_flags=status["safety_flags"],
            ),
            sequence=status["sequence"],
            source_timestamp_ms=status["source_timestamp_ms"],
        )

    ml = packet.get("ml")
    if ml is not None and ml["received_age_ms"] <= max_source_age_ms:
        store.ingest_ml(
            MlObservation(
                model_id=ml["model_id"],
                model_version=ml["model_version"],
                feature_schema_version=ml["feature_schema_version"],
                flags=ml["flags"],
                anomaly_score=ml["anomaly_q15"] / 32767.0,
                health_class=HealthClass(ml["health_class"]),
                confidence=ml["confidence_q8"] / 255.0,
                inference_age_ms=ml["inference_age_ms"],
            ),
            sequence=ml["sequence"],
            source_timestamp_ms=ml["source_timestamp_ms"],
        )
