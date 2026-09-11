from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import zlib

try:
    from tools.verify_calibration_source_derivation import (
        CalibrationSourceDerivationError,
        verify_source_derivation,
    )
except ModuleNotFoundError:  # Direct execution from repository root.
    from verify_calibration_source_derivation import CalibrationSourceDerivationError, verify_source_derivation

PROVISIONING_SCHEMA = "forgesense.calibration_provisioning_package.v1"
POLICY_SCHEMA = "forgesense.calibration_provisioning_policy.v1"
DEVICE_STATE_SCHEMA = "forgesense.calibration_device_state.v1"
ARTIFACT_INDEX_SCHEMA = "forgesense.calibration_provisioning_artifact_index.v1"
PROFILE_SCHEMA = "forgesense.approved_calibration_source_profile.v1"
SOURCE_CHANGE_SCHEMA = "forgesense.calibration_source_change.v1"
CAL_MAGIC = 0x46534331
CAL_VERSION = 1
CAL_BLOB_SIZE = 48
RAW24_MIN = -8388608
RAW24_MAX = 8388607
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1
UINT32_MAX = 2**32 - 1


class CalibrationProvisioningError(ValueError):
    pass


def _json_bytes(data: dict) -> bytes:
    return (json.dumps(data, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _canonical_sha256(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise CalibrationProvisioningError(f"required file not found: {path}") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationProvisioningError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationProvisioningError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CalibrationProvisioningError(f"{label} must contain a JSON object")
    return value


def _validate_utc(value: object, label: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalibrationProvisioningError(f"{label} must be valid ISO-8601 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise CalibrationProvisioningError(f"{label} must include UTC timezone")
    return text


def _validate_policy(policy: dict) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise CalibrationProvisioningError("unsupported calibration provisioning policy schema")
    sequence = policy.get("sequence")
    record = policy.get("record")
    storage = policy.get("storage")
    preconditions = policy.get("preconditions")
    authority = policy.get("authority")
    if not all(isinstance(item, dict) for item in (sequence, record, storage, preconditions, authority)):
        raise CalibrationProvisioningError("provisioning policy sections are incomplete")
    if sequence.get("strictly_newer_than_installed") is not True or sequence.get("wraparound_supported") is not False:
        raise CalibrationProvisioningError("provisioning policy must require strict non-wrapping sequence increase")
    minimum = int(sequence.get("minimum", -1))
    maximum = int(sequence.get("maximum", -1))
    if minimum < 1 or maximum > UINT32_MAX - 1 or minimum > maximum:
        raise CalibrationProvisioningError("provisioning sequence bounds are invalid")
    if record.get("format") != "CalibrationRecord-v1" or int(record.get("blob_size_bytes", 0)) != CAL_BLOB_SIZE:
        raise CalibrationProvisioningError("provisioning record contract does not match CalibrationRecord v1")
    if record.get("byte_order") != "little-endian" or record.get("integrity") != "CRC32/IEEE":
        raise CalibrationProvisioningError("provisioning record encoding contract is invalid")
    if int(storage.get("slot_count", 0)) != 2 or storage.get("highest-valid-sequence-recovery") is not True:
        raise CalibrationProvisioningError("provisioning storage must use two-slot highest-sequence recovery")
    if storage.get("same-sequence-different-bytes_rejected") is not True:
        raise CalibrationProvisioningError("provisioning storage must reject ambiguous equal-sequence records")
    if preconditions.get("maintenance_mode_confirmation_required") is not True:
        raise CalibrationProvisioningError("maintenance-mode confirmation must be required")
    if preconditions.get("load_output_physically_inhibited_confirmation_required") is not True:
        raise CalibrationProvisioningError("physical load-output inhibition confirmation must be required")
    if preconditions.get("write_time_recheck_required") is not True:
        raise CalibrationProvisioningError("write-time precondition recheck must be required")
    expected_authority = {
        "remote_provisioning_command_present": False,
        "automatic_provisioning": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
        "hardware_backed_monotonic_counter_claimed": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) is not expected:
            raise CalibrationProvisioningError(f"provisioning policy authority field {key} is invalid")


def _validate_device_state(state: dict, policy: dict) -> int:
    if state.get("schema") != DEVICE_STATE_SCHEMA:
        raise CalibrationProvisioningError("unsupported calibration device-state schema")
    if not str(state.get("device_id", "")).strip():
        raise CalibrationProvisioningError("device_state.device_id is required")
    _validate_utc(state.get("captured_at_utc"), "device_state.captured_at_utc")
    try:
        installed = int(state.get("installed_sequence"))
    except (TypeError, ValueError) as exc:
        raise CalibrationProvisioningError("device_state.installed_sequence must be an integer") from exc
    if installed < 0 or installed > int(policy["sequence"]["maximum"]):
        raise CalibrationProvisioningError("device_state.installed_sequence is outside policy range")
    if state.get("maintenance_mode_confirmed") is not True:
        raise CalibrationProvisioningError("maintenance mode must be explicitly confirmed")
    if state.get("load_output_physically_inhibited_confirmed") is not True:
        raise CalibrationProvisioningError("physical load-output inhibition must be explicitly confirmed")
    if not str(state.get("source", "")).strip():
        raise CalibrationProvisioningError("device_state.source is required")
    return installed


def _int32(value: object, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise CalibrationProvisioningError(f"{label} must be an integer") from exc
    if result < INT32_MIN or result > INT32_MAX:
        raise CalibrationProvisioningError(f"{label} exceeds signed 32-bit range")
    return result


def _linear_fields(mapping: object, label: str) -> tuple[int, int, int, int]:
    if not isinstance(mapping, dict):
        raise CalibrationProvisioningError(f"{label} calibration mapping is missing")
    raw_zero = _int32(mapping.get("raw_zero"), f"{label}.raw_zero")
    numerator = _int32(mapping.get("gain_numerator"), f"{label}.gain_numerator")
    denominator = _int32(mapping.get("gain_denominator"), f"{label}.gain_denominator")
    offset = _int32(mapping.get("output_offset"), f"{label}.output_offset")
    if raw_zero < RAW24_MIN or raw_zero > RAW24_MAX:
        raise CalibrationProvisioningError(f"{label}.raw_zero exceeds signed 24-bit range")
    if denominator <= 0:
        raise CalibrationProvisioningError(f"{label}.gain_denominator must be positive")
    return raw_zero, numerator, denominator, offset


def encode_calibration_record(profile: dict, sequence: int) -> bytes:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise CalibrationProvisioningError("unsupported approved calibration profile schema")
    record = profile.get("calibration_record_v1_candidate")
    if not isinstance(record, dict):
        raise CalibrationProvisioningError("approved profile calibration_record_v1_candidate is missing")
    temperature = _linear_fields(record.get("temperature"), "temperature")
    current = _linear_fields(record.get("current"), "current")
    prefix = struct.pack(
        "<IHHIiiiiiiii",
        CAL_MAGIC,
        CAL_VERSION,
        CAL_BLOB_SIZE,
        sequence,
        *temperature,
        *current,
    )
    if len(prefix) != 44:
        raise CalibrationProvisioningError("internal CalibrationRecord prefix size mismatch")
    crc = zlib.crc32(prefix) & UINT32_MAX
    return prefix + struct.pack("<I", crc)


def build_provisioning_bundle(
    source_change_dir: Path,
    *,
    bundle_dir: Path,
    change_package_dir: Path,
    approval_path: Path,
    source_root: Path,
    campaign_manifest: Path,
    repo_root: Path,
    source_change_policy_path: Path,
    device_state_path: Path,
    provisioning_policy_path: Path,
    sequence: int,
) -> dict[str, bytes]:
    source_change_dir = source_change_dir.resolve()
    try:
        derivation = verify_source_derivation(
            source_change_dir,
            bundle_dir=bundle_dir,
            change_package_dir=change_package_dir,
            approval_path=approval_path,
            source_root=source_root,
            campaign_manifest=campaign_manifest,
            repo_root=repo_root,
            policy_path=source_change_policy_path,
        )
    except CalibrationSourceDerivationError as exc:
        raise CalibrationProvisioningError(f"source derivation verification failed: {exc}") from exc

    profile_path = source_change_dir / "approved-profile.json"
    source_change_path = source_change_dir / "source-change.json"
    profile = _load_json(profile_path, "approved calibration profile")
    source_change = _load_json(source_change_path, "source-change summary")
    if source_change.get("schema") != SOURCE_CHANGE_SCHEMA:
        raise CalibrationProvisioningError("unsupported source-change summary schema")

    policy = _load_json(provisioning_policy_path, "calibration provisioning policy")
    _validate_policy(policy)
    device_state = _load_json(device_state_path, "calibration device state")
    installed_sequence = _validate_device_state(device_state, policy)

    try:
        candidate_sequence = int(sequence)
    except (TypeError, ValueError) as exc:
        raise CalibrationProvisioningError("candidate sequence must be an integer") from exc
    minimum = int(policy["sequence"]["minimum"])
    maximum = int(policy["sequence"]["maximum"])
    if candidate_sequence < minimum or candidate_sequence > maximum:
        raise CalibrationProvisioningError("candidate sequence is outside provisioning policy range")
    if candidate_sequence <= installed_sequence:
        raise CalibrationProvisioningError(
            f"candidate sequence {candidate_sequence} is not newer than installed sequence {installed_sequence}"
        )

    authority = profile.get("authority")
    if not isinstance(authority, dict) or authority.get("runtime_write_permitted") is not False or authority.get("may_relax_hard_safety_limits") is not False:
        raise CalibrationProvisioningError("approved profile authority boundary is invalid")
    if profile.get("approval_id") != source_change.get("approval_id"):
        raise CalibrationProvisioningError("profile approval_id differs from source-change summary")
    for field in ("campaign_id", "repository_commit", "evidence_root_sha256", "change_package_sha256"):
        if profile.get(field) != source_change.get(field):
            raise CalibrationProvisioningError(f"profile/source-change provenance mismatch for {field}")

    record_blob = encode_calibration_record(profile, candidate_sequence)
    record_crc32 = struct.unpack_from("<I", record_blob, 44)[0]
    record_sha256 = _sha256_bytes(record_blob)
    package = {
        "schema": PROVISIONING_SCHEMA,
        "policy_id": policy["policy_id"],
        "device_id": device_state["device_id"],
        "device_state_sha256": _file_sha256(device_state_path),
        "campaign_id": profile["campaign_id"],
        "repository_commit": profile["repository_commit"],
        "approval_id": profile["approval_id"],
        "evidence_root_sha256": profile["evidence_root_sha256"],
        "change_package_sha256": profile["change_package_sha256"],
        "source_change_sha256": _file_sha256(source_change_path),
        "approved_profile_sha256": _file_sha256(profile_path),
        "source_derivation_verification": {
            "schema": derivation.get("schema"),
            "reviewer_package_rederived": derivation.get("reviewer_package_rederived") is True,
            "approval_semantics_revalidated": derivation.get("approval_semantics_revalidated") is True,
            "current_coefficients_rederived": derivation.get("current_coefficients_rederived") is True,
            "temperature_coefficients_rederived": derivation.get("temperature_coefficients_rederived") is True,
            "hard_safety_non_regression_pass": derivation.get("hard_safety_non_regression_pass") is True,
        },
        "sequence": {
            "installed": installed_sequence,
            "candidate": candidate_sequence,
            "strictly_newer": True,
            "wraparound_supported": False,
        },
        "record": {
            "format": "CalibrationRecord-v1",
            "blob_size_bytes": len(record_blob),
            "crc32_ieee": record_crc32,
            "sha256": record_sha256,
            "temperature": profile["calibration_record_v1_candidate"]["temperature"],
            "current": profile["calibration_record_v1_candidate"]["current"],
        },
        "storage": policy["storage"],
        "preconditions": {
            "maintenance_mode_confirmed_at_package_time": True,
            "load_output_physically_inhibited_confirmed_at_package_time": True,
            "write_time_recheck_required": True,
            "note": "Package-time declarations are not proof that the device remains safe to write later.",
        },
        "authority": {
            "package_generation_only": True,
            "remote_provisioning_command_present": False,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
    }
    package_bytes = _json_bytes(package)
    hex_bytes = (record_blob.hex() + "\n").encode("ascii")
    artifacts = {
        "provisioning.json": package_bytes,
        "calibration-record.bin": record_blob,
        "calibration-record.hex": hex_bytes,
    }
    index_core = {
        "schema": ARTIFACT_INDEX_SCHEMA,
        "campaign_id": profile["campaign_id"],
        "device_id": device_state["device_id"],
        "sequence": candidate_sequence,
        "artifacts": [
            {"path": path, "sha256": _sha256_bytes(content)}
            for path, content in sorted(artifacts.items())
        ],
        "authority": {
            "integrity_index_only": True,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    index = dict(index_core)
    index["root_sha256"] = _canonical_sha256(index_core)
    artifacts["artifact-index.json"] = _json_bytes(index)
    return artifacts


def publish_provisioning_bundle(source_change_dir: Path, *, out_dir: Path, **kwargs: object) -> None:
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise CalibrationProvisioningError(f"output directory already exists: {out_dir}")
    artifacts = build_provisioning_bundle(source_change_dir, **kwargs)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.staging-", dir=out_dir.parent))
    try:
        for relative, content in artifacts.items():
            (staging / relative).write_bytes(content)
        staging.rename(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a verified ForgeSense calibration provisioning image without writing a device")
    parser.add_argument("source_change_dir", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--change-package-dir", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--source-change-policy", type=Path, default=Path("hardware/calibration/calibration_source_change_policy_v1.json"))
    parser.add_argument("--device-state", type=Path, required=True)
    parser.add_argument("--provisioning-policy", type=Path, default=Path("hardware/calibration/calibration_provisioning_policy_v1.json"))
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        publish_provisioning_bundle(
            args.source_change_dir,
            out_dir=args.out_dir,
            bundle_dir=args.bundle,
            change_package_dir=args.change_package_dir,
            approval_path=args.approval,
            source_root=args.source_root,
            campaign_manifest=args.campaign_manifest,
            repo_root=args.repo_root,
            source_change_policy_path=args.source_change_policy,
            device_state_path=args.device_state,
            provisioning_policy_path=args.provisioning_policy,
            sequence=args.sequence,
        )
    except CalibrationProvisioningError as exc:
        raise SystemExit(f"calibration provisioning package preparation failed: {exc}") from exc
    print(f"calibration provisioning package written: {args.out_dir}; device_write_performed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
