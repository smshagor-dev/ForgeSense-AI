#pragma once

#include <cstdint>

namespace forgesense::sensor_contract {
inline constexpr std::uint16_t kVersion = 1;
inline constexpr std::int16_t kTemperatureMinDeciC = -400;
inline constexpr std::int16_t kTemperatureMaxDeciC = 1250;
inline constexpr std::uint32_t kTemperatureStaleMs = 1000U;
inline constexpr std::uint16_t kVibrationMinMilliG = 0;
inline constexpr std::uint16_t kVibrationMaxMilliG = 16000;
inline constexpr std::uint32_t kVibrationStaleMs = 500U;
inline constexpr std::uint16_t kCurrentMinMilliA = 0;
inline constexpr std::uint16_t kCurrentMaxMilliA = 20000;
inline constexpr std::uint32_t kCurrentStaleMs = 500U;
inline constexpr std::uint16_t kSnapshotRateHz = 10;
}  // namespace forgesense::sensor_contract
