from __future__ import annotations

from forgesense_ml.baseline import DiagonalGaussianModel
from forgesense_protocol import FreshnessGate, HealthClass as ProtocolHealthClass, MlObservation, VALID_OBSERVATION, decode_frame, decode_ml_observation, encode_ml_observation
from forgesense_sim.scenarios import build_scenario, run_scenario


def main() -> int:
    baseline = run_scenario(build_scenario("normal"))
    model = DiagonalGaussianModel.fit([row.feature_vector() for row in baseline[80:]])
    scenario = run_scenario(build_scenario("bearing_degradation"))
    gate = FreshnessGate(model.model_id, model.model_version, model.feature_schema_version)
    accepted = 0
    first_critical: int | None = None
    startup_samples = 80
    for seq, sample in enumerate(scenario):
        if sample.sample_index < startup_samples or not sample.all_valid:
            continue
        result = model.infer(sample.feature_vector())
        observation = MlObservation(
            model_id=model.model_id,
            model_version=model.model_version,
            feature_schema_version=model.feature_schema_version,
            flags=VALID_OBSERVATION,
            anomaly_score=result.anomaly_score,
            health_class=ProtocolHealthClass(int(result.health_class)),
            confidence=result.confidence,
            inference_age_ms=25,
        )
        packet = encode_ml_observation(observation, sequence=seq & 0xFFFF, timestamp_ms=round(sample.time_s * 1000) & 0xFFFFFFFF)
        frame = decode_frame(packet)
        decoded = decode_ml_observation(frame)
        ok, _ = gate.accept(frame, decoded)
        accepted += int(ok)
        if ok and decoded.health_class is ProtocolHealthClass.CRITICAL and first_critical is None:
            first_critical = sample.sample_index
    print({"scenario": "bearing_degradation", "samples": len(scenario), "accepted_observations": accepted, "first_critical_sample": first_critical, "final_anomaly_score": round(model.infer(scenario[-1].feature_vector()).anomaly_score, 5)})
    if first_critical is None:
        raise SystemExit("virtual demo failed to detect the injected degradation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
