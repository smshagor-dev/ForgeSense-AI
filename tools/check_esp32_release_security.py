from __future__ import annotations

import argparse
import json
from pathlib import Path

PROFILE_SCHEMA = "forgesense.esp32s3_release_security_profile.v1"


def parse_sdkconfig(path: Path) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# CONFIG_") and line.endswith(" is not set"):
            key = line[len("# ") : -len(" is not set")]
            values[key] = False
            continue
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            if value == "y":
                values[key] = True
            elif value == "n":
                values[key] = False
    return values


def validate_profile(profile: dict) -> None:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("unsupported ESP32-S3 release security profile schema")
    if profile.get("target") != "esp32s3":
        raise ValueError("release security profile target must be esp32s3")
    required_enabled = profile.get("required_enabled")
    required_disabled = profile.get("required_disabled")
    if not isinstance(required_enabled, list) or not required_enabled:
        raise ValueError("release security profile required_enabled is empty")
    if not isinstance(required_disabled, list) or not required_disabled:
        raise ValueError("release security profile required_disabled is empty")
    if set(required_enabled) & set(required_disabled):
        raise ValueError("a Kconfig symbol cannot be both required-enabled and required-disabled")
    signing = profile.get("signing")
    irreversible = profile.get("device_irreversible_actions")
    authority = profile.get("authority")
    if not isinstance(signing, dict) or signing.get("private_key_in_repository_permitted") is not False:
        raise ValueError("release security profile must prohibit repository private keys")
    if signing.get("private_key_in_firmware_image_permitted") is not False:
        raise ValueError("release security profile must prohibit firmware-image private keys")
    if not isinstance(irreversible, dict) or irreversible.get("operator_review_required") is not True:
        raise ValueError("irreversible security enablement must require operator review")
    for key in (
        "automatic_efuse_burn_by_repository_tools",
        "automatic_secure_boot_enable_by_repository_tools",
        "automatic_flash_encryption_enable_by_repository_tools",
    ):
        if irreversible.get(key) is not False:
            raise ValueError(f"repository security profile may not automatically perform {key}")
    if not isinstance(authority, dict) or authority.get("does_not_change_fpga_hard_safety") is not True:
        raise ValueError("release security profile must preserve FPGA hard-safety authority")
    if authority.get("physical_device_enablement_claimed") is not False:
        raise ValueError("release security profile may not claim physical enablement")


def validate_sdkconfig(profile: dict, sdkconfig: Path) -> None:
    values = parse_sdkconfig(sdkconfig)
    missing_enabled = [key for key in profile["required_enabled"] if values.get(key) is not True]
    enabled_forbidden = [key for key in profile["required_disabled"] if values.get(key) is True]
    if missing_enabled:
        raise ValueError("secure release sdkconfig missing enabled symbols: " + ", ".join(missing_enabled))
    if enabled_forbidden:
        raise ValueError("secure release sdkconfig enables forbidden symbols: " + ", ".join(enabled_forbidden))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ForgeSense ESP32-S3 production-release security policy")
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("firmware/security/esp32_s3_release_security_profile_v1.json"),
    )
    parser.add_argument("--sdkconfig", type=Path)
    args = parser.parse_args(argv)
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        if not isinstance(profile, dict):
            raise ValueError("release security profile must be a JSON object")
        validate_profile(profile)
        if args.sdkconfig is not None:
            validate_sdkconfig(profile, args.sdkconfig)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"esp32_release_security_check FAIL: {exc}")
        return 2
    print("esp32_release_security_check PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
