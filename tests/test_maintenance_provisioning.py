from __future__ import annotations

import json
from pathlib import Path
import struct
import zlib

import pytest

from commissioning.forgesense_commission.provisioning import (
    ARTIFACT_INDEX_SCHEMA,
    OP_COMMIT_RECORD,
    OP_COMMIT_RESPONSE,
    OP_PREPARE_RECORD,
    OP_PREPARE_RESPONSE,
    OP_QUERY_STATUS,
    OP_STATUS_RESPONSE,
    PROVISIONING_SCHEMA,
    FrameParser,
    MaintenanceClient,
    MaintenanceProvisioningError,
    apply_provisioning,
    encode_frame,
    verify_reboot_recovery,
)


def _canonical_sha256(data: dict) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def make_record(sequence: int, *, current_num: int = 1, current_den: int = 2000) -> bytes:
    prefix = struct.pack(
        "<IHHIiiiiiiii",
        0x46534331,
        1,
        48,
        sequence,
        0,
        1,
        1,
        2,
        0,
        current_num,
        current_den,
        0,
    )
    return prefix + struct.pack("<I", zlib.crc32(prefix) & 0xFFFFFFFF)


def make_bundle(tmp_path: Path, *, device_id: str = "esp32s3:aabbccddeeff", installed: int = 4, candidate: int = 5) -> Path:
    root = tmp_path / "provisioning"
    root.mkdir()
    blob = make_record(candidate)
    record_crc = struct.unpack_from("<I", blob, 44)[0]
    package = {
        "schema": PROVISIONING_SCHEMA,
        "device_id": device_id,
        "sequence": {"installed": installed, "candidate": candidate},
        "record": {
            "crc32_ieee": record_crc,
            "sha256": _sha256(blob),
        },
    }
    provisioning_bytes = (json.dumps(package, indent=2) + "\n").encode()
    hex_bytes = (blob.hex() + "\n").encode("ascii")
    (root / "provisioning.json").write_bytes(provisioning_bytes)
    (root / "calibration-record.bin").write_bytes(blob)
    (root / "calibration-record.hex").write_bytes(hex_bytes)
    index_core = {
        "schema": ARTIFACT_INDEX_SCHEMA,
        "artifacts": [
            {"path": "calibration-record.bin", "sha256": _sha256(blob)},
            {"path": "calibration-record.hex", "sha256": _sha256(hex_bytes)},
            {"path": "provisioning.json", "sha256": _sha256(provisioning_bytes)},
        ],
    }
    index = dict(index_core)
    index["root_sha256"] = _canonical_sha256(index_core)
    (root / "artifact-index.json").write_text(json.dumps(index, indent=2) + "\n")
    return root


