from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import time
import zlib

MAGIC = b"FSM1"
VERSION = 1
MAX_PAYLOAD = 64
HEADER_SIZE = 8
CRC_SIZE = 4
MAX_FRAME_SIZE = HEADER_SIZE + MAX_PAYLOAD + CRC_SIZE

OP_QUERY_STATUS = 0x01
OP_PREPARE_RECORD = 0x02
OP_COMMIT_RECORD = 0x03
OP_STATUS_RESPONSE = 0x81
OP_PREPARE_RESPONSE = 0x82
OP_COMMIT_RESPONSE = 0x83

STATUS_OK = 0
STATUS_NAMES = {
    0: "OK",
    1: "BAD_REQUEST",
    2: "PHYSICAL_GATE_OPEN",
    3: "STORE_UNAVAILABLE",
    4: "SESSION_MISMATCH",
    5: "SEQUENCE_MISMATCH",
    6: "RECORD_INVALID",
    7: "PENDING_MISMATCH",
    8: "COMMIT_FAILED",
    9: "INTERNAL_ERROR",
}

PHYSICAL_EVIDENCE_SCHEMA = "forgesense.calibration_physical_provisioning.v1"
PROVISIONING_SCHEMA = "forgesense.calibration_provisioning_package.v1"
ARTIFACT_INDEX_SCHEMA = "forgesense.calibration_provisioning_artifact_index.v1"
CALIBRATION_RECORD_SIZE = 48


class MaintenanceProvisioningError(ValueError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MaintenanceProvisioningError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise MaintenanceProvisioningError(f"{label} must contain a JSON object")
    return value


def encode_frame(opcode: int, payload: bytes = b"") -> bytes:
    if not 0 <= opcode <= 0xFF:
        raise MaintenanceProvisioningError("maintenance opcode must fit one byte")
    if len(payload) > MAX_PAYLOAD:
        raise MaintenanceProvisioningError("maintenance payload exceeds maximum size")
    header = MAGIC + bytes((VERSION, opcode)) + struct.pack("<H", len(payload))
    body = header + payload
    return body + struct.pack("<I", zlib.crc32(body) & 0xFFFFFFFF)


@dataclass(frozen=True)
class Frame:
    opcode: int
    payload: bytes


class FrameParser:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def reset(self) -> None:
        self._buffer.clear()

    def feed(self, data: bytes) -> list[Frame]:
        self._buffer.extend(data)
        frames: list[Frame] = []
        while True:
            magic_index = self._buffer.find(MAGIC)
            if magic_index < 0:
                keep = min(len(self._buffer), len(MAGIC) - 1)
                if keep:
                    tail = self._buffer[-keep:]
                    self._buffer.clear()
                    self._buffer.extend(tail)
                else:
                    self._buffer.clear()
                break
            if magic_index:
                del self._buffer[:magic_index]
            if len(self._buffer) < HEADER_SIZE:
                break
            if self._buffer[4] != VERSION:
                del self._buffer[0]
                continue
            payload_size = struct.unpack_from("<H", self._buffer, 6)[0]
            if payload_size > MAX_PAYLOAD:
                del self._buffer[0]
                continue
            frame_size = HEADER_SIZE + payload_size + CRC_SIZE
            if len(self._buffer) < frame_size:
                break
            claimed_crc = struct.unpack_from("<I", self._buffer, frame_size - CRC_SIZE)[0]
            computed_crc = zlib.crc32(self._buffer[: frame_size - CRC_SIZE]) & 0xFFFFFFFF
            if claimed_crc != computed_crc:
                del self._buffer[0]
                continue
            frames.append(Frame(self._buffer[5], bytes(self._buffer[HEADER_SIZE : HEADER_SIZE + payload_size])))
            del self._buffer[:frame_size]
        return frames


@dataclass(frozen=True)
class DeviceStatus:
    device_id: str
    mac_hex: str
    boot_nonce: int
    maintenance_asserted: bool
    load_inhibit_asserted: bool
    store_ready: bool
    has_active: bool
    installed_sequence: int
    installed_crc32: int
    pending_sequence: int

    def as_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "mac_hex": self.mac_hex,
            "boot_nonce": self.boot_nonce,
            "maintenance_asserted": self.maintenance_asserted,
            "load_inhibit_asserted": self.load_inhibit_asserted,
            "store_ready": self.store_ready,
            "has_active": self.has_active,
            "installed_sequence": self.installed_sequence,
            "installed_crc32": self.installed_crc32,
            "pending_sequence": self.pending_sequence,
        }


@dataclass(frozen=True)
class PrepareResult:
    sequence: int
    record_crc32: int
    commit_nonce: int


@dataclass(frozen=True)
class CommitResult:
    installed_sequence: int
    installed_crc32: int


