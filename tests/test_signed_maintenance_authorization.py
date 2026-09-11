from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zlib

import pytest

from commissioning.forgesense_commission.provisioning import (
    ARTIFACT_INDEX_SCHEMA,
    CommitResult,
    DeviceStatus,
    MaintenanceProvisioningError,
    PrepareResult,
    PROVISIONING_SCHEMA,
)
from commissioning.forgesense_commission.signed_provisioning import (
    AUTHORIZATION_DOMAIN,
    AUTHORIZATION_REQUEST_SCHEMA,
    AuthorizationStatus,
    VerifiedAuthorization,
    apply_signed_provisioning,
    authorization_payload,
    verify_authorization_bundle,
)
from tools.package_calibration_maintenance_authorization import build_authorization


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def make_record(sequence: int) -> bytes:
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
        1,
        2000,
        0,
    )
    return prefix + struct.pack("<I", zlib.crc32(prefix) & 0xFFFFFFFF)


def make_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "provisioning"
    root.mkdir()
    blob = make_record(5)
    package = {
        "schema": PROVISIONING_SCHEMA,
        "device_id": "esp32s3:aabbccddeeff",
        "sequence": {"installed": 4, "candidate": 5},
        "record": {
            "crc32_ieee": struct.unpack_from("<I", blob, 44)[0],
            "sha256": _sha256(blob),
        },
    }
    package_bytes = (json.dumps(package, indent=2) + "\n").encode()
    hex_bytes = (blob.hex() + "\n").encode("ascii")
    (root / "provisioning.json").write_bytes(package_bytes)
    (root / "calibration-record.bin").write_bytes(blob)
    (root / "calibration-record.hex").write_bytes(hex_bytes)
    index_core = {
        "schema": ARTIFACT_INDEX_SCHEMA,
        "artifacts": [
            {"path": "calibration-record.bin", "sha256": _sha256(blob)},
            {"path": "calibration-record.hex", "sha256": _sha256(hex_bytes)},
            {"path": "provisioning.json", "sha256": _sha256(package_bytes)},
        ],
    }
    index = dict(index_core)
    index["root_sha256"] = _canonical_sha256(index_core)
    (root / "artifact-index.json").write_text(json.dumps(index, indent=2) + "\n")
    return root


