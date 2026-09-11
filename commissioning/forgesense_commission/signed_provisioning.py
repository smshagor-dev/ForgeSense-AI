from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import time
from typing import Any
import zlib

from .provisioning import (
    ARTIFACT_INDEX_SCHEMA,
    CALIBRATION_RECORD_SIZE,
    CommitResult,
    DeviceStatus,
    MaintenanceClient,
    MaintenanceProvisioningError,
    PHYSICAL_EVIDENCE_SCHEMA,
    PrepareResult,
    PROVISIONING_SCHEMA,
    STATUS_NAMES,
    STATUS_OK,
    load_provisioning_bundle,
)

AUTHORIZATION_DOMAIN = b"ForgeSense-Calibration-Maintenance-Authorization-v1\n"
AUTHORIZATION_REQUEST_SCHEMA = "forgesense.calibration_maintenance_authorization_request.v1"
AUTHORIZATION_SCHEMA = "forgesense.calibration_maintenance_authorization.v1"
OP_QUERY_AUTHORIZATION = 0x04
OP_AUTHORIZATION_RESPONSE = 0x84
OP_PREPARE_RECORD = 0x02
OP_PREPARE_RESPONSE = 0x82
MAX_MAINTENANCE_PAYLOAD = 192
MAX_SIGNATURE_SIZE = 80


@dataclass(frozen=True)
class AuthorizationStatus:
    ready: bool
    public_key_sha256: str


@dataclass(frozen=True)
class VerifiedAuthorization:
    package: dict[str, Any]
    signature_der: bytes
    artifact_root_sha256: bytes
    public_key_sha256: str
    payload_sha256: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MaintenanceProvisioningError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MaintenanceProvisioningError(f"{label} must contain a JSON object")
    return value


def _mac_from_device_id(device_id: str) -> bytes:
    prefix = "esp32s3:"
    if not device_id.startswith(prefix):
        raise MaintenanceProvisioningError("authorization device_id must use esp32s3:<12 hex> format")
    text = device_id[len(prefix) :]
    if len(text) != 12:
        raise MaintenanceProvisioningError("authorization device_id MAC must contain 12 hex characters")
    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        raise MaintenanceProvisioningError("authorization device_id MAC is not valid hex") from exc


def authorization_payload(
    *,
    device_id: str,
    expected_installed_sequence: int,
    artifact_root_sha256: str,
    record_blob: bytes,
) -> bytes:
    if expected_installed_sequence < 0 or expected_installed_sequence > 0xFFFFFFFF:
        raise MaintenanceProvisioningError("authorization expected sequence is outside uint32 range")
    if len(record_blob) != CALIBRATION_RECORD_SIZE:
        raise MaintenanceProvisioningError("authorization record must be exactly 48 bytes")
    try:
        root = bytes.fromhex(artifact_root_sha256)
    except ValueError as exc:
        raise MaintenanceProvisioningError("authorization artifact root is not valid hex") from exc
    if len(root) != 32:
        raise MaintenanceProvisioningError("authorization artifact root must be a SHA-256 digest")
    return (
        AUTHORIZATION_DOMAIN
        + _mac_from_device_id(device_id)
        + struct.pack("<I", expected_installed_sequence)
        + root
        + record_blob
    )


