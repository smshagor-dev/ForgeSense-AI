from forgesense_protocol import (
    FreshnessGate,
    HealthClass,
    MlObservation,
    ProtocolError,
    VALID_OBSERVATION,
    decode_frame,
    decode_ml_observation,
    encode_ml_observation,
    sequence_is_newer,
)


def _observation(age_ms: int = 20) -> MlObservation:
    return MlObservation(1, 1, 1, VALID_OBSERVATION, 0.8125, HealthClass.WARNING, 0.88, age_ms)


def test_ml_round_trip_and_crc_rejection() -> None:
    encoded = encode_ml_observation(_observation(age_ms=25), sequence=7, timestamp_ms=12345)
    assert encoded.hex() == "a55a011007000e00393000000100010001000100ff6701e01900e3c8"
    frame = decode_frame(encoded)
    decoded = decode_ml_observation(frame)
    assert frame.sequence == 7
    assert abs(decoded.anomaly_score - 0.8125) < 1e-4
    assert decoded.health_class is HealthClass.WARNING
    corrupted = bytearray(encoded)
    corrupted[-3] ^= 0x01
    try:
        decode_frame(bytes(corrupted))
    except ProtocolError as exc:
        assert "CRC" in str(exc)
    else:
        raise AssertionError("corrupted frame was accepted")


def test_freshness_gate_rejects_duplicate_and_stale_observation() -> None:
    gate = FreshnessGate(1, 1, 1, max_inference_age_ms=1000)
    frame = decode_frame(encode_ml_observation(_observation(), sequence=100, timestamp_ms=1))
    obs = decode_ml_observation(frame)
    assert gate.accept(frame, obs) == (True, "accepted")
    assert gate.accept(frame, obs) == (False, "replay-or-duplicate")
    stale_frame = decode_frame(encode_ml_observation(_observation(age_ms=1001), sequence=101, timestamp_ms=2))
    assert gate.accept(stale_frame, decode_ml_observation(stale_frame)) == (False, "stale-inference")


def test_sequence_wrap_is_supported() -> None:
    assert sequence_is_newer(0, 65535)
    assert not sequence_is_newer(65535, 0)
