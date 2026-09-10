#pragma once

#include "forgesense_sensing.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense::sensing {

inline constexpr std::uint32_t kCalibrationMagic = 0x46534331U; // FSC1
inline constexpr std::uint16_t kCalibrationVersion = 1;
inline constexpr std::size_t kCalibrationBlobSize = 48;

enum class CalibrationChannel : std::uint8_t {
    Temperature = 0,
    Current = 1,
};

struct CalibrationRecord {
    std::uint32_t sequence{0};
    LinearCalibration temperature{};
    LinearCalibration current{};
};

std::uint32_t crc32_ieee(const std::uint8_t* data, std::size_t size);

bool encode_calibration_record(
    const CalibrationRecord& record,
    std::array<std::uint8_t, kCalibrationBlobSize>& out);

bool decode_calibration_record(
    const std::uint8_t* data,
    std::size_t size,
    CalibrationRecord& out);

bool calibration_is_usable(const LinearCalibration& calibration);

}  // namespace forgesense::sensing
