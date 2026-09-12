from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
from typing import Any

from .audit_ledger import LedgerState, verify_ledger
from .provisioning import MaintenanceProvisioningError
from .signed_provisioning import public_key_der, verify_signature_openssl

TRANSITION_DOMAIN = b"ForgeSense-Maintenance-Authority-Transition-v1\n"
TRANSITION_REQUEST_SCHEMA = "forgesense.maintenance_authority_transition_request.v1"
TRANSITION_SCHEMA = "forgesense.maintenance_authority_transition.v1"
TRANSITION_POLICY_SCHEMA = "forgesense.maintenance_authority_transition_policy.v1"
SOURCE_MANIFEST_SCHEMA = "forgesense.maintenance_authority_source_manifest.v1"
SIGNATURE_FORMAT = "ECDSA-P256-SHA256-DER"

_SOURCE_FILES = (
    "firmware/esp32_calibration_maintenance/CMakeLists.txt",
    "firmware/esp32_calibration_maintenance/sdkconfig.defaults",
    "firmware/esp32_calibration_maintenance/main/CMakeLists.txt",
    "firmware/esp32_calibration_maintenance/main/Kconfig.projbuild",
    "firmware/esp32_calibration_maintenance/main/app_main.cpp",
    "firmware/esp32_calibration_maintenance/main/calibration_store_nvs.cpp",
    "firmware/esp32_calibration_maintenance/main/calibration_store_nvs.hpp",
    "firmware/esp32_calibration_maintenance/main/maintenance_authorization.cpp",
    "firmware/esp32_calibration_maintenance/main/maintenance_authorization.hpp",
    "firmware/esp32_calibration_maintenance/main/maintenance_protocol.cpp",
    "firmware/esp32_calibration_maintenance/main/maintenance_protocol.hpp",
)


class MaintenanceAuthorityTransitionError(MaintenanceProvisioningError):
    pass


@dataclass(frozen=True)
class VerifiedAuthorityTransition:
    package: dict[str, Any]
    request: dict[str, Any]
    payload_sha256: str
    old_public_key_sha256: str
    new_public_key_sha256: str


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
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
        raise MaintenanceAuthorityTransitionError(f"required transition input not found: {path}") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MaintenanceAuthorityTransitionError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MaintenanceAuthorityTransitionError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MaintenanceAuthorityTransitionError(f"{label} must contain a JSON object")
    return value


def _require_sha256(value: object, label: str, *, allow_none: bool = False) -> str | None:
    if allow_none and value is None:
        return None
    text = str(value or "").lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise MaintenanceAuthorityTransitionError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != TRANSITION_POLICY_SCHEMA:
        raise MaintenanceAuthorityTransitionError("unsupported maintenance-authority transition policy schema")
    signatures = policy.get("signatures")
    binding = policy.get("binding")
    installation = policy.get("installation")
    audit = policy.get("audit")
    authority = policy.get("authority")
    if not all(isinstance(section, dict) for section in (signatures, binding, installation, audit, authority)):
        raise MaintenanceAuthorityTransitionError("maintenance-authority transition policy sections are incomplete")
    expected_signatures = {
        "algorithm": SIGNATURE_FORMAT,
        "old_authority_signature_required": True,
        "new_authority_proof_of_possession_required": True,
        "same_payload_required": True,
        "private_key_loaded_by_forgesense_tooling": False,
    }
    for key, expected in expected_signatures.items():
        if signatures.get(key) != expected:
            raise MaintenanceAuthorityTransitionError(f"transition signature policy field {key} is invalid")
    for key in (
        "device_id_required",
        "audit_ledger_head_required",
        "calibration_sequence_unchanged_required",
        "active_record_sha256_unchanged_required",
        "old_public_key_fingerprint_required",
        "new_public_key_fingerprint_required",
        "source_commit_required",
        "maintenance_source_manifest_root_required",
        "sdkconfig_sha256_required",
        "maintenance_image_sha256_required",
        "sdkconfig_must_pin_new_public_key",
    ):
        if binding.get(key) is not True:
            raise MaintenanceAuthorityTransitionError(f"transition binding policy field {key} must be true")
    expected_install = {
        "runtime_key_update_supported": False,
        "remote_key_update_supported": False,
        "calibration_protocol_key_update_supported": False,
        "firmware_install_performed_by_forgesense_transition_tool": False,
        "post_install_read_only_state_capture_required": True,
        "post_install_new_fingerprint_match_required": True,
        "post_install_calibration_state_must_be_unchanged": True,
    }
    for key, expected in expected_install.items():
        if installation.get(key) != expected:
            raise MaintenanceAuthorityTransitionError(f"transition installation policy field {key} is invalid")
    expected_audit = {
        "authority_transition_event_required": True,
        "sequence_change_permitted": False,
        "record_change_permitted": False,
        "silent_authority_adoption_permitted": False,
    }
    for key, expected in expected_audit.items():
        if audit.get(key) != expected:
            raise MaintenanceAuthorityTransitionError(f"transition audit policy field {key} is invalid")
    expected_authority = {
        "transition_evidence_only": True,
        "automatic_key_rotation": False,
        "may_write_firmware": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
        "hardware_backed_key_revocation_claimed": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) != expected:
            raise MaintenanceAuthorityTransitionError(f"transition authority field {key} is invalid")


