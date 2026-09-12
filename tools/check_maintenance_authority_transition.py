from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    core = (root / "commissioning/forgesense_commission/authority_transition.py").read_text(encoding="utf-8")
    ledger = (root / "commissioning/forgesense_commission/audit_ledger.py").read_text(encoding="utf-8")
    prepare = (root / "tools/prepare_maintenance_authority_transition.py").read_text(encoding="utf-8")
    package = (root / "tools/package_maintenance_authority_transition.py").read_text(encoding="utf-8")
    manager = (root / "tools/manage_calibration_audit_ledger.py").read_text(encoding="utf-8")
    tests = (root / "tests/test_maintenance_authority_transition.py").read_text(encoding="utf-8")
    protocol = (root / "firmware/esp32_calibration_maintenance/main/maintenance_protocol.hpp").read_text(encoding="utf-8")
    production = (root / "firmware/esp32/main/app_main.cpp").read_text(encoding="utf-8")
    bridge = (root / "firmware/esp32_commissioning/main/app_main.cpp").read_text(encoding="utf-8")
    transition_policy = json.loads(
        (root / "hardware/calibration/maintenance_authority_transition_policy_v1.json").read_text(encoding="utf-8")
    )
    authority_policy = json.loads(
        (root / "hardware/calibration/maintenance_authority_policy_v1.json").read_text(encoding="utf-8")
    )

    for token in (
        'TRANSITION_DOMAIN = b"ForgeSense-Maintenance-Authority-Transition-v1\\n"',
        'TRANSITION_REQUEST_SCHEMA = "forgesense.maintenance_authority_transition_request.v1"',
        'TRANSITION_SCHEMA = "forgesense.maintenance_authority_transition.v1"',
        'SIGNATURE_FORMAT = "ECDSA-P256-SHA256-DER"',
        "build_transition_request",
        "transition_payload",
        "package_transition",
        "verify_transition_package",
        "verify_signature_openssl",
        "sdkconfig maintenance authority pin does not equal the new public key",
        "new maintenance authority public key must differ from old key",
        '"private_key_accessed_by_tool": False',
        '"may_write_firmware": False',
    ):
        assert token in core, token
    for forbidden in (
        "--private-key",
        "BEGIN PRIVATE KEY",
        "BEGIN EC PRIVATE KEY",
        '"-sign"',
        "esptool",
        "write_flash",
    ):
        assert forbidden not in core, forbidden
        assert forbidden not in prepare, forbidden
        assert forbidden not in package, forbidden

    for token in (
        'event_type == "authority_transition"',
        "authority transition may not mutate calibration state",
        "dual-signature verification",
        "append_authority_transition_evidence",
        "post-transition device fingerprint differs from dual-signed new authority",
        '"firmware_install_performed_by_transition_tool": False',
    ):
        assert token in ledger, token
    assert '"append-authority-transition"' in manager
    assert "append_authority_transition_evidence(" in manager

    assert transition_policy["signatures"]["old_authority_signature_required"] is True
    assert transition_policy["signatures"]["new_authority_proof_of_possession_required"] is True
    assert transition_policy["signatures"]["same_payload_required"] is True
    assert transition_policy["signatures"]["private_key_loaded_by_forgesense_tooling"] is False
    assert transition_policy["binding"]["sdkconfig_must_pin_new_public_key"] is True
    assert transition_policy["binding"]["maintenance_image_sha256_required"] is True
    assert transition_policy["installation"]["runtime_key_update_supported"] is False
    assert transition_policy["installation"]["remote_key_update_supported"] is False
    assert transition_policy["installation"]["calibration_protocol_key_update_supported"] is False
    assert transition_policy["installation"]["firmware_install_performed_by_forgesense_transition_tool"] is False
    assert transition_policy["audit"]["sequence_change_permitted"] is False
    assert transition_policy["audit"]["record_change_permitted"] is False
    assert transition_policy["audit"]["silent_authority_adoption_permitted"] is False
    assert transition_policy["authority"]["may_write_firmware"] is False
    assert transition_policy["authority"]["may_control_actuators"] is False
    assert transition_policy["authority"]["may_relax_hard_safety_limits"] is False

    rotation = authority_policy["rotation"]
    assert rotation["rotation_requires_dual_signed_transition_evidence"] is True
    assert rotation["old_authority_signature_required"] is True
    assert rotation["new_authority_proof_of_possession_required"] is True
    assert rotation["audit_transition_event_required"] is True
    assert rotation["calibration_state_must_remain_unchanged"] is True
    assert rotation["runtime_key_update_supported"] is False
    assert rotation["remote_key_update_supported"] is False
    assert rotation["normal_calibration_write_may_rotate_key"] is False

    for forbidden in (
        "RotateAuthorityKey",
        "UpdateAuthorityKey",
        "SetAuthorityKey",
        "WriteAuthorityKey",
        "AuthorityTransition",
    ):
        assert forbidden not in protocol, forbidden
    for forbidden in (
        "authority_transition",
        "rotate_authority_key",
        "set_authority_key",
        "update_authority_key",
    ):
        assert forbidden not in production.lower(), forbidden
        assert forbidden not in bridge.lower(), forbidden

    for token in (
        "test_dual_signed_transition_updates_only_authority_fingerprint",
        "test_sdkconfig_must_pin_exact_new_public_key",
        "test_same_key_transition_is_rejected",
        "test_tampered_new_signature_is_rejected",
        "test_post_install_calibration_state_change_is_rejected",
        "test_post_install_wrong_new_fingerprint_is_rejected",
    ):
        assert token in tests, token

    print(
        "maintenance_authority_transition_check PASS: dual old/new P-256 signatures, rebuilt-image/source/config "
        "binding, unchanged calibration state, explicit audit continuity, no private-key access, no firmware-writing "
        "authority, and no runtime/remote key-update path are present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
