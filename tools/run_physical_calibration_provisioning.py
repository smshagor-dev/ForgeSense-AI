from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

try:
    from commissioning.forgesense_commission.provisioning import (
        MaintenanceProvisioningError,
        verify_reboot_recovery,
    )
    from commissioning.forgesense_commission.signed_provisioning import (
        SignedMaintenanceClient,
        apply_signed_provisioning,
        verify_authorization_bundle,
    )
except ModuleNotFoundError:
    from forgesense_commission.provisioning import (  # type: ignore
        MaintenanceProvisioningError,
        verify_reboot_recovery,
    )
    from forgesense_commission.signed_provisioning import (  # type: ignore
        SignedMaintenanceClient,
        apply_signed_provisioning,
        verify_authorization_bundle,
    )

try:
    from tools.verify_calibration_provisioning import (
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )
except ModuleNotFoundError:
    from verify_calibration_provisioning import (  # type: ignore
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )

WRITE_CONFIRMATION = "CALIBRATION-WRITE"
DEVICE_STATE_SCHEMA = "forgesense.calibration_device_state.v1"


def _serial_port(name: str, baud: int, timeout: float):
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise MaintenanceProvisioningError(
            "pyserial is required for physical calibration maintenance: install requirements-device.txt"
        ) from exc
    return serial.Serial(name, baudrate=baud, timeout=timeout, write_timeout=timeout)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError(f"evidence file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MaintenanceProvisioningError(f"evidence file is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MaintenanceProvisioningError("evidence file must contain a JSON object")
    return value


def _add_serial_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=1.0)


def _add_verification_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("provisioning_dir", type=Path)
    parser.add_argument("--source-change-dir", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--change-package-dir", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--source-change-policy",
        type=Path,
        default=Path("hardware/calibration/calibration_source_change_policy_v1.json"),
    )
    parser.add_argument("--device-state", type=Path, required=True)
    parser.add_argument(
        "--provisioning-policy",
        type=Path,
        default=Path("hardware/calibration/calibration_provisioning_policy_v1.json"),
    )


def _verify_package(args: argparse.Namespace) -> dict:
    return verify_provisioning_bundle(
        args.provisioning_dir,
        source_change_dir=args.source_change_dir,
        bundle_dir=args.bundle,
        change_package_dir=args.change_package_dir,
        approval_path=args.approval,
        source_root=args.source_root,
        campaign_manifest=args.campaign_manifest,
        repo_root=args.repo_root,
        source_change_policy_path=args.source_change_policy,
        device_state_path=args.device_state,
        provisioning_policy_path=args.provisioning_policy,
    )


def _capture_device_state(args: argparse.Namespace) -> dict:
    serial_port = _serial_port(args.port, args.baud, args.timeout)
    try:
        if hasattr(serial_port, "reset_input_buffer"):
            serial_port.reset_input_buffer()
        client = SignedMaintenanceClient(serial_port, timeout_s=args.timeout)
        status = client.query_status()
        authorization = client.query_authorization()
    finally:
        serial_port.close()

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema": DEVICE_STATE_SCHEMA,
        "device_id": status.device_id,
        "captured_at_utc": now,
        "installed_sequence": status.installed_sequence,
        "installed_record_crc32": status.installed_crc32 if status.has_active else None,
        "maintenance_mode_confirmed": status.maintenance_asserted,
        "load_output_physically_inhibited_confirmed": status.load_inhibit_asserted,
        "maintenance_authorization_ready": authorization.ready,
        "maintenance_authority_public_key_sha256": authorization.public_key_sha256,
        "source": "dedicated signed calibration maintenance firmware readback",
        "note": (
            "Read-only status capture from eFuse MAC, calibration NVS state, physical gate GPIOs, and pinned "
            "maintenance-authority public-key state. Physical gates and authorization are rechecked at write time."
        ),
        "maintenance_readback": status.as_dict(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ForgeSense signed maintenance-only physical calibration provisioning utility"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser(
        "status",
        help="read device identity, calibration state, physical gates, and signer fingerprint; performs no write",
    )
    _add_serial_args(status)
    status.add_argument("--report-out", type=Path, required=True)

    apply = sub.add_parser(
        "apply",
        help="verify evidence and external signature, then perform one physically gated signed calibration write",
    )
    _add_verification_args(apply)
    _add_serial_args(apply)
    apply.add_argument("--authorization-dir", type=Path, required=True)
    apply.add_argument("--authority-public-key", type=Path, required=True)
    apply.add_argument("--operator", required=True)
    apply.add_argument("--confirm-write", required=True)
    apply.add_argument("--report-out", type=Path, required=True)

    reboot = sub.add_parser(
        "verify-reboot",
        help="verify retained sequence/CRC after a manual reboot or power cycle; performs no write",
    )
    _add_verification_args(reboot)
    _add_serial_args(reboot)
    reboot.add_argument("--evidence", type=Path, required=True)
    reboot.add_argument("--report-out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            report = _capture_device_state(args)
            _save_json(args.report_out, report)
            print(json.dumps(report, indent=2, allow_nan=False))
            return 0

        # Full source/evidence derivation and provisioning-bundle integrity must
        # pass before any bundle-bound serial operation opens the device.
        verification = _verify_package(args)
        if verification.get("record_rederived") is not True or verification.get("anti_rollback_gate_pass") is not True:
            raise MaintenanceProvisioningError("provisioning verification did not establish record/sequence integrity")

        authorization = None
        if args.command == "apply":
            if args.confirm_write != WRITE_CONFIRMATION:
                raise MaintenanceProvisioningError(
                    f"physical write requires exact --confirm-write {WRITE_CONFIRMATION}"
                )
            # External signature verification also completes before the serial
            # port is opened. Device-side verification is then required again.
            authorization = verify_authorization_bundle(
                args.authorization_dir,
                provisioning_dir=args.provisioning_dir,
                public_key_path=args.authority_public_key,
            )

        serial_port = _serial_port(args.port, args.baud, args.timeout)
        try:
            if hasattr(serial_port, "reset_input_buffer"):
                serial_port.reset_input_buffer()
            client = SignedMaintenanceClient(serial_port, timeout_s=args.timeout)
            if args.command == "apply":
                if authorization is None:
                    raise MaintenanceProvisioningError("verified signed authorization is missing")
                report = apply_signed_provisioning(
                    client,
                    args.provisioning_dir,
                    authorization=authorization,
                    operator=args.operator,
                )
            else:
                prior = _load_json(args.evidence)
                report = verify_reboot_recovery(client, prior)
        finally:
            serial_port.close()

        report["host_verification"] = {
            "schema": verification.get("schema"),
            "record_rederived": verification.get("record_rederived") is True,
            "source_derivation_reverified": verification.get("source_derivation_reverified") is True,
            "anti_rollback_gate_pass": verification.get("anti_rollback_gate_pass") is True,
            "hard_safety_non_regression_pass": verification.get("hard_safety_non_regression_pass") is True,
            "external_signature_verified_before_transport": authorization is not None,
        }
        _save_json(args.report_out, report)
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0
    except (MaintenanceProvisioningError, CalibrationProvisioningVerificationError) as exc:
        print(f"physical calibration provisioning failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
