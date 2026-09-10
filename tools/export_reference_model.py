from __future__ import annotations

import argparse
from pathlib import Path

from forgesense_ml.export_cpp import render_cpp_reference_header
from forgesense_ml.reference import fit_reference_model


DEFAULT_OUT = Path(
    "firmware/components/forgesense_inference/include/"
    "forgesense_reference_model_generated.h"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the synthetic reference model as a fixed C++ header."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    model = fit_reference_model()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_cpp_reference_header(model), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