class MaintenanceClient:
    def __init__(self, transport, *, timeout_s: float = 1.0) -> None:
        if timeout_s <= 0:
            raise MaintenanceProvisioningError("maintenance timeout must be positive")
        self.transport = transport
        self.timeout_s = timeout_s
        self.parser = FrameParser()

    def _write_all(self, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            written = self.transport.write(data[offset:])
            if written is None:
                written = len(data) - offset
            if written <= 0:
                raise MaintenanceProvisioningError("maintenance transport write made no progress")
            offset += int(written)

    def _request(self, opcode: int, payload: bytes, response_opcode: int) -> bytes:
        self._write_all(encode_frame(opcode, payload))
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            chunk = self.transport.read(128)
            if not chunk:
                continue
            for frame in self.parser.feed(bytes(chunk)):
                if frame.opcode == response_opcode:
                    return frame.payload
        raise MaintenanceProvisioningError(
            f"maintenance response timeout waiting for opcode 0x{response_opcode:02x}"
        )

    @staticmethod
    def _status_error(payload: bytes, expected_size: int, label: str) -> None:
        if not payload:
            raise MaintenanceProvisioningError(f"{label} response is empty")
        status = payload[0]
        if status != STATUS_OK:
            name = STATUS_NAMES.get(status, f"UNKNOWN_{status}")
            raise MaintenanceProvisioningError(f"{label} rejected by device: {name}")
        if len(payload) != expected_size:
            raise MaintenanceProvisioningError(f"{label} response has invalid length {len(payload)}")

    def query_status(self) -> DeviceStatus:
        payload = self._request(OP_QUERY_STATUS, b"", OP_STATUS_RESPONSE)
        self._status_error(payload, 27, "status query")
        mac = payload[1:7]
        mac_hex = mac.hex()
        return DeviceStatus(
            device_id=f"esp32s3:{mac_hex}",
            mac_hex=mac_hex,
            boot_nonce=struct.unpack_from("<I", payload, 7)[0],
            maintenance_asserted=payload[11] == 1,
            load_inhibit_asserted=payload[12] == 1,
            store_ready=payload[13] == 1,
            has_active=payload[14] == 1,
            installed_sequence=struct.unpack_from("<I", payload, 15)[0],
            installed_crc32=struct.unpack_from("<I", payload, 19)[0],
            pending_sequence=struct.unpack_from("<I", payload, 23)[0],
        )

    def prepare_record(self, *, boot_nonce: int, expected_floor: int, record_blob: bytes) -> PrepareResult:
        if len(record_blob) != CALIBRATION_RECORD_SIZE:
            raise MaintenanceProvisioningError("CalibrationRecord blob must be exactly 48 bytes")
        payload = struct.pack("<II", boot_nonce, expected_floor) + record_blob
        response = self._request(OP_PREPARE_RECORD, payload, OP_PREPARE_RESPONSE)
        self._status_error(response, 13, "prepare")
        return PrepareResult(
            sequence=struct.unpack_from("<I", response, 1)[0],
            record_crc32=struct.unpack_from("<I", response, 5)[0],
            commit_nonce=struct.unpack_from("<I", response, 9)[0],
        )

    def commit_record(self, *, boot_nonce: int, commit_nonce: int, sequence: int) -> CommitResult:
        payload = struct.pack("<III", boot_nonce, commit_nonce, sequence)
        response = self._request(OP_COMMIT_RECORD, payload, OP_COMMIT_RESPONSE)
        self._status_error(response, 9, "commit")
        return CommitResult(
            installed_sequence=struct.unpack_from("<I", response, 1)[0],
            installed_crc32=struct.unpack_from("<I", response, 5)[0],
        )


def load_provisioning_bundle(provisioning_dir: Path) -> tuple[dict, dict, bytes]:
    provisioning_dir = provisioning_dir.resolve()
    package = _load_json(provisioning_dir / "provisioning.json", "provisioning package")
    index = _load_json(provisioning_dir / "artifact-index.json", "provisioning artifact index")
    try:
        record_blob = (provisioning_dir / "calibration-record.bin").read_bytes()
    except FileNotFoundError as exc:
        raise MaintenanceProvisioningError("calibration-record.bin is missing") from exc

    if package.get("schema") != PROVISIONING_SCHEMA:
        raise MaintenanceProvisioningError("unsupported provisioning package schema")
    if index.get("schema") != ARTIFACT_INDEX_SCHEMA:
        raise MaintenanceProvisioningError("unsupported provisioning artifact index schema")
    if len(record_blob) != CALIBRATION_RECORD_SIZE:
        raise MaintenanceProvisioningError("retained CalibrationRecord blob is not 48 bytes")

    claimed_root = str(index.get("root_sha256", ""))
    index_core = {key: value for key, value in index.items() if key != "root_sha256"}
    if _canonical_sha256(index_core) != claimed_root:
        raise MaintenanceProvisioningError("provisioning artifact index root mismatch")

    entries = index.get("artifacts")
    if not isinstance(entries, list):
        raise MaintenanceProvisioningError("provisioning artifact index is missing artifacts")
    hashes = {str(item.get("path")): str(item.get("sha256")) for item in entries if isinstance(item, dict)}
    for name in ("provisioning.json", "calibration-record.bin", "calibration-record.hex"):
        if hashes.get(name) != _file_sha256(provisioning_dir / name):
            raise MaintenanceProvisioningError(f"provisioning artifact hash mismatch: {name}")
    if package.get("record", {}).get("sha256") != _sha256_bytes(record_blob):
        raise MaintenanceProvisioningError("provisioning record SHA-256 metadata mismatch")
    return package, index, record_blob


def apply_provisioning(
    client: MaintenanceClient,
    provisioning_dir: Path,
    *,
    operator: str,
) -> dict:
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

    pre = client.query_status()
    if pre.device_id != package.get("device_id"):
        raise MaintenanceProvisioningError(
            f"device identity mismatch: package={package.get('device_id')} device={pre.device_id}"
        )
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

    prepared = client.prepare_record(
        boot_nonce=pre.boot_nonce,
        expected_floor=pre.installed_sequence,
        record_blob=record_blob,
    )
    if prepared.sequence != candidate_sequence or prepared.record_crc32 != expected_crc:
        raise MaintenanceProvisioningError("device PREPARE acknowledgement differs from requested record")
    if prepared.commit_nonce in (0, 0xFFFFFFFF):
        raise MaintenanceProvisioningError("device returned an invalid commit nonce")

    committed = client.commit_record(
        boot_nonce=pre.boot_nonce,
        commit_nonce=prepared.commit_nonce,
        sequence=candidate_sequence,
    )
    if committed.installed_sequence != candidate_sequence or committed.installed_crc32 != expected_crc:
        raise MaintenanceProvisioningError("device COMMIT acknowledgement differs from requested record")

    post = client.query_status()
    if post.device_id != pre.device_id or post.boot_nonce != pre.boot_nonce:
        raise MaintenanceProvisioningError("device identity/session changed before post-write verification")
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
            "directory": str(provisioning_dir),
            "artifact_index_root_sha256": index["root_sha256"],
            "provisioning_json_sha256": _file_sha256(provisioning_dir / "provisioning.json"),
            "record_sha256": _sha256_bytes(record_blob),
            "candidate_sequence": candidate_sequence,
            "candidate_crc32_ieee": expected_crc,
        },
        "device": {
            "device_id": pre.device_id,
            "boot_nonce": pre.boot_nonce,
        },
        "observations": {
            "pre_write": pre.as_dict(),
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
            "automatic_provisioning": False,
            "may_control_actuators": False,
            "may_relax_hard_safety_limits": False,
            "hardware_backed_monotonic_counter_claimed": False,
        },
        "evidence_boundary": (
            "This report records maintenance-protocol observations for one device write. "
            "It does not establish calibration accuracy, metrological traceability, product certification, "
            "or hardware-backed rollback protection."
        ),
    }


