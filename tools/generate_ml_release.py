from __future__ import annotations

import argparse
from pathlib import Path

from forgesense_ml.release import write_release_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic ForgeSense synthetic dataset and ML evaluation artifacts")
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("build/ml-release"))
    args = parser.parse_args()
    write_release_artifacts(args.out_dir, repository_commit=args.repository_commit)
    print(args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
