#pragma once

#include <cstddef>
#include <cstdint>

namespace forgesense::sensing {

inline constexpr std::uint16_t kDiagNone = 0x0000;
inline constexpr std::uint16_t kDiagBadCalibration = 0x0001;
inline constexpr std::uint16_t kDiagNumericSaturation = 0x0002;
inline constexpr std::uint16_t kDiagWindowNotReady = 0x0004;
inline constexpr std::uint16_t kDiagRawOutOfRange = 0x0008;
inline constexpr std::int32_t kRaw24Min = -8388608;
inline constexpr std::int32_t kRaw24Max = 8388607;

struct LinearCalibration {
    std::int32_t raw_zero{0};
    std::int32_t gain_numerator{1};
    std::int32_t gain_denominator{1};
    std::int32_t output_offset{0};
};

struct LinearCalibrationResult {
    std::int16_t value{0};
    std::uint16_t diagnostics{kDiagNone};
    bool valid{false};
};

LinearCalibrationResult calibrate_to_i16(
    std::int32_t raw_value,
    const LinearCalibration& calibration);

std::uint32_t integer_sqrt_u64(std::uint64_t value);

class VibrationRmsWindow {
public:
    explicit VibrationRmsWindow(std::uint16_t window_samples = 64);

    void reset();
    bool ingest(std::int16_t conditioned_milli_g, std::uint16_t& rms_milli_g);

    std::uint16_t window_samples() const { return window_samples_; }
    std::uint16_t samples_collected() const { return samples_collected_; }
    std::uint16_t diagnostics() const {
        return samples_collected_ == 0 ? kDiagWindowNotReady : kDiagNone;
    }

private:
    std::uint16_t window_samples_{64};
    std::uint16_t samples_collected_{0};
    std::uint64_t sum_squares_{0};
};

}  // namespace forgesense::sensing