def _run_openssl(args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["openssl", *args],
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError("OpenSSL is required for maintenance authorization verification") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise MaintenanceProvisioningError(f"OpenSSL verification command failed: {detail or result.returncode}")
    return result.stdout


def public_key_der(public_key_path: Path) -> bytes:
    text = _run_openssl(["pkey", "-pubin", "-in", str(public_key_path), "-text_pub", "-noout"])
    description = text.decode("utf-8", errors="replace")
    if "prime256v1" not in description and "P-256" not in description:
        raise MaintenanceProvisioningError("maintenance authority public key must use NIST P-256/prime256v1")
    der = _run_openssl(["pkey", "-pubin", "-in", str(public_key_path), "-outform", "DER"])
    if not der:
        raise MaintenanceProvisioningError("maintenance authority public key DER is empty")
    return der


def verify_signature_openssl(
    *,
    public_key_path: Path,
    payload: bytes,
    signature_der: bytes,
) -> str:
    if not signature_der or len(signature_der) > MAX_SIGNATURE_SIZE:
        raise MaintenanceProvisioningError("maintenance authorization signature length is invalid")
    der = public_key_der(public_key_path)
    with tempfile.TemporaryDirectory(prefix="forgesense-auth-") as tmp:
        root = Path(tmp)
        payload_path = root / "payload.bin"
        signature_path = root / "signature.der"
        payload_path.write_bytes(payload)
        signature_path.write_bytes(signature_der)
        _run_openssl(
            [
                "dgst",
                "-sha256",
                "-verify",
                str(public_key_path),
                "-signature",
                str(signature_path),
                str(payload_path),
            ]
        )
    return _sha256_bytes(der)


def verify_authorization_bundle(
    authorization_dir: Path,
    *,
    provisioning_dir: Path,
    public_key_path: Path,
) -> VerifiedAuthorization:
    authorization_dir = authorization_dir.resolve()
    package = _load_json(authorization_dir / "authorization.json", "maintenance authorization")
    if package.get("schema") != AUTHORIZATION_SCHEMA:
        raise MaintenanceProvisioningError("unsupported maintenance authorization schema")
    try:
        signature_der = (authorization_dir / "authorization-signature.der").read_bytes()
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError("authorization-signature.der is missing") from exc

    provisioning, index, record_blob = load_provisioning_bundle(provisioning_dir)
    if provisioning.get("schema") != PROVISIONING_SCHEMA or index.get("schema") != ARTIFACT_INDEX_SCHEMA:
        raise MaintenanceProvisioningError("provisioning bundle schema mismatch during authorization verification")

    device_id = str(provisioning.get("device_id", ""))
    sequence = provisioning.get("sequence")
    if not isinstance(sequence, dict):
        raise MaintenanceProvisioningError("provisioning sequence metadata is missing")
    expected_installed = int(sequence.get("installed", -1))
    candidate_sequence = int(sequence.get("candidate", -1))
    artifact_root = str(index.get("root_sha256", ""))
    payload = authorization_payload(
        device_id=device_id,
        expected_installed_sequence=expected_installed,
        artifact_root_sha256=artifact_root,
        record_blob=record_blob,
    )
    payload_sha256 = _sha256_bytes(payload)

    expected_fields = {
        "device_id": device_id,
        "expected_installed_sequence": expected_installed,
        "candidate_sequence": candidate_sequence,
        "artifact_root_sha256": artifact_root,
        "record_sha256": _sha256_bytes(record_blob),
        "payload_sha256": payload_sha256,
        "signature_format": "ECDSA-P256-SHA256-DER",
    }
    for key, expected in expected_fields.items():
        if package.get(key) != expected:
            raise MaintenanceProvisioningError(f"authorization metadata mismatch for {key}")
    if package.get("signature_sha256") != _sha256_bytes(signature_der):
        raise MaintenanceProvisioningError("authorization signature SHA-256 mismatch")

    key_fingerprint = verify_signature_openssl(
        public_key_path=public_key_path,
        payload=payload,
        signature_der=signature_der,
    )
    if package.get("authority_public_key_sha256") != key_fingerprint:
        raise MaintenanceProvisioningError("authorization public-key fingerprint mismatch")

    authority = package.get("authority")
    if not isinstance(authority, dict):
        raise MaintenanceProvisioningError("authorization authority section is missing")
    expected_authority = {
        "external_signature_required": True,
        "signature_verified": True,
        "private_key_accessed_by_tool": False,
        "automatic_provisioning": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) is not expected:
            raise MaintenanceProvisioningError(f"authorization authority field {key} is invalid")

    return VerifiedAuthorization(
        package=package,
        signature_der=signature_der,
        artifact_root_sha256=bytes.fromhex(artifact_root),
        public_key_sha256=key_fingerprint,
        payload_sha256=payload_sha256,
    )


def _encode_large_frame(opcode: int, payload: bytes = b"") -> bytes:
    if not 0 <= opcode <= 0xFF:
        raise MaintenanceProvisioningError("maintenance opcode must fit one byte")
    if len(payload) > MAX_MAINTENANCE_PAYLOAD:
        raise MaintenanceProvisioningError("maintenance payload exceeds signed-protocol maximum")
    header = b"FSM1" + bytes((1, opcode)) + struct.pack("<H", len(payload))
    body = header + payload
    return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)


