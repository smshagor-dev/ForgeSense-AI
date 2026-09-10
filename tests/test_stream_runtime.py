from forgesense_protocol import HealthClass, MlObservation, VALID_OBSERVATION
from forgesense_protocol import decode_frame, decode_ml_observation, encode_ml_observation
from forgesense_stream import StreamDecoder
from forgesense_sim.plant import MachinePlant
from forgesense_ml.baseline import DiagonalGaussianModel
from forgesense_ml.runtime import EdgeInferenceRuntime


def _observation(score: float = 0.2) -> MlObservation:
    health = HealthClass.CRITICAL if score >= 0.9 else HealthClass.WARNING if score >= 0.72 else HealthClass.NORMAL
    return MlObservation(1, 1, 1, VALID_OBSERVATION, score, health, 0.9, 0)


def test_stream_decoder_handles_partial_and_back_to_back_frames() -> None:
    first = encode_ml_observation(_observation(0.2), sequence=1, timestamp_ms=100)
    second = encode_ml_observation(_observation(0.8), sequence=2, timestamp_ms=200)
    decoder = StreamDecoder()
    assert decoder.feed(b"\x00\x13garbage" + first[:5]) == []
    frames = decoder.feed(first[5:] + second)
    assert [frame.sequence for frame in frames] == [1, 2]
    assert decoder.stats.frames_ok == 2
    assert decoder.stats.discarded_bytes >= 9


def test_stream_decoder_recovers_after_crc_corruption() -> None:
    bad = bytearray(encode_ml_observation(_observation(0.4), sequence=10, timestamp_ms=1000))
    bad[-1] ^= 0x40
    good = encode_ml_observation(_observation(0.4), sequence=11, timestamp_ms=1100)
    decoder = StreamDecoder()
    frames = decoder.feed(bytes(bad) + good)
    assert [frame.sequence for frame in frames] == [11]
    assert decoder.stats.crc_or_frame_errors >= 1


def test_feature_window_resets_on_invalid_sensor() -> None:
    plant = MachinePlant(seed=10)
    snapshots = []
    for _ in range(120):
        sample = plant.step(load=0.6, dt_s=0.1)
        snapshots.append(plant.sense(sample))
    model = DiagonalGaussianModel.fit([sample.feature_vector() for sample in snapshots[40:100]])
    runtime = EdgeInferenceRuntime(model, window_size=4)
    assert runtime.ingest(snapshots[100]) is None
    assert runtime.ingest(snapshots[101]) is None
    invalid = plant.sense(plant.step(load=0.6, dt_s=0.1), dropout_vibration=True)
    assert runtime.ingest(invalid) is None
    assert runtime.ingest(snapshots[102]) is None
    assert runtime.ingest(snapshots[103]) is None
    assert runtime.ingest(snapshots[104]) is None
    result = runtime.ingest(snapshots[105])
    assert result is not None
    assert result.flags & VALID_OBSERVATION
    encoded = encode_ml_observation(result, sequence=5, timestamp_ms=500)
    assert decode_ml_observation(decode_frame(encoded)).model_id == 1
