from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .scenarios import build_scenario, run_scenario


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic ForgeSense AI virtual machine scenario.")
    parser.add_argument("scenario", choices=["normal", "bearing_degradation", "overcurrent", "cooling_loss", "sensor_dropout"])
    parser.add_argument("--out", type=Path, help="Optional JSONL output path.")
    args = parser.parse_args()
    snapshots = run_scenario(build_scenario(args.scenario))
    rows = [asdict(sample) for sample in snapshots]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        print(f"wrote {len(rows)} samples to {args.out}")
    else:
        print(json.dumps(rows[-1], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
