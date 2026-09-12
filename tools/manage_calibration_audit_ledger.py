from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from commissioning.forgesense_commission.audit_ledger import (
        CalibrationAuditLedgerError,
        append_authority_transition_evidence,
        append_reboot_evidence,
        append_write_evidence,
        initialize_ledger,
        preflight_live_state,
        verify_ledger,
    )
except ModuleNotFoundError:
    from forgesense_commission.audit_ledger import (  # type: ignore
        CalibrationAuditLedgerError,
        append_authority_transition_evidence,
        append_reboot_evidence,
        append_write_evidence,
        initialize_ledger,
        preflight_live_state,
        verify_ledger,
    )

DEFAULT_POLICY = Path("hardware/calibration/calibration_audit_ledger_policy_v1.json")


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationAuditLedgerError(f"device-state file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationAuditLedgerError(f"device-state file is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CalibrationAuditLedgerError("device-state file must contain a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize, verify, and append ForgeSense calibration audit-ledger evidence"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize a fresh-device audit ledger at calibration sequence zero")
    init.add_argument("--ledger", type=Path, required=True)
    init.add_argument("--device-state", type=Path, required=True)
    init.add_argument("--policy", type=Path, default=DEFAULT_POLICY)

    verify = sub.add_parser("verify", help="verify the complete tamper-evident audit chain")
    verify.add_argument("--ledger", type=Path, required=True)
    verify.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    verify.add_argument("--device-state", type=Path)

    append_write = sub.add_parser(
        "append-write",
        help="append retained committed physical-write evidence after verified audit preflight",
    )
    append_write.add_argument("--ledger", type=Path, required=True)
    append_write.add_argument("--evidence", type=Path, required=True)
    append_write.add_argument("--policy", type=Path, default=DEFAULT_POLICY)

    append_reboot = sub.add_parser(
        "append-reboot",
        help="append retained reboot-verification evidence without changing calibration state",
    )
    append_reboot.add_argument("--ledger", type=Path, required=True)
    append_reboot.add_argument("--evidence", type=Path, required=True)
    append_reboot.add_argument("--policy", type=Path, default=DEFAULT_POLICY)

    append_transition = sub.add_parser(
        "append-authority-transition",
        help="append a dual-signed maintenance-authority transition after read-only post-install verification",
    )
    append_transition.add_argument("--ledger", type=Path, required=True)
    append_transition.add_argument("--transition-package", type=Path, required=True)
    append_transition.add_argument("--post-device-state", type=Path, required=True)
    append_transition.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            state = initialize_ledger(
                args.ledger,
                device_state_path=args.device_state,
                policy_path=args.policy,
            )
        elif args.command == "verify":
            state = verify_ledger(args.ledger, policy_path=args.policy)
            if args.device_state is not None:
                device = _load_json(args.device_state)
                state = preflight_live_state(
                    args.ledger,
                    policy_path=args.policy,
                    device_id=str(device.get("device_id", "")),
                    installed_sequence=int(device.get("installed_sequence", -1)),
                    active_record_sha256=device.get("active_record_sha256"),
                    authority_public_key_sha256=str(
                        device.get("maintenance_authority_public_key_sha256", "")
                    ),
                )
        elif args.command == "append-write":
            state = append_write_evidence(
                args.ledger,
                evidence_path=args.evidence,
                policy_path=args.policy,
            )
        elif args.command == "append-reboot":
            state = append_reboot_evidence(
                args.ledger,
                evidence_path=args.evidence,
                policy_path=args.policy,
            )
        else:
            state = append_authority_transition_evidence(
                args.ledger,
                transition_package_dir=args.transition_package,
                post_device_state_path=args.post_device_state,
                policy_path=args.policy,
            )
        print(json.dumps(state.as_dict(), indent=2, allow_nan=False))
        return 0
    except (CalibrationAuditLedgerError, MaintenanceProvisioningError, ValueError) as exc:
        print(f"calibration audit-ledger operation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