def verify_reboot_recovery(client: MaintenanceClient, evidence: dict) -> dict:
    if evidence.get("schema") != PHYSICAL_EVIDENCE_SCHEMA or evidence.get("commit_verified") is not True:
        raise MaintenanceProvisioningError("prior physical provisioning evidence is invalid or uncommitted")
    device = evidence.get("device")
    provisioning = evidence.get("provisioning")
    if not isinstance(device, dict) or not isinstance(provisioning, dict):
        raise MaintenanceProvisioningError("prior provisioning evidence is incomplete")

    expected_device = str(device.get("device_id", ""))
    prior_boot_nonce = int(device.get("boot_nonce", -1))
    expected_sequence = int(provisioning.get("candidate_sequence", -1))
    expected_crc = int(provisioning.get("candidate_crc32_ieee", -1))

    status = client.query_status()
    if status.device_id != expected_device:
        raise MaintenanceProvisioningError("reboot verification reached a different device")
    if status.boot_nonce == prior_boot_nonce:
        raise MaintenanceProvisioningError("boot nonce did not change; a new boot/recovery was not observed")
    if not status.store_ready or not status.has_active:
        raise MaintenanceProvisioningError("calibration store did not recover an active record after reboot")
    if status.installed_sequence != expected_sequence or status.installed_crc32 != expected_crc:
        raise MaintenanceProvisioningError("recovered calibration record differs from committed evidence")
    if status.pending_sequence != 0:
        raise MaintenanceProvisioningError("device reports a pending record after reboot recovery")

    verified = deepcopy(evidence)
    verified["reboot_recovery_verified"] = True
    verified["reboot_verification"] = {
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "previous_boot_nonce": prior_boot_nonce,
        "observed_boot_nonce": status.boot_nonce,
        "boot_nonce_changed": True,
        "recovered_status": status.as_dict(),
        "sequence_match": True,
        "crc_match": True,
    }
    return verified