def load_transition_policy(path: Path) -> dict[str, Any]:
    policy = _load_json(path, "maintenance-authority transition policy")
    _validate_policy(policy)
    return policy


def _full_commit(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise MaintenanceAuthorityTransitionError("source commit must be a full 40-hex Git commit")
    return value


def _git_output(repo_root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )
    except FileNotFoundError as exc:
        raise MaintenanceAuthorityTransitionError("Git is required to bind maintenance sources to a reviewed commit") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or str(result.returncode)
        raise MaintenanceAuthorityTransitionError(f"Git source verification failed: {detail}")
    return result.stdout


def _verify_source_checkout(repo_root: Path, source_commit: str) -> str:
    repo_root = repo_root.resolve()
    expected = _full_commit(source_commit)
    head = _git_output(repo_root, ["rev-parse", "HEAD"]).strip().lower()
    if head != expected:
        raise MaintenanceAuthorityTransitionError(
            f"maintenance source checkout HEAD {head} differs from reviewed source commit {expected}"
        )
    for relative in _SOURCE_FILES:
        _git_output(repo_root, ["ls-files", "--error-unmatch", "--", relative])
    status = _git_output(
        repo_root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *_SOURCE_FILES],
    )
    if status.strip():
        raise MaintenanceAuthorityTransitionError("maintenance source files are dirty relative to the reviewed source commit")
    return expected


def _device_mac(device_id: str) -> bytes:
    if not re.fullmatch(r"esp32s3:[0-9a-f]{12}", device_id):
        raise MaintenanceAuthorityTransitionError("device_id must use esp32s3:<12 lowercase hex> format")
    return bytes.fromhex(device_id.split(":", 1)[1])


