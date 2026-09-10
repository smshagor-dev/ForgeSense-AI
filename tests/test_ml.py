from forgesense_ml.baseline import DiagonalGaussianModel, HealthClass
from forgesense_sim.scenarios import build_scenario, run_scenario


def test_baseline_model_separates_severe_bearing_fault() -> None:
    normal = run_scenario(build_scenario("normal"))
    training = [row.feature_vector() for row in normal[80:] if row.all_valid]
    model = DiagonalGaussianModel.fit(training)
    normal_score = model.infer(normal[-1].feature_vector()).anomaly_score
    bearing = run_scenario(build_scenario("bearing_degradation"))
    fault_score = model.infer(bearing[-1].feature_vector()).anomaly_score
    assert normal_score < model.warning_threshold
    assert fault_score > model.critical_threshold
    assert model.infer(bearing[-1].feature_vector()).health_class is HealthClass.CRITICAL


def test_model_artifact_round_trip(tmp_path) -> None:
    normal = run_scenario(build_scenario("normal"))
    model = DiagonalGaussianModel.fit([row.feature_vector() for row in normal[80:]])
    path = tmp_path / "model.json"
    model.save(path)
    loaded = DiagonalGaussianModel.load(path)
    assert loaded == model