class FakeMaintenanceTransport:
    def __init__(self) -> None:
        self.mac = bytes.fromhex("aabbccddeeff")
        self.boot_nonce = 0x12345678
        self.maintenance = True
        self.inhibit = True
        self.store_ready = True
        self.has_active = True
        self.installed_sequence = 4
        self.installed_crc = 0x11112222
        self.pending_blob: bytes | None = None
        self.commit_nonce = 0xA1B2C3D4
        self.rx = bytearray()
        self.parser = FrameParser()
        self.opcodes: list[int] = []
        self.prepare_status = 0
        self.commit_status = 0
        self.post_sequence_override: int | None = None
        self.post_crc_override: int | None = None
        self.commit_complete = False

    def _status_payload(self) -> bytes:
        sequence = self.installed_sequence
        crc = self.installed_crc
        if self.commit_complete and self.post_sequence_override is not None:
            sequence = self.post_sequence_override
        if self.commit_complete and self.post_crc_override is not None:
            crc = self.post_crc_override
        pending_sequence = 0
        if self.pending_blob is not None:
            pending_sequence = struct.unpack_from("<I", self.pending_blob, 8)[0]
        return (
            bytes([0])
            + self.mac
            + struct.pack("<I", self.boot_nonce)
            + bytes(
                [
                    1 if self.maintenance else 0,
                    1 if self.inhibit else 0,
                    1 if self.store_ready else 0,
                    1 if self.has_active else 0,
                ]
            )
            + struct.pack("<III", sequence, crc, pending_sequence)
        )

    def _respond(self, opcode: int, payload: bytes) -> None:
        self.rx.extend(encode_frame(opcode, payload))

    def _handle(self, opcode: int, payload: bytes) -> None:
        self.opcodes.append(opcode)
        if opcode == OP_QUERY_STATUS:
            self._respond(OP_STATUS_RESPONSE, self._status_payload())
            return
        if opcode == OP_PREPARE_RECORD:
            if self.prepare_status:
                self._respond(OP_PREPARE_RESPONSE, bytes([self.prepare_status]))
                return
            boot_nonce, floor = struct.unpack_from("<II", payload, 0)
            assert boot_nonce == self.boot_nonce
            assert floor == self.installed_sequence
            self.pending_blob = bytes(payload[8:56])
            sequence = struct.unpack_from("<I", self.pending_blob, 8)[0]
            crc = struct.unpack_from("<I", self.pending_blob, 44)[0]
            self._respond(
                OP_PREPARE_RESPONSE,
                bytes([0]) + struct.pack("<III", sequence, crc, self.commit_nonce),
            )
            return
        if opcode == OP_COMMIT_RECORD:
            if self.commit_status:
                self._respond(OP_COMMIT_RESPONSE, bytes([self.commit_status]))
                return
            boot_nonce, commit_nonce, sequence = struct.unpack("<III", payload)
            assert boot_nonce == self.boot_nonce
            if self.pending_blob is None or commit_nonce != self.commit_nonce:
                self._respond(OP_COMMIT_RESPONSE, bytes([7]))
                return
            pending_sequence = struct.unpack_from("<I", self.pending_blob, 8)[0]
            if sequence != pending_sequence:
                self._respond(OP_COMMIT_RESPONSE, bytes([7]))
                return
            self.installed_sequence = sequence
            self.installed_crc = struct.unpack_from("<I", self.pending_blob, 44)[0]
            self.pending_blob = None
            self.commit_complete = True
            self._respond(
                OP_COMMIT_RESPONSE,
                bytes([0]) + struct.pack("<II", self.installed_sequence, self.installed_crc),
            )
            return
        raise AssertionError(f"unexpected opcode {opcode}")

    def write(self, data: bytes) -> int:
        for frame in self.parser.feed(data):
            self._handle(frame.opcode, frame.payload)
        return len(data)

    def read(self, size: int = 1) -> bytes:
        if not self.rx:
            return b""
        count = min(size, len(self.rx))
        data = bytes(self.rx[:count])
        del self.rx[:count]
        return data


def test_frame_parser_handles_fragmentation_crc_corruption_and_resync() -> None:
    valid = encode_frame(OP_QUERY_STATUS, b"")
    corrupted = bytearray(encode_frame(OP_PREPARE_RECORD, b"1234"))
    corrupted[-1] ^= 0x80
    parser = FrameParser()
    frames = []
    frames += parser.feed(b"noise" + bytes(corrupted[:5]))
    frames += parser.feed(bytes(corrupted[5:]) + valid[:3])
    frames += parser.feed(valid[3:])
    assert len(frames) == 1
    assert frames[0].opcode == OP_QUERY_STATUS
    assert frames[0].payload == b""


