from __future__ import annotations

import json
from pathlib import Path

POLICY_SCHEMA = "forgesense.calibration_provisioning_policy.v1"


class SignedProvisioningPolicyError(ValueError):
    pass


def validate_signed_provisioning_policy(path: Path) -> dict:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SignedProvisioningPolicyError(f"signed provisioning policy not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SignedProvisioningPolicyError(f"signed provisioning policy is invalid JSON: {path}") from exc
    if not isinstance(policy, dict) or policy.get("schema") != POLICY_SCHEMA:
        raise SignedProvisioningPolicyError("unsupported signed provisioning policy schema")

    preconditions = policy.get("preconditions")
    authority = policy.get("authority")
    recovery = policy.get("recovery")
    if not all(isinstance(section, dict) for section in (preconditions, authority, recovery)):
        raise SignedProvisioningPolicyError("signed provisioning policy sections are incomplete")

    if preconditions.get("maintenance_mode_confirmation_required") is not True:
        raise SignedProvisioningPolicyError("maintenance-mode confirmation must be required")
    if preconditions.get("load_output_physically_inhibited_confirmation_required") is not True:
        raise SignedProvisioningPolicyError("load-output inhibit confirmation must be required")
    if preconditions.get("write_time_recheck_required") is not True:
        raise SignedProvisioningPolicyError("write-time safety recheck must be required")
    if preconditions.get("signed_maintenance_authorization_required_at_write_time") is not True:
        raise SignedProvisioningPolicyError("signed maintenance authorization must be required at write time")

    expected_authority = {
        "remote_provisioning_command_present": False,
        "automatic_provisioning": False,
        "cryptographic_authorization_required_for_write": True,
        "private_signing_key_on_device": False,
        "may_control_actuators": False,
        "may_relax_hard_safety_limits": False,
        "hardware_backed_monotonic_counter_claimed": False,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) is not expected:
            raise SignedProvisioningPolicyError(f"signed provisioning authority field {key} is invalid")

    expected_recovery = {
        "approved_profile_restoration_supported": True,
        "exact_active_record_readback_required": True,
        "candidate_sequence_increment_exactly_one": True,
        "sequence_decrement_permitted": False,
        "same_coefficients_noop_rejected": True,
        "signed_maintenance_authorization_required": True,
        "automatic_recovery": False,
    }
    for key, expected in expected_recovery.items():
        if recovery.get(key) is not expected:
            raise SignedProvisioningPolicyError(f"calibration recovery policy field {key} is invalid")
    return policy


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate signed ForgeSense calibration provisioning policy")
    parser.add_argument(
        "policy",
        nargs="?",
        type=Path,
        default=Path("hardware/calibration/calibration_provisioning_policy_v1.json"),
    )
    args = parser.parse_args()
    try:
        policy = validate_signed_provisioning_policy(args.policy)
    except SignedProvisioningPolicyError as exc:
        print(f"signed provisioning policy validation failed: {exc}")
        return 2
    print(
        "signed provisioning policy PASS: "
        f"policy_id={policy.get('policy_id')} signed_write=true monotonic_recovery=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
