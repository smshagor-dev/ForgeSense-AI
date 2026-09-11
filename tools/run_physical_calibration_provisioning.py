from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import sys

try:
    from commissioning.forgesense_commission.audit_ledger import (
        CalibrationAuditLedgerError,
        append_reboot_evidence,
        append_write_evidence,
        preflight_live_state,
        verify_ledger,
    )
    from commissioning.forgesense_commission.provisioning import MaintenanceProvisioningError
    from commissioning.forgesense_commission.recovery import (
        RECOVERY_INTENT_SCHEMA,
        RecoveryMaintenanceClient,
        apply_recovery_aware_signed_provisioning,
        verify_recovery_aware_reboot,
    )
    from commissioning.forgesense_commission.signed_provisioning import verify_authorization_bundle
except ModuleNotFoundError:
    from forgesense_commission.audit_ledger import (  # type: ignore
        CalibrationAuditLedgerError,
        append_reboot_evidence,
        append_write_evidence,
        preflight_live_state,
        verify_ledger,
    )
    from forgesense_commission.provisioning import MaintenanceProvisioningError  # type: ignore
    from forgesense_commission.recovery import (  # type: ignore
        RECOVERY_INTENT_SCHEMA,
        RecoveryMaintenanceClient,
        apply_recovery_aware_signed_provisioning,
        verify_recovery_aware_reboot,
    )
    from forgesense_commission.signed_provisioning import verify_authorization_bundle  # type: ignore

try:
    from tools.validate_signed_provisioning_policy import (
        SignedProvisioningPolicyError,
        validate_signed_provisioning_policy,
    )
    from tools.verify_calibration_provisioning import (
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )
    from tools.verify_calibration_recovery import (
        CalibrationRecoveryVerificationError,
        verify_recovery_bundle,
    )
