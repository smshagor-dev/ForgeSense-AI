from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from .provisioning import MaintenanceProvisioningError, PHYSICAL_EVIDENCE_SCHEMA

LEDGER_SCHEMA = "forgesense.calibration_audit_ledger.v1"
ENTRY_SCHEMA = "forgesense.calibration_audit_entry.v1"
POLICY_SCHEMA = "forgesense.calibration_audit_ledger_policy.v1"
GENESIS_PREVIOUS_SHA256 = "0" * 64
_ENTRY_NAME = re.compile(r"^(\d{8})\.json$")


class CalibrationAuditLedgerError(MaintenanceProvisioningError):
    pass


@dataclass(frozen=True)
class LedgerState:
    device_id: str
    entry_count: int
    head_sha256: str
    sequence: int
    record_sha256: str | None
    authority_public_key_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "entry_count": self.entry_count,
            "head_sha256": self.head_sha256,
            "sequence": self.sequence,
            "record_sha256": self.record_sha256,
            "authority_public_key_sha256": self.authority_public_key_sha256,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _canonical_sha256(data: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise CalibrationAuditLedgerError(f"required audit evidence not found: {path}") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CalibrationAuditLedgerError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CalibrationAuditLedgerError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CalibrationAuditLedgerError(f"{label} must contain a JSON object")
    return value


def _require_sha256(value: object, label: str, *, allow_none: bool = False) -> str | None:
    if allow_none and value is None:
        return None
    text = str(value or "").lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise CalibrationAuditLedgerError(f"{label} must be a lowercase SHA-256 hex digest")
    return text


def _validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema") != POLICY_SCHEMA:
        raise CalibrationAuditLedgerError("unsupported calibration audit-ledger policy schema")
    init = policy.get("initialization")
    chain = policy.get("chain")
    preflight = policy.get("write_preflight")
    events = policy.get("events")
    authority = policy.get("authority")
    if not all(isinstance(section, dict) for section in (init, chain, preflight, events, authority)):
        raise CalibrationAuditLedgerError("calibration audit-ledger policy sections are incomplete")

    expected_init = {
        "fresh_device_sequence_required": 0,
        "active_record_must_be_absent": True,
        "maintenance_authority_ready_required": True,
        "adopt_nonzero_history_supported": False,
    }
    for key, expected in expected_init.items():
        if init.get(key) != expected:
            raise CalibrationAuditLedgerError(f"audit ledger initialization policy field {key} is invalid")

    expected_chain = {
        "hash": "SHA-256",
        "canonical_json": True,
        "contiguous_entry_index_required": True,
        "previous_entry_hash_required": True,
        "head_derived_from_last_entry": True,
        "metadata_bound_by_genesis": True,
        "silent_entry_rewrite_permitted": False,
    }
    for key, expected in expected_chain.items():
        if chain.get(key) != expected:
            raise CalibrationAuditLedgerError(f"audit ledger chain policy field {key} is invalid")

    expected_preflight = {
        "ledger_required": True,
        "live_device_id_match_required": True,
        "live_sequence_match_required": True,
        "live_active_record_sha256_match_required_when_active": True,
        "live_authority_public_key_sha256_match_required": True,
        "unexpected_authority_rotation_permitted": False,
    }
    for key, expected in expected_preflight.items():
        if preflight.get(key) != expected:
            raise CalibrationAuditLedgerError(f"audit ledger preflight policy field {key} is invalid")

    expected_events = {
        "write_commit": True,
        "recovery_commit": True,
        "reboot_verified": True,
        "automatic_event_insertion": False,
        "sequence_decrement_permitted": False,
        "recovery_increment_exactly_one": True,
    }
    for key, expected in expected_events.items():
        if events.get(key) != expected:
            raise CalibrationAuditLedgerError(f"audit ledger event policy field {key} is invalid")

    expected_authority = {
        "audit_only": True,
        "is_digital_signature": False,
        "is_immutable_storage": False,
        "automatic_provisioning": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
        "hardware_backed_monotonic_counter_claimed": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) != expected:
            raise CalibrationAuditLedgerError(f"audit ledger authority field {key} is invalid")


def load_policy(policy_path: Path) -> dict[str, Any]:
    policy = _load_json(policy_path, "calibration audit-ledger policy")
    _validate_policy(policy)
    return policy


def _entry_hash(entry: dict[str, Any]) -> str:
    core = {key: value for key, value in entry.items() if key != "entry_sha256"}
    return _canonical_sha256(core)


def _entry_files(ledger_dir: Path) -> list[Path]:
    try:
        children = list(ledger_dir.iterdir())
    except FileNotFoundError as exc:
        raise CalibrationAuditLedgerError(f"audit ledger not found: {ledger_dir}") from exc
    result: list[tuple[int, Path]] = []
    for child in children:
        if child.name == "ledger.json":
            continue
        match = _ENTRY_NAME.fullmatch(child.name)
        if not match:
            raise CalibrationAuditLedgerError(f"unexpected file in audit ledger directory: {child.name}")
        if not child.is_file() or child.is_symlink():
            raise CalibrationAuditLedgerError(f"audit ledger entry is not a regular file: {child.name}")
        result.append((int(match.group(1)), child))
    result.sort(key=lambda item: item[0])
    return [path for _, path in result]


def _state_fields(entry: dict[str, Any], label: str) -> tuple[int, str | None, str]:
    section = entry.get(label)
    if not isinstance(section, dict):
        raise CalibrationAuditLedgerError(f"audit entry {label} section is missing")
    try:
        sequence = int(section.get("sequence"))
    except (TypeError, ValueError) as exc:
        raise CalibrationAuditLedgerError(f"audit entry {label}.sequence must be an integer") from exc
    if sequence < 0 or sequence > 0xFFFFFFFE:
        raise CalibrationAuditLedgerError(f"audit entry {label}.sequence is outside supported range")
    record_sha = _require_sha256(
        section.get("record_sha256"),
        f"audit entry {label}.record_sha256",
        allow_none=True,
    )
    authority_sha = _require_sha256(
        section.get("authority_public_key_sha256"),
        f"audit entry {label}.authority_public_key_sha256",
    )
    return sequence, record_sha, str(authority_sha)


def verify_ledger(
    ledger_dir: Path,
    *,
    policy_path: Path,
    expected_device_id: str | None = None,
) -> LedgerState:
    ledger_dir = ledger_dir.resolve()
    policy = load_policy(policy_path)
    metadata_path = ledger_dir / "ledger.json"
    if metadata_path.exists() and (metadata_path.is_symlink() or not metadata_path.is_file()):
        raise CalibrationAuditLedgerError("audit ledger metadata must be a regular non-symlink file")
    metadata = _load_json(metadata_path, "calibration audit ledger metadata")
    if metadata.get("schema") != LEDGER_SCHEMA:
        raise CalibrationAuditLedgerError("unsupported calibration audit ledger schema")
    if metadata.get("policy_id") != policy.get("policy_id"):
        raise CalibrationAuditLedgerError("audit ledger policy_id differs from active policy")
    device_id = str(metadata.get("device_id", "")).strip()
    if not device_id:
        raise CalibrationAuditLedgerError("audit ledger device_id is missing")
    if expected_device_id is not None and device_id != expected_device_id:
        raise CalibrationAuditLedgerError("audit ledger belongs to a different device")
    authority_meta = metadata.get("authority")
    if not isinstance(authority_meta, dict) or authority_meta != policy["authority"]:
        raise CalibrationAuditLedgerError("audit ledger metadata authority boundary differs from policy")

    files = _entry_files(ledger_dir)
    if not files:
        raise CalibrationAuditLedgerError("audit ledger contains no genesis entry")

    previous_hash = GENESIS_PREVIOUS_SHA256
    sequence = 0
    record_sha: str | None = None
    authority_sha = ""
    for expected_index, path in enumerate(files):
        if path.name != f"{expected_index:08d}.json":
            raise CalibrationAuditLedgerError("audit ledger entry indexes are not contiguous")
        entry = _load_json(path, f"audit ledger entry {path.name}")
        if entry.get("schema") != ENTRY_SCHEMA:
            raise CalibrationAuditLedgerError(f"unsupported audit ledger entry schema in {path.name}")
        if int(entry.get("index", -1)) != expected_index:
            raise CalibrationAuditLedgerError(f"audit ledger entry index mismatch in {path.name}")
        if entry.get("device_id") != device_id:
            raise CalibrationAuditLedgerError(f"audit ledger device binding mismatch in {path.name}")
        if entry.get("previous_entry_sha256") != previous_hash:
            raise CalibrationAuditLedgerError(f"audit ledger previous-entry hash mismatch in {path.name}")
        claimed_hash = _require_sha256(entry.get("entry_sha256"), f"{path.name}.entry_sha256")
        if claimed_hash != _entry_hash(entry):
            raise CalibrationAuditLedgerError(f"audit ledger entry hash mismatch in {path.name}")

        before_sequence, before_record, before_authority = _state_fields(entry, "state_before")
        after_sequence, after_record, after_authority = _state_fields(entry, "state_after")
        event_type = str(entry.get("event_type", ""))
        event_authority = entry.get("authority")
        if not isinstance(event_authority, dict):
            raise CalibrationAuditLedgerError(f"audit ledger event authority is missing in {path.name}")
        for key in ("may_control_actuators", "may_relax_hard_safety_limits", "automatic_provisioning"):
            if event_authority.get(key) is not False:
                raise CalibrationAuditLedgerError(f"audit ledger event authority field {key} is invalid in {path.name}")

        if expected_index == 0:
            if event_type != "genesis":
                raise CalibrationAuditLedgerError("first audit ledger entry must be genesis")
            if before_sequence != 0 or after_sequence != 0 or before_record is not None or after_record is not None:
                raise CalibrationAuditLedgerError("audit ledger genesis must represent sequence zero with no active record")
            if before_authority != after_authority:
                raise CalibrationAuditLedgerError("audit ledger genesis authority fingerprint is inconsistent")
            metadata_sha = _require_sha256(entry.get("ledger_metadata_sha256"), "genesis.ledger_metadata_sha256")
            if metadata_sha != _file_sha256(metadata_path):
                raise CalibrationAuditLedgerError("audit ledger metadata hash differs from genesis binding")
            authority_sha = after_authority
        else:
            if before_sequence != sequence or before_record != record_sha or before_authority != authority_sha:
                raise CalibrationAuditLedgerError(f"audit ledger state continuity mismatch in {path.name}")
            if after_authority != before_authority:
                raise CalibrationAuditLedgerError("unexpected maintenance-authority rotation in audit ledger")
            if event_type == "write_commit":
                if after_sequence <= before_sequence or after_record is None:
                    raise CalibrationAuditLedgerError("write audit event does not contain a newer committed record")
            elif event_type == "recovery_commit":
                if after_sequence != before_sequence + 1 or after_record is None:
                    raise CalibrationAuditLedgerError("recovery audit event must commit a record at exactly the next sequence")
            elif event_type == "reboot_verified":
                if after_sequence != before_sequence or after_record != before_record:
                    raise CalibrationAuditLedgerError("reboot verification audit event may not mutate calibration state")
            else:
                raise CalibrationAuditLedgerError(f"unsupported audit event_type in {path.name}: {event_type}")
            sequence = after_sequence
            record_sha = after_record
            authority_sha = after_authority
        previous_hash = str(claimed_hash)

    return LedgerState(
        device_id=device_id,
        entry_count=len(files),
        head_sha256=previous_hash,
        sequence=sequence,
        record_sha256=record_sha,
        authority_public_key_sha256=authority_sha,
    )


def initialize_ledger(
    ledger_dir: Path,
    *,
    device_state_path: Path,
    policy_path: Path,
) -> LedgerState:
    policy = load_policy(policy_path)
    state = _load_json(device_state_path, "calibration device state")
    device_id = str(state.get("device_id", "")).strip()
    if not device_id:
        raise CalibrationAuditLedgerError("device state device_id is missing")
    if int(state.get("installed_sequence", -1)) != 0:
        raise CalibrationAuditLedgerError("audit ledger initialization requires installed calibration sequence zero")
    if (
        state.get("installed_record_crc32") is not None
        or state.get("active_record_sha256") is not None
        or state.get("active_record_hex") is not None
    ):
        raise CalibrationAuditLedgerError("audit ledger initialization requires no active calibration record")
    if state.get("maintenance_authorization_ready") is not True:
        raise CalibrationAuditLedgerError("audit ledger initialization requires a ready maintenance authority")
    authority_sha = _require_sha256(
        state.get("maintenance_authority_public_key_sha256"),
        "device_state.maintenance_authority_public_key_sha256",
    )

    ledger_dir = ledger_dir.resolve()
    if ledger_dir.exists():
        raise CalibrationAuditLedgerError(f"audit ledger already exists: {ledger_dir}")
    ledger_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{ledger_dir.name}.", dir=ledger_dir.parent))
    try:
        metadata = {
            "schema": LEDGER_SCHEMA,
            "policy_id": policy["policy_id"],
            "device_id": device_id,
            "created_at_utc": _utc_now(),
            "source_device_state_sha256": _file_sha256(device_state_path),
            "authority": policy["authority"],
            "evidence_boundary": (
                "This is an append-structured SHA-256 audit chain. It is not a digital signature, immutable storage, "
                "or hardware-backed monotonic evidence."
            ),
        }
        metadata_path = staging / "ledger.json"
        metadata_path.write_bytes(_json_bytes(metadata))
        genesis_core: dict[str, Any] = {
            "schema": ENTRY_SCHEMA,
            "index": 0,
            "event_type": "genesis",
            "timestamp_utc": _utc_now(),
            "device_id": device_id,
            "previous_entry_sha256": GENESIS_PREVIOUS_SHA256,
            "ledger_metadata_sha256": _file_sha256(metadata_path),
            "evidence": {"device_state_sha256": _file_sha256(device_state_path)},
            "state_before": {
                "sequence": 0,
                "record_sha256": None,
                "authority_public_key_sha256": authority_sha,
            },
            "state_after": {
                "sequence": 0,
                "record_sha256": None,
                "authority_public_key_sha256": authority_sha,
            },
            "authority": {
                "audit_only": True,
                "automatic_provisioning": False,
                "may_control_actuators": False,
                "may_relax_hard_safety_limits": False,
            },
        }
        genesis = dict(genesis_core)
        genesis["entry_sha256"] = _canonical_sha256(genesis_core)
        (staging / "00000000.json").write_bytes(_json_bytes(genesis))
        staging.rename(ledger_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return verify_ledger(ledger_dir, policy_path=policy_path, expected_device_id=device_id)


def preflight_live_state(
    ledger_dir: Path,
    *,
    policy_path: Path,
    device_id: str,
    installed_sequence: int,
    active_record_sha256: str | None,
    authority_public_key_sha256: str,
) -> LedgerState:
    state = verify_ledger(ledger_dir, policy_path=policy_path, expected_device_id=device_id)
    if installed_sequence != state.sequence:
        raise CalibrationAuditLedgerError(
            f"live calibration sequence {installed_sequence} differs from audit ledger sequence {state.sequence}"
        )
    live_record = _require_sha256(active_record_sha256, "live active record SHA-256", allow_none=True)
    if live_record != state.record_sha256:
        raise CalibrationAuditLedgerError("live active CalibrationRecord SHA-256 differs from audit ledger head")
    live_authority = _require_sha256(
        authority_public_key_sha256,
        "live maintenance authority public-key SHA-256",
    )
    if live_authority != state.authority_public_key_sha256:
        raise CalibrationAuditLedgerError("live maintenance authority fingerprint differs from audit ledger head")
    return state


def _require_preflight_binding(report: dict[str, Any], state: LedgerState) -> None:
    host = report.get("host_verification")
    if not isinstance(host, dict):
        raise CalibrationAuditLedgerError("physical evidence lacks audit-ledger host preflight binding")
    if host.get("audit_ledger_required") is not True or host.get("audit_ledger_preflight_verified") is not True:
        raise CalibrationAuditLedgerError("physical evidence was not produced under mandatory audit-ledger preflight")
    if host.get("audit_ledger_head_before_operation") != state.head_sha256:
        raise CalibrationAuditLedgerError("physical evidence audit-ledger head does not match current ledger head")
    if int(host.get("audit_ledger_entry_count_before_operation", -1)) != state.entry_count:
        raise CalibrationAuditLedgerError("physical evidence audit-ledger entry count does not match current ledger")


def _append_entry(ledger_dir: Path, entry_core: dict[str, Any], *, policy_path: Path) -> LedgerState:
    ledger_dir = ledger_dir.resolve()
    state = verify_ledger(ledger_dir, policy_path=policy_path, expected_device_id=str(entry_core["device_id"]))
    index = state.entry_count
    if int(entry_core.get("index", -1)) != index:
        raise CalibrationAuditLedgerError("audit entry index does not match ledger head")
    if entry_core.get("previous_entry_sha256") != state.head_sha256:
        raise CalibrationAuditLedgerError("audit entry previous hash does not match ledger head")
    entry = dict(entry_core)
    entry["entry_sha256"] = _canonical_sha256(entry_core)
    target = ledger_dir / f"{index:08d}.json"
    if target.exists():
        raise CalibrationAuditLedgerError(f"audit ledger entry already exists: {target.name}")
    try:
        with target.open("xb") as handle:
            handle.write(_json_bytes(entry))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CalibrationAuditLedgerError(f"audit ledger entry already exists: {target.name}") from exc
    return verify_ledger(ledger_dir, policy_path=policy_path, expected_device_id=state.device_id)


def append_write_evidence(
    ledger_dir: Path,
    *,
    evidence_path: Path,
    policy_path: Path,
) -> LedgerState:
    report = _load_json(evidence_path, "physical calibration provisioning evidence")
    if report.get("schema") != PHYSICAL_EVIDENCE_SCHEMA or report.get("commit_verified") is not True:
        raise CalibrationAuditLedgerError("physical provisioning evidence is not a committed calibration write")
    device = report.get("device")
    provisioning = report.get("provisioning")
    authorization = report.get("authorization")
    observations = report.get("observations")
    if not all(isinstance(section, dict) for section in (device, provisioning, authorization, observations)):
        raise CalibrationAuditLedgerError("physical provisioning evidence sections are incomplete")
    device_id = str(device.get("device_id", ""))
    state = verify_ledger(ledger_dir, policy_path=policy_path, expected_device_id=device_id)
    _require_preflight_binding(report, state)
    pre = observations.get("pre_write")
    post = observations.get("post_write")
    if not isinstance(pre, dict) or not isinstance(post, dict):
        raise CalibrationAuditLedgerError("physical provisioning evidence lacks pre/post write observations")
    from_sequence = int(pre.get("installed_sequence", -1))
    to_sequence = int(provisioning.get("candidate_sequence", -1))
    if from_sequence != state.sequence or int(post.get("installed_sequence", -1)) != to_sequence:
        raise CalibrationAuditLedgerError("physical provisioning sequence does not continue the audit ledger")
    signer_sha = _require_sha256(
        authorization.get("authority_public_key_sha256"),
        "physical evidence authority_public_key_sha256",
    )
    if signer_sha != state.authority_public_key_sha256:
        raise CalibrationAuditLedgerError("physical provisioning signer differs from audit ledger authority")
    record_sha = _require_sha256(provisioning.get("record_sha256"), "physical evidence record_sha256")
    event_type = "recovery_commit" if isinstance(report.get("recovery"), dict) else "write_commit"
    if event_type == "recovery_commit" and to_sequence != from_sequence + 1:
        raise CalibrationAuditLedgerError("recovery evidence does not use exactly the next calibration sequence")
    if to_sequence <= from_sequence:
        raise CalibrationAuditLedgerError("physical provisioning evidence does not increase calibration sequence")

    entry_core: dict[str, Any] = {
        "schema": ENTRY_SCHEMA,
        "index": state.entry_count,
        "event_type": event_type,
        "timestamp_utc": str(report.get("timestamp_utc", _utc_now())),
        "device_id": device_id,
        "previous_entry_sha256": state.head_sha256,
        "evidence": {
            "physical_evidence_sha256": _file_sha256(evidence_path),
            "artifact_index_root_sha256": _require_sha256(
                provisioning.get("artifact_index_root_sha256"),
                "physical evidence artifact_index_root_sha256",
            ),
            "authorization_payload_sha256": _require_sha256(
                authorization.get("payload_sha256"),
                "physical evidence authorization payload SHA-256",
            ),
            "authorization_signature_sha256": _require_sha256(
                authorization.get("signature_sha256"),
                "physical evidence authorization signature SHA-256",
            ),
        },
        "state_before": {
            "sequence": state.sequence,
            "record_sha256": state.record_sha256,
            "authority_public_key_sha256": state.authority_public_key_sha256,
        },
        "state_after": {
            "sequence": to_sequence,
            "record_sha256": record_sha,
            "authority_public_key_sha256": state.authority_public_key_sha256,
        },
        "authority": {
            "audit_only": True,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    return _append_entry(ledger_dir, entry_core, policy_path=policy_path)


def append_reboot_evidence(
    ledger_dir: Path,
    *,
    evidence_path: Path,
    policy_path: Path,
) -> LedgerState:
    report = _load_json(evidence_path, "reboot-verified calibration evidence")
    if report.get("schema") != PHYSICAL_EVIDENCE_SCHEMA or report.get("commit_verified") is not True:
        raise CalibrationAuditLedgerError("reboot evidence is not based on a committed calibration write")
    if report.get("reboot_recovery_verified") is not True:
        raise CalibrationAuditLedgerError("calibration reboot recovery has not been verified")
    device = report.get("device")
    provisioning = report.get("provisioning")
    authorization = report.get("authorization")
    if not all(isinstance(section, dict) for section in (device, provisioning, authorization)):
        raise CalibrationAuditLedgerError("reboot evidence sections are incomplete")
    device_id = str(device.get("device_id", ""))
    state = verify_ledger(ledger_dir, policy_path=policy_path, expected_device_id=device_id)
    _require_preflight_binding(report, state)
    sequence = int(provisioning.get("candidate_sequence", -1))
    record_sha = _require_sha256(provisioning.get("record_sha256"), "reboot evidence record SHA-256")
    signer_sha = _require_sha256(
        authorization.get("authority_public_key_sha256"),
        "reboot evidence authority public-key SHA-256",
    )
    if sequence != state.sequence or record_sha != state.record_sha256:
        raise CalibrationAuditLedgerError("reboot evidence does not match the current audit ledger calibration state")
    if signer_sha != state.authority_public_key_sha256:
        raise CalibrationAuditLedgerError("reboot evidence signer differs from audit ledger authority")
    reboot = report.get("reboot_verification")
    if not isinstance(reboot, dict) or reboot.get("boot_nonce_changed") is not True:
        raise CalibrationAuditLedgerError("reboot evidence lacks a verified new boot nonce")
    exact_record_sha = reboot.get("active_record_sha256")
    if exact_record_sha is not None and _require_sha256(
        exact_record_sha,
        "reboot exact active record SHA-256",
    ) != record_sha:
        raise CalibrationAuditLedgerError("reboot exact active record SHA-256 differs from committed record")

    entry_core: dict[str, Any] = {
        "schema": ENTRY_SCHEMA,
        "index": state.entry_count,
        "event_type": "reboot_verified",
        "timestamp_utc": str(reboot.get("timestamp_utc", _utc_now())),
        "device_id": device_id,
        "previous_entry_sha256": state.head_sha256,
        "evidence": {
            "reboot_evidence_sha256": _file_sha256(evidence_path),
            "previous_boot_nonce": int(reboot.get("previous_boot_nonce", -1)),
            "observed_boot_nonce": int(reboot.get("observed_boot_nonce", -1)),
        },
        "state_before": {
            "sequence": state.sequence,
            "record_sha256": state.record_sha256,
            "authority_public_key_sha256": state.authority_public_key_sha256,
        },
        "state_after": {
            "sequence": state.sequence,
            "record_sha256": state.record_sha256,
            "authority_public_key_sha256": state.authority_public_key_sha256,
        },
        "authority": {
            "audit_only": True,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
        },
    }
    return _append_entry(ledger_dir, entry_core, policy_path=policy_path)
