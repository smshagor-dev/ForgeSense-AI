from __future__ import annotations

import argparse
from pathlib import Path

from .reference import fit_reference_model, reference_training_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the ForgeSense compact anomaly baseline.")
    parser.add_argument("--out", type=Path, default=Path("build/model.json"))
    args = parser.parse_args()

    rows = reference_training_rows()
    model = fit_reference_model()
    model.save(args.out)
    print(f"saved model to {args.out} using {len(rows)} settled baseline samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
