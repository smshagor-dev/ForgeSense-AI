from __future__ import annotations

import argparse
import json
from pathlib import Path

ORDER = ("temperature", "vibration", "current")


def load(path: Path):
    data = json.loads(path.read_text())
    if data.get("schema") != "forgesense.sensor_contract.v1":
        raise ValueError("unsupported sensor contract schema")
    if data.get("contract_version") != 1:
        raise ValueError("unsupported sensor contract version")
    channels = data.get("channels")
    if not isinstance(channels, dict):
        raise ValueError("channels must be an object")
    for name in ORDER:
        item = channels.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"missing channel {name}")
        for key in ("minimum", "maximum", "stale_after_ms"):
            value = item.get(key)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name}.{key} must be integer")
        if item["minimum"] > item["maximum"]:
            raise ValueError(f"{name} range invalid")
        if item["stale_after_ms"] < 1:
            raise ValueError(f"{name} stale timeout invalid")
        if item.get("required") is not True:
            raise ValueError(f"{name} must remain required in v1")
    rate = data.get("export", {}).get("snapshot_rate_hz")
    if isinstance(rate, bool) or not isinstance(rate, int) or rate < 1:
        raise ValueError("snapshot_rate_hz invalid")
    return data


def cxx(data) -> str:
    c = data["channels"]
    return f'''#pragma once

#include <cstdint>

namespace forgesense::sensor_contract {{
inline constexpr std::uint16_t kVersion = 1;
inline constexpr std::int16_t kTemperatureMinDeciC = {c['temperature']['minimum']};
inline constexpr std::int16_t kTemperatureMaxDeciC = {c['temperature']['maximum']};
inline constexpr std::uint32_t kTemperatureStaleMs = {c['temperature']['stale_after_ms']}U;
inline constexpr std::uint16_t kVibrationMinMilliG = {c['vibration']['minimum']};
inline constexpr std::uint16_t kVibrationMaxMilliG = {c['vibration']['maximum']};
inline constexpr std::uint32_t kVibrationStaleMs = {c['vibration']['stale_after_ms']}U;
inline constexpr std::uint16_t kCurrentMinMilliA = {c['current']['minimum']};
inline constexpr std::uint16_t kCurrentMaxMilliA = {c['current']['maximum']};
inline constexpr std::uint32_t kCurrentStaleMs = {c['current']['stale_after_ms']}U;
inline constexpr std::uint16_t kSnapshotRateHz = {data['export']['snapshot_rate_hz']};
}}  // namespace forgesense::sensor_contract
'''


def vhdl(data) -> str:
    c = data["channels"]
    return f'''library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package sensor_contract_pkg is
    constant SENSOR_CONTRACT_VERSION : natural := 1;
    constant TEMP_MIN_DECI_C : integer := {c['temperature']['minimum']};
    constant TEMP_MAX_DECI_C : integer := {c['temperature']['maximum']};
    constant TEMP_STALE_MS : natural := {c['temperature']['stale_after_ms']};
    constant VIB_MIN_MILLI_G : natural := {c['vibration']['minimum']};
    constant VIB_MAX_MILLI_G : natural := {c['vibration']['maximum']};
    constant VIB_STALE_MS : natural := {c['vibration']['stale_after_ms']};
    constant CURRENT_MIN_MILLI_A : natural := {c['current']['minimum']};
    constant CURRENT_MAX_MILLI_A : natural := {c['current']['maximum']};
    constant CURRENT_STALE_MS : natural := {c['current']['stale_after_ms']};
    constant SENSOR_SNAPSHOT_RATE_HZ : natural := {data['export']['snapshot_rate_hz']};
end package;
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ForgeSense sensor-contract constants.")
    parser.add_argument("contract", type=Path)
    parser.add_argument("--cxx", type=Path, required=True)
    parser.add_argument("--vhdl", type=Path, required=True)
    args = parser.parse_args()
    data = load(args.contract)
    args.cxx.parent.mkdir(parents=True, exist_ok=True)
    args.vhdl.parent.mkdir(parents=True, exist_ok=True)
    args.cxx.write_text(cxx(data))
    args.vhdl.write_text(vhdl(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
