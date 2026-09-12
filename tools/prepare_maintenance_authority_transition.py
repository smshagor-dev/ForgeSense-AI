from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys
import tempfile

try:
    from commissioning.forgesense_commission.authority_transition import (
        MaintenanceAuthorityTransitionError,
        build_transition_request,
    )
except ModuleNotFoundError:
    from forgesense_commission.authority_transition import (  # type: ignore
        MaintenanceAuthorityTransitionError,
        build_transition_request,
    )

DEFAULT_AUDIT_POLICY = Path("hardware/calibration/calibration_audit_ledger_policy_v1.json")
DEFAULT_TRANSITION_POLICY = Path("hardware/calibration/maintenance_authority_transition_policy_v1.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a dual-signature maintenance-authority transition request without accessing private keys"
    )
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--device-state", type=Path, required=True)
    parser.add_argument("--old-public-key", type=Path, required=True)
    parser.add_argument("--new-public-key", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--sdkconfig", type=Path, required=True)
    parser.add_argument("--maintenance-image", type=Path, required=True)
    parser.add_argument("--audit-policy", type=Path, default=DEFAULT_AUDIT_POLICY)
    parser.add_argument("--transition-policy", type=Path, default=DEFAULT_TRANSITION_POLICY)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        artifacts = build_transition_request(
            ledger_dir=args.ledger,
            audit_policy_path=args.audit_policy,
            device_state_path=args.device_state,
            old_public_key_path=args.old_public_key,
            new_public_key_path=args.new_public_key,
            source_commit=args.source_commit,
            repo_root=args.repo_root,
            sdkconfig_path=args.sdkconfig,
            maintenance_image_path=args.maintenance_image,
            transition_policy_path=args.transition_policy,
        )
        out = args.out_dir.resolve()
        if out.exists():
            raise MaintenanceAuthorityTransitionError(f"transition request output already exists: {out}")
        out.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
        try:
            for name, payload in artifacts.items():
                (staging / name).write_bytes(payload)
            staging.rename(out)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        print(out)
        return 0
    except (MaintenanceAuthorityTransitionError, OSError, ValueError) as exc:
        print(f"maintenance-authority transition request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