def _source_manifest(repo_root: Path, source_commit: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    files: list[dict[str, str]] = []
    for relative in _SOURCE_FILES:
        path = (repo_root / relative).resolve()
        try:
            path.relative_to(repo_root)
        except ValueError as exc:
            raise MaintenanceAuthorityTransitionError("maintenance source path escapes repository root") from exc
        if path.is_symlink() or not path.is_file():
            raise MaintenanceAuthorityTransitionError(f"maintenance source is not a regular file: {relative}")
        files.append({"path": relative, "sha256": _file_sha256(path)})
    root_material = {"source_commit": source_commit, "files": files}
    return {
        "schema": SOURCE_MANIFEST_SCHEMA,
        "source_commit": source_commit,
        "files": files,
        "root_sha256": _canonical_sha256(root_material),
    }


def transition_payload(
    *,
    device_id: str,
    calibration_sequence: int,
    active_record_sha256: str | None,
    ledger_head_sha256: str,
    old_public_key_sha256: str,
    new_public_key_sha256: str,
    source_commit: str,
    source_manifest_root_sha256: str,
    sdkconfig_sha256: str,
    maintenance_image_sha256: str,
) -> bytes:
    if calibration_sequence < 0 or calibration_sequence > 0xFFFFFFFE:
        raise MaintenanceAuthorityTransitionError("calibration sequence is outside supported range")
    record_sha = _require_sha256(active_record_sha256, "active record SHA-256", allow_none=True)
    ledger_sha = _require_sha256(ledger_head_sha256, "audit ledger head SHA-256")
    old_sha = _require_sha256(old_public_key_sha256, "old public-key SHA-256")
    new_sha = _require_sha256(new_public_key_sha256, "new public-key SHA-256")
    source_root = _require_sha256(source_manifest_root_sha256, "source manifest root SHA-256")
    sdkconfig_sha = _require_sha256(sdkconfig_sha256, "sdkconfig SHA-256")
    image_sha = _require_sha256(maintenance_image_sha256, "maintenance image SHA-256")
    commit = bytes.fromhex(_full_commit(source_commit))
    present = 0 if record_sha is None else 1
    record_bytes = bytes(32) if record_sha is None else bytes.fromhex(record_sha)
    return b"".join(
        (
            TRANSITION_DOMAIN,
            _device_mac(device_id),
            struct.pack("<I", calibration_sequence),
            bytes((present,)),
            record_bytes,
            bytes.fromhex(str(ledger_sha)),
            bytes.fromhex(str(old_sha)),
            bytes.fromhex(str(new_sha)),
            commit,
            bytes.fromhex(str(source_root)),
            bytes.fromhex(str(sdkconfig_sha)),
            bytes.fromhex(str(image_sha)),
        )
    )


def _device_state_matches_ledger(device: dict[str, Any], ledger: LedgerState) -> None:
    if str(device.get("device_id", "")) != ledger.device_id:
        raise MaintenanceAuthorityTransitionError("device state belongs to a different audit ledger device")
    if int(device.get("installed_sequence", -1)) != ledger.sequence:
        raise MaintenanceAuthorityTransitionError("device calibration sequence differs from audit ledger head")
    record_sha = _require_sha256(device.get("active_record_sha256"), "device active record SHA-256", allow_none=True)
    if record_sha != ledger.record_sha256:
        raise MaintenanceAuthorityTransitionError("device active record SHA-256 differs from audit ledger head")
    if device.get("maintenance_authorization_ready") is not True:
        raise MaintenanceAuthorityTransitionError("device maintenance authority is not ready")
    authority_sha = _require_sha256(
        device.get("maintenance_authority_public_key_sha256"),
        "device maintenance authority public-key SHA-256",
    )
    if authority_sha != ledger.authority_public_key_sha256:
        raise MaintenanceAuthorityTransitionError("device maintenance authority fingerprint differs from audit ledger head")


def build_transition_request(
    *,
    ledger_dir: Path,
    audit_policy_path: Path,
    device_state_path: Path,
    old_public_key_path: Path,
    new_public_key_path: Path,
    source_commit: str,
    repo_root: Path,
    sdkconfig_path: Path,
    maintenance_image_path: Path,
    transition_policy_path: Path,
) -> dict[str, bytes]:
    policy = load_transition_policy(transition_policy_path)
    ledger = verify_ledger(ledger_dir, policy_path=audit_policy_path)
    device = _load_json(device_state_path, "pre-transition device state")
    _device_state_matches_ledger(device, ledger)

    old_der = public_key_der(old_public_key_path)
    new_der = public_key_der(new_public_key_path)
    old_fp = _sha256_bytes(old_der)
    new_fp = _sha256_bytes(new_der)
    if old_fp != ledger.authority_public_key_sha256:
        raise MaintenanceAuthorityTransitionError("old public key does not match current audit-ledger authority")
    if new_fp == old_fp:
        raise MaintenanceAuthorityTransitionError("new maintenance authority public key must differ from old key")

    try:
        sdkconfig_text = sdkconfig_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MaintenanceAuthorityTransitionError(f"sdkconfig not found: {sdkconfig_path}") from exc
    pin_pattern = re.compile(
        r'^CONFIG_FORGESENSE_MAINTENANCE_AUTHORITY_PUBKEY_DER_HEX="([0-9A-Fa-f]+)"$',
        re.MULTILINE,
    )
    match = pin_pattern.search(sdkconfig_text)
    if match is None:
        raise MaintenanceAuthorityTransitionError("sdkconfig does not contain the maintenance authority DER pin")
    if match.group(1).lower() != new_der.hex():
        raise MaintenanceAuthorityTransitionError("sdkconfig maintenance authority pin does not equal the new public key")

    source_commit_value = _verify_source_checkout(repo_root, source_commit)
    manifest = _source_manifest(repo_root, source_commit_value)
    sdkconfig_sha = _file_sha256(sdkconfig_path)
    image_sha = _file_sha256(maintenance_image_path)
    payload = transition_payload(
        device_id=ledger.device_id,
        calibration_sequence=ledger.sequence,
        active_record_sha256=ledger.record_sha256,
        ledger_head_sha256=ledger.head_sha256,
        old_public_key_sha256=old_fp,
        new_public_key_sha256=new_fp,
        source_commit=source_commit_value,
        source_manifest_root_sha256=manifest["root_sha256"],
        sdkconfig_sha256=sdkconfig_sha,
        maintenance_image_sha256=image_sha,
    )
    request = {
        "schema": TRANSITION_REQUEST_SCHEMA,
        "policy_id": policy["policy_id"],
        "signature_format": SIGNATURE_FORMAT,
        "device_id": ledger.device_id,
        "calibration_sequence": ledger.sequence,
        "active_record_sha256": ledger.record_sha256,
        "audit_ledger_head_sha256": ledger.head_sha256,
        "audit_ledger_entry_count": ledger.entry_count,
        "old_authority_public_key_sha256": old_fp,
        "new_authority_public_key_sha256": new_fp,
        "source_commit": source_commit_value,
        "source_checkout_verified_clean": True,
        "source_manifest_root_sha256": manifest["root_sha256"],
        "sdkconfig_sha256": sdkconfig_sha,
        "maintenance_image_sha256": image_sha,
        "payload_sha256": _sha256_bytes(payload),
        "payload_size": len(payload),
        "authority": {
            "old_authority_signature_required": True,
            "new_authority_proof_of_possession_required": True,
            "private_key_accessed_by_tool": False,
            "automatic_key_rotation": False,
            "may_write_firmware": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    return {
        "transition-request.json": _json_bytes(request),
        "transition-payload.bin": payload,
        "source-manifest.json": _json_bytes(manifest),
    }


def _copy_public_key_to_package(source: Path, target: Path) -> None:
    data = source.read_bytes()
    if b"PRIVATE KEY" in data:
        raise MaintenanceAuthorityTransitionError("transition package accepts public keys only")
    target.write_bytes(data)


def package_transition(
    request_dir: Path,
    *,
    old_signature_path: Path,
    new_signature_path: Path,
    old_public_key_path: Path,
    new_public_key_path: Path,
    output_dir: Path,
) -> None:
    request_dir = request_dir.resolve()
    request = _load_json(request_dir / "transition-request.json", "transition request")
    if request.get("schema") != TRANSITION_REQUEST_SCHEMA:
        raise MaintenanceAuthorityTransitionError("unsupported transition request schema")
    payload = (request_dir / "transition-payload.bin").read_bytes()
    manifest = (request_dir / "source-manifest.json").read_bytes()
    if request.get("payload_sha256") != _sha256_bytes(payload):
        raise MaintenanceAuthorityTransitionError("transition request payload SHA-256 mismatch")
    old_signature = old_signature_path.read_bytes()
    new_signature = new_signature_path.read_bytes()
    old_fp = verify_signature_openssl(
        public_key_path=old_public_key_path,
        payload=payload,
        signature_der=old_signature,
    )
    new_fp = verify_signature_openssl(
        public_key_path=new_public_key_path,
        payload=payload,
        signature_der=new_signature,
    )
    if old_fp != request.get("old_authority_public_key_sha256"):
        raise MaintenanceAuthorityTransitionError("old transition signer fingerprint differs from request")
    if new_fp != request.get("new_authority_public_key_sha256"):
        raise MaintenanceAuthorityTransitionError("new transition signer fingerprint differs from request")

    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise MaintenanceAuthorityTransitionError(f"transition package output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        shutil.copy2(request_dir / "transition-request.json", staging / "transition-request.json")
        (staging / "transition-payload.bin").write_bytes(payload)
        (staging / "source-manifest.json").write_bytes(manifest)
        (staging / "old-authority-signature.der").write_bytes(old_signature)
        (staging / "new-authority-signature.der").write_bytes(new_signature)
        _copy_public_key_to_package(old_public_key_path, staging / "old-authority-public.pem")
        _copy_public_key_to_package(new_public_key_path, staging / "new-authority-public.pem")
        package = {
            "schema": TRANSITION_SCHEMA,
            "request_sha256": _file_sha256(staging / "transition-request.json"),
            "payload_sha256": _sha256_bytes(payload),
            "source_manifest_sha256": _file_sha256(staging / "source-manifest.json"),
            "old_signature_sha256": _sha256_bytes(old_signature),
            "new_signature_sha256": _sha256_bytes(new_signature),
            "old_authority_public_key_sha256": old_fp,
            "new_authority_public_key_sha256": new_fp,
            "device_id": request["device_id"],
            "calibration_sequence": request["calibration_sequence"],
            "active_record_sha256": request["active_record_sha256"],
            "audit_ledger_head_sha256": request["audit_ledger_head_sha256"],
            "maintenance_image_sha256": request["maintenance_image_sha256"],
            "source_commit": request["source_commit"],
            "signature_format": SIGNATURE_FORMAT,
            "authority": {
                "old_signature_verified": True,
                "new_proof_of_possession_verified": True,
                "private_key_accessed_by_tool": False,
                "automatic_key_rotation": False,
                "may_write_firmware": False,
                "may_control_actuators": False,
                "may_relax_hard_safety_limits": False,
            },
        }
        (staging / "transition.json").write_bytes(_json_bytes(package))
        staging.rename(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_transition_package(package_dir: Path) -> VerifiedAuthorityTransition:
    package_dir = package_dir.resolve()
    package = _load_json(package_dir / "transition.json", "maintenance-authority transition package")
    request = _load_json(package_dir / "transition-request.json", "maintenance-authority transition request")
    if package.get("schema") != TRANSITION_SCHEMA or request.get("schema") != TRANSITION_REQUEST_SCHEMA:
        raise MaintenanceAuthorityTransitionError("unsupported maintenance-authority transition package schema")
    if request.get("source_checkout_verified_clean") is not True:
        raise MaintenanceAuthorityTransitionError("transition request lacks verified clean source-checkout binding")
    payload = (package_dir / "transition-payload.bin").read_bytes()
    old_signature = (package_dir / "old-authority-signature.der").read_bytes()
    new_signature = (package_dir / "new-authority-signature.der").read_bytes()
    old_public = package_dir / "old-authority-public.pem"
    new_public = package_dir / "new-authority-public.pem"
    manifest = _load_json(package_dir / "source-manifest.json", "maintenance source manifest")
    if manifest.get("schema") != SOURCE_MANIFEST_SCHEMA:
        raise MaintenanceAuthorityTransitionError("unsupported maintenance source manifest schema")
    if manifest.get("source_commit") != request.get("source_commit"):
        raise MaintenanceAuthorityTransitionError("transition source-manifest commit differs from signed request")
    if request.get("source_manifest_root_sha256") != manifest.get("root_sha256"):
        raise MaintenanceAuthorityTransitionError("transition request source-manifest root mismatch")
    manifest_material = {
        "source_commit": manifest.get("source_commit"),
        "files": manifest.get("files"),
    }
    if _canonical_sha256(manifest_material) != manifest.get("root_sha256"):
        raise MaintenanceAuthorityTransitionError("transition source-manifest root is invalid")
    expected_payload = transition_payload(
        device_id=str(request.get("device_id", "")),
        calibration_sequence=int(request.get("calibration_sequence", -1)),
        active_record_sha256=request.get("active_record_sha256"),
        ledger_head_sha256=str(request.get("audit_ledger_head_sha256", "")),
        old_public_key_sha256=str(request.get("old_authority_public_key_sha256", "")),
        new_public_key_sha256=str(request.get("new_authority_public_key_sha256", "")),
        source_commit=str(request.get("source_commit", "")),
        source_manifest_root_sha256=str(request.get("source_manifest_root_sha256", "")),
        sdkconfig_sha256=str(request.get("sdkconfig_sha256", "")),
        maintenance_image_sha256=str(request.get("maintenance_image_sha256", "")),
    )
    if payload != expected_payload or request.get("payload_sha256") != _sha256_bytes(payload):
        raise MaintenanceAuthorityTransitionError("transition payload does not match request bindings")
    old_fp = verify_signature_openssl(public_key_path=old_public, payload=payload, signature_der=old_signature)
    new_fp = verify_signature_openssl(public_key_path=new_public, payload=payload, signature_der=new_signature)
    if old_fp != request.get("old_authority_public_key_sha256") or new_fp != request.get("new_authority_public_key_sha256"):
        raise MaintenanceAuthorityTransitionError("transition signer fingerprint mismatch")
    expected_package = {
        "request_sha256": _file_sha256(package_dir / "transition-request.json"),
        "payload_sha256": _sha256_bytes(payload),
        "source_manifest_sha256": _file_sha256(package_dir / "source-manifest.json"),
        "old_signature_sha256": _sha256_bytes(old_signature),
        "new_signature_sha256": _sha256_bytes(new_signature),
        "old_authority_public_key_sha256": old_fp,
        "new_authority_public_key_sha256": new_fp,
        "device_id": request.get("device_id"),
        "calibration_sequence": request.get("calibration_sequence"),
        "active_record_sha256": request.get("active_record_sha256"),
        "audit_ledger_head_sha256": request.get("audit_ledger_head_sha256"),
        "maintenance_image_sha256": request.get("maintenance_image_sha256"),
        "source_commit": request.get("source_commit"),
        "signature_format": SIGNATURE_FORMAT,
    }
    for key, expected in expected_package.items():
        if package.get(key) != expected:
            raise MaintenanceAuthorityTransitionError(f"transition package metadata mismatch for {key}")
    authority = package.get("authority")
    if not isinstance(authority, dict):
        raise MaintenanceAuthorityTransitionError("transition package authority section is missing")
    expected_authority = {
        "old_signature_verified": True,
        "new_proof_of_possession_verified": True,
        "private_key_accessed_by_tool": False,
        "automatic_key_rotation": False,
        "may_write_firmware": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) != expected:
            raise MaintenanceAuthorityTransitionError(f"transition package authority field {key} is invalid")
    return VerifiedAuthorityTransition(
        package=package,
        request=request,
        payload_sha256=_sha256_bytes(payload),
        old_public_key_sha256=old_fp,
        new_public_key_sha256=new_fp,
    )
