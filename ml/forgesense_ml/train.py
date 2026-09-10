from __future__ import annotations

import argparse
from pathlib import Path

from forgesense_sim.scenarios import build_scenario, run_scenario
from .baseline import DiagonalGaussianModel


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the ForgeSense compact anomaly baseline.")
    parser.add_argument("--out", type=Path, default=Path("build/model.json"))
    args = parser.parse_args()
    baseline = run_scenario(build_scenario("normal"))
    rows = [sample.feature_vector() for sample in baseline if sample.all_valid]
    model = DiagonalGaussianModel.fit(rows)
    model.save(args.out)
    print(f"saved model to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
