from __future__ import annotations

from forgesense_sim.scenarios import build_scenario, run_scenario

from .baseline import DiagonalGaussianModel

STARTUP_SETTLE_SAMPLES = 80


def reference_training_rows() -> list[tuple[float, float, float]]:
    """Return the complete settled synthetic normal operating envelope.

    This dataset is simulation evidence only. It is never a substitute for
    hardware calibration or representative field data.
    """
    baseline = run_scenario(build_scenario("normal"))
    return [
        sample.feature_vector()
        for sample in baseline[STARTUP_SETTLE_SAMPLES:]
        if sample.all_valid
    ]


def fit_reference_model() -> DiagonalGaussianModel:
    return DiagonalGaussianModel.fit(reference_training_rows())
