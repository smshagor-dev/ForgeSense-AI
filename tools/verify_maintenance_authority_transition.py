from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from commissioning.forgesense_commission.authority_transition import (
        MaintenanceAuthorityTransitionError,
        verify_transition_package,
    )
except ModuleNotFoundError:
    from forgesense_commission.authority_transition import (  # type: ignore
        MaintenanceAuthorityTransitionError,
        verify_transition_package,
    )

DEFAULT_POLICY = Path("hardware/calibration/maintenance_authority_transition_policy_v1.json")


def _policy_id(path: Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise MaintenanceAuthorityTransitionError(f"transition policy is unavailable or invalid: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != "forgesense.maintenance_authority_transition_policy.v1":
        raise MaintenanceAuthorityTransitionError("unsupported maintenance-authority transition policy schema")
    return str(value.get("policy_id", ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a packaged maintenance-authority transition")
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--transition-policy", type=Path, default=DEFAULT_POLICY)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        verified = verify_transition_package(args.package_dir)
        expected_policy = _policy_id(args.transition_policy)
        if verified.request.get("policy_id") != expected_policy:
            raise MaintenanceAuthorityTransitionError("transition request policy_id differs from active transition policy")
        print(
            json.dumps(
                {
                    "schema": "forgesense.maintenance_authority_transition_verification.v1",
                    "device_id": verified.request.get("device_id"),
                    "payload_sha256": verified.payload_sha256,
                    "old_authority_public_key_sha256": verified.old_public_key_sha256,
                    "new_authority_public_key_sha256": verified.new_public_key_sha256,
                    "policy_id": expected_policy,
                    "old_signature_verified": True,
                    "new_proof_of_possession_verified": True,
                    "calibration_state_change_authorized": False,
                    "firmware_write_authorized": False,
                },
                indent=2,
                allow_nan=False,
            )
        )
        return 0
    except (MaintenanceAuthorityTransitionError, OSError, ValueError) as exc:
        print(f"maintenance-authority transition verification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