def generate_p256_keypair(tmp_path: Path) -> tuple[Path, Path]:
    if shutil.which("openssl") is None:
        pytest.skip("OpenSSL is required for external-signature regression")
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    subprocess.run(
        ["openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(private_key)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return private_key, public_key


def make_signed_authorization(tmp_path: Path, bundle: Path) -> tuple[Path, Path, bytes]:
    private_key, public_key = generate_p256_keypair(tmp_path)
    package = json.loads((bundle / "provisioning.json").read_text())
    index = json.loads((bundle / "artifact-index.json").read_text())
    blob = (bundle / "calibration-record.bin").read_bytes()
    payload = authorization_payload(
        device_id=package["device_id"],
        expected_installed_sequence=package["sequence"]["installed"],
        artifact_root_sha256=index["root_sha256"],
        record_blob=blob,
    )

    request_dir = tmp_path / "request"
    request_dir.mkdir()
    request = {
        "schema": AUTHORIZATION_REQUEST_SCHEMA,
        "signature_format": "ECDSA-P256-SHA256-DER",
        "device_id": package["device_id"],
        "expected_installed_sequence": package["sequence"]["installed"],
        "candidate_sequence": package["sequence"]["candidate"],
        "artifact_root_sha256": index["root_sha256"],
        "record_sha256": _sha256(blob),
        "payload_sha256": _sha256(payload),
    }
    (request_dir / "authorization-request.json").write_text(json.dumps(request, indent=2) + "\n")
    (request_dir / "authorization-payload.bin").write_bytes(payload)

    signature = tmp_path / "signature.der"
    subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-sign",
            str(private_key),
            "-out",
            str(signature),
            str(request_dir / "authorization-payload.bin"),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    artifacts = build_authorization(
        request_dir,
        signature_path=signature,
        public_key_path=public_key,
    )
    authorization_dir = tmp_path / "authorization"
    authorization_dir.mkdir()
    for name, content in artifacts.items():
        (authorization_dir / name).write_bytes(content)
    return authorization_dir, public_key, payload


def test_authorization_payload_binds_device_sequence_root_and_record() -> None:
    record = make_record(5)
    root = "11" * 32
    payload = authorization_payload(
        device_id="esp32s3:aabbccddeeff",
        expected_installed_sequence=4,
        artifact_root_sha256=root,
        record_blob=record,
    )
    assert payload.startswith(AUTHORIZATION_DOMAIN + bytes.fromhex("aabbccddeeff") + struct.pack("<I", 4))
    assert bytes.fromhex(root) in payload
    assert payload.endswith(record)


def test_valid_external_signature_packages_and_reverifies(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    authorization_dir, public_key, payload = make_signed_authorization(tmp_path, bundle)
    verified = verify_authorization_bundle(
        authorization_dir,
        provisioning_dir=bundle,
        public_key_path=public_key,
    )
    assert verified.payload_sha256 == _sha256(payload)
    assert len(verified.signature_der) > 0
    assert len(verified.artifact_root_sha256) == 32
    assert len(verified.public_key_sha256) == 64
    assert verified.package["authority"]["private_key_accessed_by_tool"] is False


def test_tampered_signature_is_rejected(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    authorization_dir, public_key, _ = make_signed_authorization(tmp_path, bundle)
    signature_path = authorization_dir / "authorization-signature.der"
    signature = bytearray(signature_path.read_bytes())
    signature[-1] ^= 0x01
    signature_path.write_bytes(signature)
    with pytest.raises(MaintenanceProvisioningError):
        verify_authorization_bundle(
            authorization_dir,
            provisioning_dir=bundle,
            public_key_path=public_key,
        )


class FakeSignedClient:
    def __init__(self, key_fingerprint: str) -> None:
        self.key_fingerprint = key_fingerprint
        self.record_blob: bytes | None = None
        self.prepare_calls = 0
        self.commit_calls = 0
        self.boot_nonce = 0x12345678
        self.installed_sequence = 4
        self.installed_crc = 0x11112222

    def query_status(self) -> DeviceStatus:
        return DeviceStatus(
            device_id="esp32s3:aabbccddeeff",
            mac_hex="aabbccddeeff",
            boot_nonce=self.boot_nonce,
            maintenance_asserted=True,
            load_inhibit_asserted=True,
            store_ready=True,
            has_active=True,
            installed_sequence=self.installed_sequence,
            installed_crc32=self.installed_crc,
            pending_sequence=0,
        )

    def query_authorization(self) -> AuthorizationStatus:
        return AuthorizationStatus(ready=True, public_key_sha256=self.key_fingerprint)

    def prepare_authorized_record(self, **kwargs) -> PrepareResult:
        self.prepare_calls += 1
        assert kwargs["boot_nonce"] == self.boot_nonce
        assert kwargs["expected_floor"] == 4
        assert len(kwargs["artifact_root_sha256"]) == 32
        assert kwargs["signature_der"] == b"signed"
        self.record_blob = bytes(kwargs["record_blob"])
        return PrepareResult(
            sequence=5,
            record_crc32=struct.unpack_from("<I", self.record_blob, 44)[0],
            commit_nonce=0xA1B2C3D4,
        )

    def commit_record(self, **kwargs) -> CommitResult:
        self.commit_calls += 1
        assert kwargs["boot_nonce"] == self.boot_nonce
        assert kwargs["commit_nonce"] == 0xA1B2C3D4
        assert kwargs["sequence"] == 5
        assert self.record_blob is not None
        self.installed_sequence = 5
        self.installed_crc = struct.unpack_from("<I", self.record_blob, 44)[0]
        return CommitResult(installed_sequence=5, installed_crc32=self.installed_crc)


def fake_authorization(bundle: Path, key_fingerprint: str = "22" * 32) -> VerifiedAuthorization:
    index = json.loads((bundle / "artifact-index.json").read_text())
    return VerifiedAuthorization(
        package={
            "schema": "forgesense.calibration_maintenance_authorization.v1",
            "signature_sha256": _sha256(b"signed"),
            "signature_format": "ECDSA-P256-SHA256-DER",
        },
        signature_der=b"signed",
        artifact_root_sha256=bytes.fromhex(index["root_sha256"]),
        public_key_sha256=key_fingerprint,
        payload_sha256="33" * 32,
    )


def test_signed_apply_rejects_device_signer_mismatch_before_prepare(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    client = FakeSignedClient("44" * 32)
    with pytest.raises(MaintenanceProvisioningError, match="pinned public key differs"):
        apply_signed_provisioning(
            client,  # type: ignore[arg-type]
            bundle,
            authorization=fake_authorization(bundle, "22" * 32),
            operator="Tester",
        )
    assert client.prepare_calls == 0
    assert client.commit_calls == 0


def test_signed_apply_binds_authorization_and_retains_crypto_evidence(tmp_path: Path) -> None:
    bundle = make_bundle(tmp_path)
    key = "22" * 32
    client = FakeSignedClient(key)
    report = apply_signed_provisioning(
        client,  # type: ignore[arg-type]
        bundle,
        authorization=fake_authorization(bundle, key),
        operator="Tester",
    )
    assert client.prepare_calls == 1
    assert client.commit_calls == 1
    assert report["commit_verified"] is True
    assert report["authorization"]["host_signature_verification"] is True
    assert report["authorization"]["device_signature_verification_confirmed_by_prepare"] is True
    assert report["authorization"]["authority_public_key_sha256"] == key
    assert report["authority"]["signed_authorization_required"] is True
    assert report["authority"]["may_relax_hard_safety_limits"] is False
