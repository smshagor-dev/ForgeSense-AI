from forgesense_protocol import (
    SENSOR_ALL_VALID,
    SensorSnapshotWire,
    decode_frame,
    decode_sensor_snapshot,
    encode_sensor_snapshot,
)


def test_sensor_snapshot_cross_language_golden_frame() -> None:
    snapshot = SensorSnapshotWire(
        temperature_deci_c=287,
        vibration_milli_g=142,
        current_milli_a=1460,
        flags=SENSOR_ALL_VALID,
    )
    encoded = encode_sensor_snapshot(
        snapshot,
        sequence=0x1234,
        timestamp_ms=0x01020304,
    )
    assert encoded.hex() == "a55a011134120800040302011f018e00b4050700d9b7"
    frame = decode_frame(encoded)
    decoded = decode_sensor_snapshot(frame)
    assert decoded == snapshot
    assert decoded.all_valid
    assert decoded.feature_vector() == (28.7, 0.142, 1.46)


def test_sensor_validity_is_explicit() -> None:
    snapshot = SensorSnapshotWire(
        temperature_deci_c=-25,
        vibration_milli_g=0,
        current_milli_a=0,
        flags=0,
    )
    frame = decode_frame(
        encode_sensor_snapshot(snapshot, sequence=1, timestamp_ms=0)
    )
    decoded = decode_sensor_snapshot(frame)
    assert not decoded.all_valid