except ModuleNotFoundError:
    from validate_signed_provisioning_policy import (  # type: ignore
        SignedProvisioningPolicyError,
        validate_signed_provisioning_policy,
    )
    from verify_calibration_provisioning import (  # type: ignore
        CalibrationProvisioningVerificationError,
        verify_provisioning_bundle,
    )
    from verify_calibration_recovery import (  # type: ignore
        CalibrationRecoveryVerificationError,
        verify_recovery_bundle,
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
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


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
    parser.add_argument("--audit-ledger", type=Path, required=True)
    parser.add_argument(
        "--audit-policy",
        type=Path,
        default=Path("hardware/calibration/calibration_audit_ledger_policy_v1.json"),
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


def _verify_recovery_if_present(args: argparse.Namespace) -> dict | None:
    package = _load_json(args.provisioning_dir / "provisioning.json")
    intent = package.get("intent")
    if intent is None:
        return None
    if not isinstance(intent, dict) or intent.get("schema") != RECOVERY_INTENT_SCHEMA:
        raise MaintenanceProvisioningError("unsupported provisioning intent on physical write path")
    return verify_recovery_bundle(
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
        client = RecoveryMaintenanceClient(serial_port, timeout_s=args.timeout)
        status = client.query_status()
        authorization = client.query_authorization()
        active = client.query_active_record()
    finally:
        serial_port.close()

    if status.has_active != active.present:
        raise MaintenanceProvisioningError("status and active-record readback disagree about active calibration presence")
    if active.present:
        if active.sequence != status.installed_sequence or active.crc32_ieee != status.installed_crc32:
            raise MaintenanceProvisioningError("status and exact active-record readback disagree")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema": DEVICE_STATE_SCHEMA,
        "device_id": status.device_id,
        "captured_at_utc": now,
        "installed_sequence": status.installed_sequence,
        "installed_record_crc32": status.installed_crc32 if status.has_active else None,
        "active_record_sha256": active.sha256,
        "active_record_hex": active.blob.hex() if active.blob is not None else None,
        "maintenance_mode_confirmed": status.maintenance_asserted,
        "load_output_physically_inhibited_confirmed": status.load_inhibit_asserted,
        "maintenance_authorization_ready": authorization.ready,
        "maintenance_authority_public_key_sha256": authorization.public_key_sha256,
        "source": "dedicated signed calibration maintenance firmware exact readback",
        "note": (
            "Read-only status capture from eFuse MAC, exact active CalibrationRecord bytes, calibration NVS state, "
            "physical gate GPIOs, and pinned maintenance-authority public-key state. Physical gates, active record, "
            "authorization, and audit-ledger continuity are rechecked at write time."
        ),
        "maintenance_readback": status.as_dict(),
    }


def _preflight_audit_ledger(args: argparse.Namespace, client: RecoveryMaintenanceClient) -> dict:
    package = _load_json(args.provisioning_dir / "provisioning.json")
    device_id = str(package.get("device_id", ""))
    structural = verify_ledger(
        args.audit_ledger,
        policy_path=args.audit_policy,
        expected_device_id=device_id,
    )
    status = client.query_status()
    authorization = client.query_authorization()
    active = client.query_active_record()
    if status.device_id != device_id:
        raise CalibrationAuditLedgerError("live device identity differs from provisioning/audit-ledger device")
    if status.has_active != active.present:
        raise CalibrationAuditLedgerError("live status and active-record readback disagree during audit preflight")
    if active.present and (
        active.sequence != status.installed_sequence or active.crc32_ieee != status.installed_crc32
    ):
        raise CalibrationAuditLedgerError("live exact active record differs from status during audit preflight")
    live = preflight_live_state(
        args.audit_ledger,
        policy_path=args.audit_policy,
        device_id=status.device_id,
        installed_sequence=status.installed_sequence,
        active_record_sha256=active.sha256,
        authority_public_key_sha256=authorization.public_key_sha256,
    )
    if live != structural:
        raise CalibrationAuditLedgerError("audit ledger changed during preflight verification")
    return live.as_dict()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ForgeSense signed maintenance-only physical calibration provisioning utility"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser(
        "status",
        help=(
            "read device identity, exact active calibration record, physical gates, and signer fingerprint; "
            "performs no write"
        ),
    )
    _add_serial_args(status)
    status.add_argument("--report-out", type=Path, required=True)

    apply = sub.add_parser(
        "apply",
        help=(
            "verify evidence, audit-ledger continuity, recovery intent when present, and external signature, then "
            "perform one physically gated signed calibration write"
        ),
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
        help=(
            "verify retained sequence/CRC/exact active record after a manual reboot or power cycle and append a "
            "non-mutating audit event; performs no write"
        ),
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

        validate_signed_provisioning_policy(args.provisioning_policy)

        verification = _verify_package(args)
        if verification.get("record_rederived") is not True or verification.get("anti_rollback_gate_pass") is not True:
            raise MaintenanceProvisioningError("provisioning verification did not establish record/sequence integrity")
        recovery_verification = _verify_recovery_if_present(args)

        package = _load_json(args.provisioning_dir / "provisioning.json")
        pre_serial_ledger = verify_ledger(
            args.audit_ledger,
            policy_path=args.audit_policy,
            expected_device_id=str(package.get("device_id", "")),
        )

        authorization = None
        if args.command == "apply":
            if args.confirm_write != WRITE_CONFIRMATION:
                raise MaintenanceProvisioningError(
                    f"physical write requires exact --confirm-write {WRITE_CONFIRMATION}"
                )
            authorization = verify_authorization_bundle(
                args.authorization_dir,
                provisioning_dir=args.provisioning_dir,
                public_key_path=args.authority_public_key,
            )

        serial_port = _serial_port(args.port, args.baud, args.timeout)
        try:
            if hasattr(serial_port, "reset_input_buffer"):
                serial_port.reset_input_buffer()
            client = RecoveryMaintenanceClient(serial_port, timeout_s=args.timeout)
            live_ledger = _preflight_audit_ledger(args, client)
            if live_ledger["head_sha256"] != pre_serial_ledger.head_sha256:
                raise CalibrationAuditLedgerError("audit ledger head changed between structural and live preflight")
            if args.command == "apply":
                if authorization is None:
                    raise MaintenanceProvisioningError("verified signed authorization is missing")
                report = apply_recovery_aware_signed_provisioning(
                    client,
                    args.provisioning_dir,
                    authorization=authorization,
                    operator=args.operator,
                )
            else:
                prior = _load_json(args.evidence)
                report = verify_recovery_aware_reboot(client, prior)
        finally:
            serial_port.close()

        report["host_verification"] = {
            "schema": verification.get("schema"),
            "record_rederived": verification.get("record_rederived") is True,
            "source_derivation_reverified": verification.get("source_derivation_reverified") is True,
            "anti_rollback_gate_pass": verification.get("anti_rollback_gate_pass") is True,
            "hard_safety_non_regression_pass": verification.get("hard_safety_non_regression_pass") is True,
            "external_signature_verified_before_transport": authorization is not None,
            "recovery_intent_present": recovery_verification is not None,
            "recovery_monotonic_sequence_verified": (
                recovery_verification is not None
                and recovery_verification.get("monotonic_sequence_preserved") is True
            ),
            "audit_ledger_required": True,
            "audit_ledger_preflight_verified": True,
            "audit_ledger_head_before_operation": live_ledger["head_sha256"],
            "audit_ledger_entry_count_before_operation": live_ledger["entry_count"],
        }

        # Retain the physical evidence before appending its hash into the ledger.
        # If the append fails after a successful device write, this file remains
        # available for explicit ledger reconciliation; history is never silently rewritten.
        _save_json(args.report_out, report)
        if args.command == "apply":
            ledger_after = append_write_evidence(
                args.audit_ledger,
                evidence_path=args.report_out,
                policy_path=args.audit_policy,
            )
        else:
            ledger_after = append_reboot_evidence(
                args.audit_ledger,
                evidence_path=args.report_out,
                policy_path=args.audit_policy,
            )

        output = dict(report)
        output["audit_ledger_append"] = {
            "entry_count": ledger_after.entry_count,
            "head_sha256": ledger_after.head_sha256,
            "sequence": ledger_after.sequence,
            "record_sha256": ledger_after.record_sha256,
            "authority_public_key_sha256": ledger_after.authority_public_key_sha256,
        }
        print(json.dumps(output, indent=2, allow_nan=False))
        return 0
    except (
        MaintenanceProvisioningError,
        CalibrationProvisioningVerificationError,
        CalibrationRecoveryVerificationError,
        SignedProvisioningPolicyError,
        CalibrationAuditLedgerError,
    ) as exc:
        print(f"physical calibration provisioning failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
