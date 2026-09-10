from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct

SOF = b"\xA5\x5A"
PROTOCOL_VERSION = 1
VALID_OBSERVATION = 0x0001

_HEADER = struct.Struct("<2sBBHHI")
_ML_PAYLOAD = struct.Struct("<HHHHHBBH")
_CRC = struct.Struct("<H")


class ProtocolError(ValueError):
    pass


class MessageType(IntEnum):
    ML_OBSERVATION = 0x10
    HEARTBEAT = 0x20
    STATUS = 0x30


class HealthClass(IntEnum):
    NORMAL = 0
    WARNING = 1
    CRITICAL = 2
    ABSTAIN = 3


@dataclass(frozen=True)
class Frame:
    version: int
    message_type: int
    sequence: int
    timestamp_ms: int
    payload: bytes


@dataclass(frozen=True)
class MlObservation:
    model_id: int
    model_version: int
    feature_schema_version: int
    flags: int
    anomaly_score: float
    health_class: HealthClass
    confidence: float
    inference_age_ms: int


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    crc = initial
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_frame(*, message_type: int, sequence: int, timestamp_ms: int, payload: bytes, version: int = PROTOCOL_VERSION) -> bytes:
    if not (0 <= sequence <= 0xFFFF):
        raise ProtocolError("sequence out of range")
    if not (0 <= timestamp_ms <= 0xFFFFFFFF):
        raise ProtocolError("timestamp out of range")
    if len(payload) > 0xFFFF:
        raise ProtocolError("payload too large")
    header = _HEADER.pack(SOF, version, int(message_type), sequence, len(payload), timestamp_ms)
    body = header[2:] + payload
    return header + payload + _CRC.pack(crc16_ccitt(body))


def decode_frame(data: bytes, *, expected_version: int = PROTOCOL_VERSION) -> Frame:
    minimum = _HEADER.size + _CRC.size
    if len(data) < minimum:
        raise ProtocolError("frame truncated")
    sof, version, message_type, sequence, payload_len, timestamp_ms = _HEADER.unpack_from(data)
    if sof != SOF:
        raise ProtocolError("invalid start marker")
    expected_len = _HEADER.size + payload_len + _CRC.size
    if len(data) != expected_len:
        raise ProtocolError("frame length mismatch")
    if version != expected_version:
        raise ProtocolError("unsupported protocol version")
    payload = data[_HEADER.size : _HEADER.size + payload_len]
    received_crc = _CRC.unpack_from(data, _HEADER.size + payload_len)[0]
    calculated_crc = crc16_ccitt(data[2 : _HEADER.size + payload_len])
    if received_crc != calculated_crc:
        raise ProtocolError("CRC mismatch")
    return Frame(version, message_type, sequence, timestamp_ms, payload)


def encode_ml_observation(observation: MlObservation, *, sequence: int, timestamp_ms: int) -> bytes:
    score_q15 = round(min(max(observation.anomaly_score, 0.0), 1.0) * 32767)
    confidence_q8 = round(min(max(observation.confidence, 0.0), 1.0) * 255)
    payload = _ML_PAYLOAD.pack(
        observation.model_id,
        observation.model_version,
        observation.feature_schema_version,
        observation.flags,
        score_q15,
        int(observation.health_class),
        confidence_q8,
        observation.inference_age_ms,
    )
    return encode_frame(message_type=MessageType.ML_OBSERVATION, sequence=sequence, timestamp_ms=timestamp_ms, payload=payload)


def decode_ml_observation(frame: Frame) -> MlObservation:
    if frame.message_type != MessageType.ML_OBSERVATION:
        raise ProtocolError("not an ML observation frame")
    if len(frame.payload) != _ML_PAYLOAD.size:
        raise ProtocolError("invalid ML observation payload length")
    model_id, model_version, schema, flags, score_q15, health, confidence_q8, age_ms = _ML_PAYLOAD.unpack(frame.payload)
    try:
        health_class = HealthClass(health)
    except ValueError as exc:
        raise ProtocolError("invalid health class") from exc
    return MlObservation(
        model_id=model_id,
        model_version=model_version,
        feature_schema_version=schema,
        flags=flags,
        anomaly_score=score_q15 / 32767.0,
        health_class=health_class,
        confidence=confidence_q8 / 255.0,
        inference_age_ms=age_ms,
    )


def sequence_is_newer(candidate: int, previous: int) -> bool:
    delta = (candidate - previous) & 0xFFFF
    return 0 < delta < 0x8000


@dataclass
class FreshnessGate:
    expected_model_id: int
    expected_model_version: int
    expected_feature_schema_version: int
    max_inference_age_ms: int = 1500
    last_sequence: int | None = None

    def accept(self, frame: Frame, observation: MlObservation) -> tuple[bool, str]:
        if not observation.flags & VALID_OBSERVATION:
            return False, "observation-invalid"
        if observation.model_id != self.expected_model_id:
            return False, "model-id"
        if observation.model_version != self.expected_model_version:
            return False, "model-version"
        if observation.feature_schema_version != self.expected_feature_schema_version:
            return False, "feature-schema"
        if observation.inference_age_ms > self.max_inference_age_ms:
            return False, "stale-inference"
        if self.last_sequence is not None and not sequence_is_newer(frame.sequence, self.last_sequence):
            return False, "replay-or-duplicate"
        self.last_sequence = frame.sequence
        return True, "accepted"