class SignedMaintenanceClient(MaintenanceClient):
    def _request_large(self, opcode: int, payload: bytes, response_opcode: int) -> bytes:
        self._write_all(_encode_large_frame(opcode, payload))
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            chunk = self.transport.read(256)
            if not chunk:
                continue
            for frame in self.parser.feed(bytes(chunk)):
                if frame.opcode == response_opcode:
                    return frame.payload
        raise MaintenanceProvisioningError(
            f"maintenance response timeout waiting for opcode 0x{response_opcode:02x}"
        )

    def query_authorization(self) -> AuthorizationStatus:
        payload = self._request(OP_QUERY_AUTHORIZATION, b"", OP_AUTHORIZATION_RESPONSE)
        if not payload:
            raise MaintenanceProvisioningError("authorization status response is empty")
        status = payload[0]
        if status != STATUS_OK:
            name = STATUS_NAMES.get(status, f"UNKNOWN_{status}")
            raise MaintenanceProvisioningError(f"authorization status rejected by device: {name}")
        if len(payload) != 34:
            raise MaintenanceProvisioningError("authorization status response has invalid length")
        return AuthorizationStatus(
            ready=payload[1] == 1,
            public_key_sha256=bytes(payload[2:34]).hex(),
        )

    def prepare_authorized_record(
        self,
        *,
        boot_nonce: int,
        expected_floor: int,
        artifact_root_sha256: bytes,
        record_blob: bytes,
        signature_der: bytes,
    ) -> PrepareResult:
        if len(artifact_root_sha256) != 32:
            raise MaintenanceProvisioningError("authorization artifact root must be 32 bytes")
        if len(record_blob) != CALIBRATION_RECORD_SIZE:
            raise MaintenanceProvisioningError("CalibrationRecord blob must be exactly 48 bytes")
        if not signature_der or len(signature_der) > MAX_SIGNATURE_SIZE:
            raise MaintenanceProvisioningError("authorization signature length is invalid")
        payload = (
            struct.pack("<II", boot_nonce, expected_floor)
            + artifact_root_sha256
            + record_blob
            + struct.pack("<H", len(signature_der))
            + signature_der
        )
        response = self._request_large(OP_PREPARE_RECORD, payload, OP_PREPARE_RESPONSE)
        if not response:
            raise MaintenanceProvisioningError("signed prepare response is empty")
        status = response[0]
        if status != STATUS_OK:
            name = {
                **STATUS_NAMES,
                10: "AUTHORIZATION_FAILED",
                11: "AUTHORIZATION_UNAVAILABLE",
            }.get(status, f"UNKNOWN_{status}")
            raise MaintenanceProvisioningError(f"signed prepare rejected by device: {name}")
        if len(response) != 13:
            raise MaintenanceProvisioningError("signed prepare response has invalid length")
        return PrepareResult(
            sequence=struct.unpack_from("<I", response, 1)[0],
            record_crc32=struct.unpack_from("<I", response, 5)[0],
            commit_nonce=struct.unpack_from("<I", response, 9)[0],
        )


