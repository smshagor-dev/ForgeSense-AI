from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from typing import Any

from .provisioning import (
    CALIBRATION_RECORD_SIZE,
    MaintenanceProvisioningError,
    STATUS_NAMES,
    STATUS_OK,
    load_provisioning_bundle,
    verify_reboot_recovery,
)
from .signed_provisioning import (
    SignedMaintenanceClient,
    VerifiedAuthorization,
    apply_signed_provisioning,
)

RECOVERY_INTENT_SCHEMA = "forgesense.calibration_recovery_intent.v1"
OP_QUERY_ACTIVE_RECORD = 0x05
OP_ACTIVE_RECORD_RESPONSE = 0x85


@dataclass(frozen=True)
class ActiveCalibrationRecord:
    present: bool
    blob: bytes | None
    sequence: int
    crc32_ieee: int
    sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "sequence": self.sequence,
            "crc32_ieee": self.crc32_ieee,
            "sha256": self.sha256,
            "record_hex": self.blob.hex() if self.blob is not None else None,
        }


class RecoveryMaintenanceClient(SignedMaintenanceClient):
    def query_active_record(self) -> ActiveCalibrationRecord:
        payload = self._request(OP_QUERY_ACTIVE_RECORD, b"", OP_ACTIVE_RECORD_RESPONSE)
        if not payload:
            raise MaintenanceProvisioningError("active-record response is empty")
        status = payload[0]
        if status != STATUS_OK:
            name = STATUS_NAMES.get(status, f"UNKNOWN_{status}")
            raise MaintenanceProvisioningError(f"active-record query rejected by device: {name}")
        if len(payload) != 50:
            raise MaintenanceProvisioningError("active-record response has invalid length")
        present = payload[1] == 1
        if not present:
            if any(payload[2:]):
                raise MaintenanceProvisioningError("inactive record response contains nonzero record bytes")
            return ActiveCalibrationRecord(False, None, 0, 0, None)

        blob = bytes(payload[2:50])
        if len(blob) != CALIBRATION_RECORD_SIZE:
            raise MaintenanceProvisioningError("active CalibrationRecord blob has invalid size")
        sequence = struct.unpack_from("<I", blob, 8)[0]
        crc32_ieee = struct.unpack_from("<I", blob, 44)[0]
        return ActiveCalibrationRecord(
            True,
            blob,
            sequence,
            crc32_ieee,
            hashlib.sha256(blob).hexdigest(),
        )


def validate_recovery_runtime_binding(
    package: dict[str, Any],
    active: ActiveCalibrationRecord,
) -> dict[str, Any] | None:
    intent = package.get("intent")
    if intent is None:
        return None
    if not isinstance(intent, dict) or intent.get("schema") != RECOVERY_INTENT_SCHEMA:
        raise MaintenanceProvisioningError("unsupported provisioning intent schema")
    if intent.get("mode") != "restore_approved_profile_with_new_sequence":
        raise MaintenanceProvisioningError("unsupported calibration recovery mode")
    if not active.present or active.blob is None or active.sha256 is None:
        raise MaintenanceProvisioningError("recovery requires an exact active CalibrationRecord readback")

    source = intent.get("from_active_record")
    sequence = intent.get("sequence_semantics")
    authority = intent.get("authority")
    if not isinstance(source, dict) or not isinstance(sequence, dict) or not isinstance(authority, dict):
        raise MaintenanceProvisioningError("calibration recovery intent is incomplete")
    if source.get("sha256") != active.sha256:
        raise MaintenanceProvisioningError("active record SHA-256 changed since recovery package creation")
    if int(source.get("sequence", -1)) != active.sequence:
        raise MaintenanceProvisioningError("active record sequence changed since recovery package creation")
    if int(source.get("crc32_ieee", -1)) != active.crc32_ieee:
        raise MaintenanceProvisioningError("active record CRC changed since recovery package creation")

    package_sequence = package.get("sequence")
    if not isinstance(package_sequence, dict):
        raise MaintenanceProvisioningError("recovery provisioning sequence metadata is missing")
    installed = int(package_sequence.get("installed", -1))
    candidate = int(package_sequence.get("candidate", -1))
    if installed != active.sequence or candidate != installed + 1:
        raise MaintenanceProvisioningError("recovery must restore coefficients using exactly the next sequence")
    if (
        sequence.get("decrement_permitted") is not False
        or sequence.get("candidate_is_new_higher_sequence") is not True
        or sequence.get("increment_exactly_one") is not True
    ):
        raise MaintenanceProvisioningError("recovery intent sequence semantics are invalid")

    expected_authority = {
        "signed_maintenance_authorization_required": True,
        "automatic_recovery": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
        "hardware_backed_monotonic_counter_claimed": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) is not expected:
            raise MaintenanceProvisioningError(f"recovery authority field {key} is invalid")
    return intent


