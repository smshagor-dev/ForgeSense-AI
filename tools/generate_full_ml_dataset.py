from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from forgesense_ml.full_dataset import generate_full_dataset


def _repo_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git rev-parse failed"
        raise RuntimeError(detail)
    commit = result.stdout.strip().lower()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise RuntimeError("git HEAD is not a full 40-hex commit")
    return commit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the full deterministic ForgeSense synthetic ML dataset v2"
    )
    parser.add_argument("--out-dir", type=Path, default=Path("build/ml-dataset-v2"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--repository-commit", default=None)
    parser.add_argument("--runs-per-scenario", type=int, default=15)
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=None,
        help="optional development/test cap per run; omit for the full dataset",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        commit = (args.repository_commit or _repo_commit(args.repo_root)).lower()
        manifest = generate_full_dataset(
            args.out_dir,
            repository_commit=commit,
            runs_per_scenario=args.runs_per_scenario,
            sample_limit=args.sample_limit,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"full ML dataset generation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "dataset_id": manifest["dataset_id"],
        "output_dir": str(args.out_dir.resolve()),
        "total_runs": manifest["total_runs"],
        "raw_rows": manifest["raw_rows"],
        "window_rows": manifest["window_rows"],
        "baseline_normal_train_rows": manifest["baseline_normal_train_rows"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
