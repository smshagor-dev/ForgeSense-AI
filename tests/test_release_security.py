from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.check_esp32_release_security import parse_sdkconfig, validate_profile, validate_sdkconfig


def load_profile() -> dict:
    return json.loads(
        Path("firmware/security/esp32_s3_release_security_profile_v1.json").read_text(encoding="utf-8")
    )


def test_release_security_profile_is_fail_closed() -> None:
    profile = load_profile()
    validate_profile(profile)
    assert "CONFIG_SECURE_BOOT_V2_ENABLED" in profile["required_enabled"]
    assert "CONFIG_SECURE_FLASH_ENCRYPTION_MODE_RELEASE" in profile["required_enabled"]
    assert "CONFIG_SECURE_BOOT_ALLOW_JTAG" in profile["required_disabled"]
    assert profile["signing"]["private_key_in_repository_permitted"] is False
    assert profile["device_irreversible_actions"]["operator_review_required"] is True


def test_sdkconfig_validation_accepts_required_secure_profile(tmp_path: Path) -> None:
    profile = load_profile()
    lines = [f"{key}=y" for key in profile["required_enabled"]]
    lines += [f"# {key} is not set" for key in profile["required_disabled"]]
    sdkconfig = tmp_path / "sdkconfig"
    sdkconfig.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert parse_sdkconfig(sdkconfig)
    validate_sdkconfig(profile, sdkconfig)


def test_sdkconfig_validation_rejects_insecure_jtag(tmp_path: Path) -> None:
    profile = load_profile()
    lines = [f"{key}=y" for key in profile["required_enabled"]]
    lines += [f"# {key} is not set" for key in profile["required_disabled"]]
    lines.append("CONFIG_SECURE_BOOT_ALLOW_JTAG=y")
    sdkconfig = tmp_path / "sdkconfig"
    sdkconfig.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden"):
        validate_sdkconfig(profile, sdkconfig)
