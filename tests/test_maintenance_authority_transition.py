from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from commissioning.forgesense_commission import authority_transition as transition
from commissioning.forgesense_commission.audit_ledger import (
    CalibrationAuditLedgerError,
    append_authority_transition_evidence,
    initialize_ledger,
    verify_ledger,
)

AUDIT_POLICY = Path("hardware/calibration/calibration_audit_ledger_policy_v1.json")
TRANSITION_POLICY = Path("hardware/calibration/maintenance_authority_transition_policy_v1.json")
DEVICE_ID = "esp32s3:aabbccddeeff"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(*args: str) -> None:
    subprocess.run(list(args), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_key(root: Path, name: str) -> tuple[Path, Path]:
    private = root / f"{name}-private.pem"
    public = root / f"{name}-public.pem"
    run("openssl", "ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", str(private))
    run("openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public))
    return private, public


def sign(private: Path, payload: Path, output: Path) -> None:
    run(
        "openssl",
        "dgst",
        "-sha256",
        "-sign",
        str(private),
        "-out",
        str(output),
        str(payload),
    )


def prepare_source_tree(root: Path) -> None:
    for relative in transition._SOURCE_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"synthetic source for {relative}\n", encoding="utf-8")


def make_fixture(tmp_path: Path) -> dict:
    if shutil.which("openssl") is None:
        pytest.skip("OpenSSL is required for maintenance-authority transition tests")
    old_private, old_public = make_key(tmp_path, "old")
    new_private, new_public = make_key(tmp_path, "new")
    old_der = transition.public_key_der(old_public)
    new_der = transition.public_key_der(new_public)
    old_fp = hashlib.sha256(old_der).hexdigest()
    new_fp = hashlib.sha256(new_der).hexdigest()

    device_state = {
        "schema": "forgesense.calibration_device_state.v1",
        "device_id": DEVICE_ID,
        "installed_sequence": 0,
        "installed_record_crc32": None,
        "active_record_sha256": None,
        "active_record_hex": None,
        "maintenance_authorization_ready": True,
        "maintenance_authority_public_key_sha256": old_fp,
    }
    device_path = tmp_path / "device-state-before.json"
    write_json(device_path, device_state)
    ledger = tmp_path / "ledger"
    initialize_ledger(ledger, device_state_path=device_path, policy_path=AUDIT_POLICY)

    repo_root = tmp_path / "repo"
    prepare_source_tree(repo_root)
    sdkconfig = tmp_path / "sdkconfig"
    sdkconfig.write_text(
        f'CONFIG_FORGESENSE_MAINTENANCE_AUTHORITY_PUBKEY_DER_HEX="{new_der.hex()}"\n',
        encoding="utf-8",
    )
    image = tmp_path / "forgesense-maintenance.bin"
    image.write_bytes(b"synthetic-maintenance-image-v2")
    return {
        "old_private": old_private,
        "old_public": old_public,
        "new_private": new_private,
        "new_public": new_public,
        "old_fp": old_fp,
        "new_fp": new_fp,
        "device_path": device_path,
        "ledger": ledger,
        "repo_root": repo_root,
        "sdkconfig": sdkconfig,
        "image": image,
    }


def build_request(tmp_path: Path, fixture: dict) -> Path:
    artifacts = transition.build_transition_request(
        ledger_dir=fixture["ledger"],
        audit_policy_path=AUDIT_POLICY,
        device_state_path=fixture["device_path"],
        old_public_key_path=fixture["old_public"],
        new_public_key_path=fixture["new_public"],
        source_commit="a" * 40,
        repo_root=fixture["repo_root"],
        sdkconfig_path=fixture["sdkconfig"],
        maintenance_image_path=fixture["image"],
        transition_policy_path=TRANSITION_POLICY,
    )
    request_dir = tmp_path / "request"
    request_dir.mkdir()
    for name, data in artifacts.items():
        (request_dir / name).write_bytes(data)
    return request_dir


def package_request(tmp_path: Path, fixture: dict, request_dir: Path) -> Path:
    old_signature = tmp_path / "old-signature.der"
    new_signature = tmp_path / "new-signature.der"
    payload = request_dir / "transition-payload.bin"
    sign(fixture["old_private"], payload, old_signature)
    sign(fixture["new_private"], payload, new_signature)
    package_dir = tmp_path / "transition-package"
    transition.package_transition(
        request_dir,
        old_signature_path=old_signature,
        new_signature_path=new_signature,
        old_public_key_path=fixture["old_public"],
        new_public_key_path=fixture["new_public"],
        output_dir=package_dir,
    )
    return package_dir


def test_dual_signed_transition_updates_only_authority_fingerprint(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    request_dir = build_request(tmp_path, fixture)
    package_dir = package_request(tmp_path, fixture, request_dir)
    verified = transition.verify_transition_package(package_dir)
    assert verified.old_public_key_sha256 == fixture["old_fp"]
    assert verified.new_public_key_sha256 == fixture["new_fp"]

    post = {
        "schema": "forgesense.calibration_device_state.v1",
        "device_id": DEVICE_ID,
        "installed_sequence": 0,
        "installed_record_crc32": None,
        "active_record_sha256": None,
        "active_record_hex": None,
        "maintenance_authorization_ready": True,
        "maintenance_authority_public_key_sha256": fixture["new_fp"],
    }
    post_path = tmp_path / "device-state-after.json"
    write_json(post_path, post)
    state = append_authority_transition_evidence(
        fixture["ledger"],
        transition_package_dir=package_dir,
        post_device_state_path=post_path,
        policy_path=AUDIT_POLICY,
    )
    assert state.sequence == 0
    assert state.record_sha256 is None
    assert state.authority_public_key_sha256 == fixture["new_fp"]
    assert state.entry_count == 2
    assert verify_ledger(fixture["ledger"], policy_path=AUDIT_POLICY) == state


def test_sdkconfig_must_pin_exact_new_public_key(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    fixture["sdkconfig"].write_text(
        'CONFIG_FORGESENSE_MAINTENANCE_AUTHORITY_PUBKEY_DER_HEX="00"\n',
        encoding="utf-8",
    )
    with pytest.raises(transition.MaintenanceAuthorityTransitionError, match="does not equal"):
        build_request(tmp_path, fixture)


def test_same_key_transition_is_rejected(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    fixture["new_public"] = fixture["old_public"]
    with pytest.raises(transition.MaintenanceAuthorityTransitionError, match="must differ"):
        build_request(tmp_path, fixture)


def test_tampered_new_signature_is_rejected(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    request_dir = build_request(tmp_path, fixture)
    package_dir = package_request(tmp_path, fixture, request_dir)
    signature_path = package_dir / "new-authority-signature.der"
    signature = bytearray(signature_path.read_bytes())
    signature[-1] ^= 0x01
    signature_path.write_bytes(bytes(signature))
    with pytest.raises(transition.MaintenanceAuthorityTransitionError):
        transition.verify_transition_package(package_dir)


def test_post_install_calibration_state_change_is_rejected(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    request_dir = build_request(tmp_path, fixture)
    package_dir = package_request(tmp_path, fixture, request_dir)
    post_path = tmp_path / "device-state-after.json"
    write_json(
        post_path,
        {
            "device_id": DEVICE_ID,
            "installed_sequence": 1,
            "active_record_sha256": "9" * 64,
            "maintenance_authorization_ready": True,
            "maintenance_authority_public_key_sha256": fixture["new_fp"],
        },
    )
    with pytest.raises(CalibrationAuditLedgerError, match="calibration sequence"):
        append_authority_transition_evidence(
            fixture["ledger"],
            transition_package_dir=package_dir,
            post_device_state_path=post_path,
            policy_path=AUDIT_POLICY,
        )


def test_post_install_wrong_new_fingerprint_is_rejected(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    request_dir = build_request(tmp_path, fixture)
    package_dir = package_request(tmp_path, fixture, request_dir)
    post_path = tmp_path / "device-state-after.json"
    write_json(
        post_path,
        {
            "device_id": DEVICE_ID,
            "installed_sequence": 0,
            "active_record_sha256": None,
            "maintenance_authorization_ready": True,
            "maintenance_authority_public_key_sha256": "f" * 64,
        },
    )
    with pytest.raises(CalibrationAuditLedgerError, match="fingerprint differs"):
        append_authority_transition_evidence(
            fixture["ledger"],
            transition_package_dir=package_dir,
            post_device_state_path=post_path,
            policy_path=AUDIT_POLICY,
        )
