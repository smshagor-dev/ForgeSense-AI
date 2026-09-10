from __future__ import annotations

import argparse
from pathlib import Path

from forgesense_sim.scenarios import build_scenario, run_scenario
from .baseline import DiagonalGaussianModel

STARTUP_SETTLE_SAMPLES = 80


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the ForgeSense compact anomaly baseline.")
    parser.add_argument("--out", type=Path, default=Path("build/model.json"))
    args = parser.parse_args()

    baseline = run_scenario(build_scenario("normal"))
    settled = baseline[STARTUP_SETTLE_SAMPLES:]
    rows = [sample.feature_vector() for sample in settled if sample.all_valid]
    model = DiagonalGaussianModel.fit(rows)
    model.save(args.out)
    print(f"saved model to {args.out} using {len(rows)} settled baseline samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
