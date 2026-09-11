from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    protocol_h = (root / "firmware/esp32_calibration_maintenance/main/maintenance_protocol.hpp").read_text(encoding="utf-8")
    auth_h = (root / "firmware/esp32_calibration_maintenance/main/maintenance_authorization.hpp").read_text(encoding="utf-8")
    auth_cpp = (root / "firmware/esp32_calibration_maintenance/main/maintenance_authorization.cpp").read_text(encoding="utf-8")
    app = (root / "firmware/esp32_calibration_maintenance/main/app_main.cpp").read_text(encoding="utf-8")
    kconfig = (root / "firmware/esp32_calibration_maintenance/main/Kconfig.projbuild").read_text(encoding="utf-8")
    cmake = (root / "firmware/esp32_calibration_maintenance/main/CMakeLists.txt").read_text(encoding="utf-8")
    host = (root / "commissioning/forgesense_commission/signed_provisioning.py").read_text(encoding="utf-8")
    request_tool = (root / "tools/prepare_calibration_maintenance_authorization.py").read_text(encoding="utf-8")
    package_tool = (root / "tools/package_calibration_maintenance_authorization.py").read_text(encoding="utf-8")
    physical_tool = (root / "tools/run_physical_calibration_provisioning.py").read_text(encoding="utf-8")
    tests = (root / "tests/test_signed_maintenance_authorization.py").read_text(encoding="utf-8")
    production_app = (root / "firmware/esp32/main/app_main.cpp").read_text(encoding="utf-8")
    transparent_bridge = (root / "firmware/esp32_commissioning/main/app_main.cpp").read_text(encoding="utf-8")
    policy = json.loads(
        (root / "hardware/calibration/calibration_provisioning_policy_v1.json").read_text(encoding="utf-8")
    )

    for token in (
        "kMaintenanceMaxPayload = 192",
        "QueryAuthorization = 0x04",
        "AuthorizationResponse = 0x84",
        "AuthorizationFailed = 10",
        "AuthorizationUnavailable = 11",
    ):
        assert token in protocol_h, token

    for token in (
        "ForgeSense-Calibration-Maintenance-Authorization-v1",
        "kAuthorizationMaxSignatureSize = 80",
        "MaintenanceAuthorizationVerifier",
    ):
        assert token in auth_h, token

    for token in (
        "kPrime256v1Oid",
        "contains_prime256v1_oid",
        "mbedtls_pk_parse_public_key",
        "mbedtls_pk_verify",
        "MBEDTLS_MD_SHA256",
        "mbedtls_pk_get_bitlen(&key) == 256U",
        "public_key_sha256_",
    ):
        assert token in auth_cpp, token
    for forbidden in (
        "mbedtls_pk_parse_key(",
        "BEGIN PRIVATE KEY",
        "BEGIN EC PRIVATE KEY",
    ):
        assert forbidden not in auth_cpp, forbidden

    assert 'default ""' in kconfig
    assert "FORGESENSE_MAINTENANCE_AUTHORITY_PUBKEY_DER_HEX" in kconfig
    assert kconfig.count("default -1") >= 2
    assert '"maintenance_authorization.cpp"' in cmake
    assert "mbedtls" in cmake

    for token in (
        "handle_query_authorization",
        "g_authorization.ready()",
        "g_authorization.verify(",
        "MaintenanceStatus::AuthorizationFailed",
        "MaintenanceStatus::AuthorizationUnavailable",
        "frame.payload.data() + 40U",
        "frame.payload.data() + 88U",
        "clear_pending();",
    ):
        assert token in app, token
    verify_position = app.index("g_authorization.verify(")
    pending_position = app.index("g_pending_valid = true")
    assert verify_position < pending_position

    assert policy["preconditions"]["signed_maintenance_authorization_required_at_write_time"] is True
    assert policy["authority"]["cryptographic_authorization_required_for_write"] is True
    assert policy["authority"]["private_signing_key_on_device"] is False
    assert policy["authority"]["may_control_actuators"] is False
    assert policy["authority"]["may_relax_hard_safety_limits"] is False

    for token in (
        'AUTHORIZATION_DOMAIN = b"ForgeSense-Calibration-Maintenance-Authorization-v1\\n"',
        '"ECDSA-P256-SHA256-DER"',
        '"prime256v1"',
        '"P-256"',
        '"dgst"',
        '"-verify"',
        "verify_authorization_bundle",
        "query_authorization",
        "prepare_authorized_record",
        "device_signature_verification_confirmed_by_prepare",
    ):
        assert token in host, token
    assert '"-sign"' not in host

    for text in (request_tool, package_tool):
        assert "--private-key" not in text
        assert "BEGIN PRIVATE KEY" not in text
        assert "BEGIN EC PRIVATE KEY" not in text
        assert '"-sign"' not in text
    assert "verify_provisioning_bundle(" in request_tool
    assert "verify_signature_openssl(" in package_tool
    assert '"private_key_accessed_by_tool": False' in request_tool
    assert '"private_key_accessed_by_tool": False' in package_tool

    assert "apply_signed_provisioning" in physical_tool
    assert "verify_authorization_bundle(" in physical_tool
    assert "--authorization-dir" in physical_tool
    assert "--authority-public-key" in physical_tool
    auth_verify_position = physical_tool.index("authorization = verify_authorization_bundle(")
    serial_position = physical_tool.index("serial_port = _serial_port", auth_verify_position)
    assert auth_verify_position < serial_position
    assert "apply_provisioning(" not in physical_tool

    for forbidden in (
        "maintenance_authorization",
        "AuthorizationFailed",
        "AUTHORIZATION_DOMAIN",
        "prepare_authorized_record",
    ):
        assert forbidden not in production_app
        assert forbidden not in transparent_bridge

    for token in (
        "test_valid_external_signature_packages_and_reverifies",
        "test_tampered_signature_is_rejected",
        "test_signed_apply_rejects_device_signer_mismatch_before_prepare",
        "test_signed_apply_binds_authorization_and_retains_crypto_evidence",
    ):
        assert token in tests, token

    print(
        "signed_maintenance_authorization_check PASS: exact prime256v1 pinned-key verification, external detached "
        "signing, device/sequence/artifact/record binding, signed-only physical apply, and production safety "
        "separation are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