def test_physical_provisioning_sends_exact_record_and_retains_evidence(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    transport = FakeMaintenanceTransport()
    client = MaintenanceClient(transport, timeout_s=0.05)
    report = apply_provisioning(client, bundle, operator="Test Operator")

    expected = (bundle / "calibration-record.bin").read_bytes()
    assert transport.opcodes == [OP_QUERY_STATUS, OP_PREPARE_RECORD, OP_COMMIT_RECORD, OP_QUERY_STATUS]
    assert report["commit_verified"] is True
    assert report["reboot_recovery_verified"] is False
    assert report["device"]["device_id"] == "esp32s3:aabbccddeeff"
    assert report["provisioning"]["candidate_sequence"] == 5
    assert report["observations"]["commit"]["installed_sequence"] == 5
    assert transport.installed_sequence == 5
    assert transport.installed_crc == struct.unpack_from("<I", expected, 44)[0]
    assert report["authority"]["may_relax_hard_safety_limits"] is False


def test_wrong_device_blocks_before_prepare(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path, device_id="esp32s3:001122334455")
    transport = FakeMaintenanceTransport()
    with pytest.raises(MaintenanceProvisioningError, match="device identity mismatch"):
        apply_provisioning(MaintenanceClient(transport, timeout_s=0.05), bundle, operator="Tester")
    assert transport.opcodes == [OP_QUERY_STATUS]


def test_open_physical_gate_blocks_before_prepare(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    transport = FakeMaintenanceTransport()
    transport.inhibit = False
    with pytest.raises(MaintenanceProvisioningError, match="physical maintenance"):
        apply_provisioning(MaintenanceClient(transport, timeout_s=0.05), bundle, operator="Tester")
    assert transport.opcodes == [OP_QUERY_STATUS]


def test_installed_sequence_mismatch_blocks_before_prepare(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path, installed=3)
    transport = FakeMaintenanceTransport()
    with pytest.raises(MaintenanceProvisioningError, match="installed sequence changed"):
        apply_provisioning(MaintenanceClient(transport, timeout_s=0.05), bundle, operator="Tester")
    assert transport.opcodes == [OP_QUERY_STATUS]


def test_prepare_rejection_blocks_commit(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    transport = FakeMaintenanceTransport()
    transport.prepare_status = 2
    with pytest.raises(MaintenanceProvisioningError, match="PHYSICAL_GATE_OPEN"):
        apply_provisioning(MaintenanceClient(transport, timeout_s=0.05), bundle, operator="Tester")
    assert transport.opcodes == [OP_QUERY_STATUS, OP_PREPARE_RECORD]


def test_commit_requires_matching_challenge() -> None:
    transport = FakeMaintenanceTransport()
    client = MaintenanceClient(transport, timeout_s=0.05)
    status = client.query_status()
    prepared = client.prepare_record(
        boot_nonce=status.boot_nonce,
        expected_floor=status.installed_sequence,
        record_blob=make_record(5),
    )
    assert prepared.commit_nonce == transport.commit_nonce
    with pytest.raises(MaintenanceProvisioningError, match="PENDING_MISMATCH"):
        client.commit_record(
            boot_nonce=status.boot_nonce,
            commit_nonce=prepared.commit_nonce ^ 1,
            sequence=5,
        )


def test_post_write_readback_mismatch_fails(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    transport = FakeMaintenanceTransport()
    transport.post_sequence_override = 99
    with pytest.raises(MaintenanceProvisioningError, match="post-write status"):
        apply_provisioning(MaintenanceClient(transport, timeout_s=0.05), bundle, operator="Tester")


def _successful_report(tmp_path: Path) -> tuple[dict, FakeMaintenanceTransport]:
    bundle = make_bundle(tmp_path)
    transport = FakeMaintenanceTransport()
    report = apply_provisioning(
        MaintenanceClient(transport, timeout_s=0.05),
        bundle,
        operator="Tester",
    )
    return report, transport


def test_reboot_verification_requires_new_boot_and_retained_record(tmp_path: Path) -> None:
    report, transport = _successful_report(tmp_path)
    transport.boot_nonce = 0x87654321
    verified = verify_reboot_recovery(MaintenanceClient(transport, timeout_s=0.05), report)
    assert verified["reboot_recovery_verified"] is True
    assert verified["reboot_verification"]["boot_nonce_changed"] is True
    assert verified["reboot_verification"]["sequence_match"] is True
    assert verified["reboot_verification"]["crc_match"] is True


def test_reboot_verification_rejects_same_boot(tmp_path: Path) -> None:
    report, transport = _successful_report(tmp_path)
    with pytest.raises(MaintenanceProvisioningError, match="boot nonce did not change"):
        verify_reboot_recovery(MaintenanceClient(transport, timeout_s=0.05), report)


def test_reboot_verification_rejects_wrong_recovered_record(tmp_path: Path) -> None:
    report, transport = _successful_report(tmp_path)
    transport.boot_nonce = 0x87654321
    transport.installed_sequence = 6
    with pytest.raises(MaintenanceProvisioningError, match="recovered calibration record differs"):
        verify_reboot_recovery(MaintenanceClient(transport, timeout_s=0.05), report)