def apply_signed_provisioning(
    client: SignedMaintenanceClient,
    provisioning_dir: Path,
    *,
    authorization: VerifiedAuthorization,
    operator: str,
) -> dict[str, Any]:
    if not operator.strip():
        raise MaintenanceProvisioningError("operator is required for physical provisioning evidence")
    package, index, record_blob = load_provisioning_bundle(provisioning_dir)
    sequence = package.get("sequence")
    record = package.get("record")
    if not isinstance(sequence, dict) or not isinstance(record, dict):
        raise MaintenanceProvisioningError("provisioning package sequence/record metadata is incomplete")
    candidate_sequence = int(sequence.get("candidate", -1))
    expected_installed = int(sequence.get("installed", -1))
    expected_crc = int(record.get("crc32_ieee", -1))
    if struct.unpack_from("<I", record_blob, 44)[0] != expected_crc:
        raise MaintenanceProvisioningError("retained record CRC differs from package metadata")

    pre: DeviceStatus = client.query_status()
    auth_status = client.query_authorization()
    if pre.device_id != package.get("device_id"):
        raise MaintenanceProvisioningError(
            f"device identity mismatch: package={package.get('device_id')} device={pre.device_id}"
        )
    if not auth_status.ready:
        raise MaintenanceProvisioningError("device has no ready pinned maintenance authority public key")
    if auth_status.public_key_sha256 != authorization.public_key_sha256:
        raise MaintenanceProvisioningError("device pinned public key differs from verified authorization signer")
    if not pre.store_ready:
        raise MaintenanceProvisioningError("device calibration store is unavailable")
    if not pre.maintenance_asserted or not pre.load_inhibit_asserted:
        raise MaintenanceProvisioningError("both physical maintenance and load-inhibit gates must be asserted")
    if pre.installed_sequence != expected_installed:
        raise MaintenanceProvisioningError(
            f"installed sequence changed: package={expected_installed} device={pre.installed_sequence}"
        )
    if candidate_sequence <= pre.installed_sequence:
        raise MaintenanceProvisioningError("candidate sequence is not newer than device state")
    if pre.pending_sequence != 0:
        raise MaintenanceProvisioningError("device already has a pending maintenance record; reboot before retrying")

    prepared = client.prepare_authorized_record(
        boot_nonce=pre.boot_nonce,
        expected_floor=pre.installed_sequence,
        artifact_root_sha256=authorization.artifact_root_sha256,
        record_blob=record_blob,
        signature_der=authorization.signature_der,
    )
    if prepared.sequence != candidate_sequence or prepared.record_crc32 != expected_crc:
        raise MaintenanceProvisioningError("device signed PREPARE acknowledgement differs from requested record")
    if prepared.commit_nonce in (0, 0xFFFFFFFF):
        raise MaintenanceProvisioningError("device returned an invalid commit nonce")

    committed: CommitResult = client.commit_record(
        boot_nonce=pre.boot_nonce,
        commit_nonce=prepared.commit_nonce,
        sequence=candidate_sequence,
    )
    if committed.installed_sequence != candidate_sequence or committed.installed_crc32 != expected_crc:
        raise MaintenanceProvisioningError("device COMMIT acknowledgement differs from requested record")

    post: DeviceStatus = client.query_status()
    post_auth = client.query_authorization()
    if post.device_id != pre.device_id or post.boot_nonce != pre.boot_nonce:
        raise MaintenanceProvisioningError("device identity/session changed before post-write verification")
    if not post_auth.ready or post_auth.public_key_sha256 != authorization.public_key_sha256:
        raise MaintenanceProvisioningError("device authority key changed before post-write verification")
    if not post.store_ready or not post.has_active:
        raise MaintenanceProvisioningError("device store did not report an active record after commit")
    if post.installed_sequence != candidate_sequence or post.installed_crc32 != expected_crc:
        raise MaintenanceProvisioningError("post-write status does not match committed record")
    if post.pending_sequence != 0:
        raise MaintenanceProvisioningError("pending record was not cleared after commit")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema": PHYSICAL_EVIDENCE_SCHEMA,
        "timestamp_utc": now,
        "operator": operator.strip(),
        "provisioning": {
            "directory": str(Path(provisioning_dir).resolve()),
            "artifact_index_root_sha256": index["root_sha256"],
            "provisioning_json_sha256": _file_sha256(Path(provisioning_dir) / "provisioning.json"),
            "record_sha256": _sha256_bytes(record_blob),
            "candidate_sequence": candidate_sequence,
            "candidate_crc32_ieee": expected_crc,
        },
        "authorization": {
            "schema": authorization.package.get("schema"),
            "payload_sha256": authorization.payload_sha256,
            "signature_sha256": authorization.package.get("signature_sha256"),
            "signature_format": authorization.package.get("signature_format"),
            "authority_public_key_sha256": authorization.public_key_sha256,
            "host_signature_verification": True,
            "device_signature_verification_confirmed_by_prepare": True,
        },
        "device": {
            "device_id": pre.device_id,
            "boot_nonce": pre.boot_nonce,
        },
        "observations": {
            "pre_write": pre.as_dict(),
            "pre_write_authorization": {
                "ready": auth_status.ready,
                "public_key_sha256": auth_status.public_key_sha256,
            },
            "prepare": {
                "sequence": prepared.sequence,
                "record_crc32_ieee": prepared.record_crc32,
                "commit_nonce": prepared.commit_nonce,
            },
            "commit": {
                "installed_sequence": committed.installed_sequence,
                "installed_crc32_ieee": committed.installed_crc32,
            },
            "post_write": post.as_dict(),
        },
        "commit_verified": True,
        "reboot_recovery_verified": False,
        "authority": {
            "maintenance_only": True,
            "signed_authorization_required": True,
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
        "evidence_boundary": (
            "This report records cryptographically authorized maintenance-protocol observations for one device write. "
            "It does not establish calibration accuracy, metrological traceability, product certification, "
            "or hardware-backed rollback protection."
        ),
    }
