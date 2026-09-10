#pragma once

#include <array>
#include <cstdint>

namespace forgesense::generated {

inline constexpr std::uint16_t kModelId = 1;
inline constexpr std::uint16_t kModelVersion = 1;
inline constexpr std::uint16_t kFeatureSchemaVersion = 1;
inline constexpr std::array<float, 3> kMean = {28.4468406F, 0.137552385F, 1.4566953F};
inline constexpr std::array<float, 3> kScale = {1.46704515F, 0.0106640075F, 0.127177009F};
inline constexpr float kWarningThreshold = 0.72F;
inline constexpr float kCriticalThreshold = 0.9F;

}  // namespace forgesense::generated