def apply_recovery_aware_signed_provisioning(
    client: RecoveryMaintenanceClient,
    provisioning_dir,
    *,
    authorization: VerifiedAuthorization,
    operator: str,
) -> dict[str, Any]:
    package, _, _ = load_provisioning_bundle(provisioning_dir)
    intent = package.get("intent")
    active_before = None
    if intent is not None:
        active_before = client.query_active_record()
        validate_recovery_runtime_binding(package, active_before)

    report = apply_signed_provisioning(
        client,
        provisioning_dir,
        authorization=authorization,
        operator=operator,
    )

    active_after = client.query_active_record()
    expected_sha = str(report["provisioning"]["record_sha256"])
    expected_sequence = int(report["provisioning"]["candidate_sequence"])
    expected_crc = int(report["provisioning"]["candidate_crc32_ieee"])
    if not active_after.present or active_after.sha256 != expected_sha:
        raise MaintenanceProvisioningError("post-write exact active record differs from committed calibration record")
    if active_after.sequence != expected_sequence or active_after.crc32_ieee != expected_crc:
        raise MaintenanceProvisioningError("post-write exact active record sequence/CRC differs from committed record")
    report["observations"]["post_write_exact_active_record"] = active_after.as_dict()

    if intent is not None and active_before is not None:
        if active_after.sequence != active_before.sequence + 1:
            raise MaintenanceProvisioningError("post-recovery active record did not preserve exact next-sequence semantics")
        report["recovery"] = {
            "intent_schema": RECOVERY_INTENT_SCHEMA,
            "mode": "restore_approved_profile_with_new_sequence",
            "from_active_record": active_before.as_dict(),
            "to_active_record": active_after.as_dict(),
            "monotonic_sequence_preserved": True,
            "sequence_decrement_performed": False,
        }
    return report


def verify_recovery_aware_reboot(
    client: RecoveryMaintenanceClient,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    verified = verify_reboot_recovery(client, evidence)
    provisioning = evidence.get("provisioning")
    if not isinstance(provisioning, dict):
        raise MaintenanceProvisioningError("prior provisioning evidence is missing")
    expected_sha = str(provisioning.get("record_sha256", ""))
    expected_sequence = int(provisioning.get("candidate_sequence", -1))
    expected_crc = int(provisioning.get("candidate_crc32_ieee", -1))
    active = client.query_active_record()
    if not active.present or active.sha256 != expected_sha:
        raise MaintenanceProvisioningError("reboot exact active-record SHA-256 differs from committed evidence")
    if active.sequence != expected_sequence or active.crc32_ieee != expected_crc:
        raise MaintenanceProvisioningError("reboot exact active-record sequence/CRC differs from committed evidence")

    reboot = verified.get("reboot_verification")
    if not isinstance(reboot, dict):
        raise MaintenanceProvisioningError("reboot recovery evidence section is missing")
    reboot["exact_active_record"] = active.as_dict()
    reboot["active_record_sha256"] = active.sha256
    reboot["exact_record_sha256_match"] = True

    recovery = evidence.get("recovery")
    if recovery is not None:
        if not isinstance(recovery, dict) or recovery.get("intent_schema") != RECOVERY_INTENT_SCHEMA:
            raise MaintenanceProvisioningError("prior recovery evidence is incomplete or unsupported")
        reboot["recovery_exact_record_reverified"] = True
    return verified
