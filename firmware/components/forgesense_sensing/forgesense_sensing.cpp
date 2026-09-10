#include "forgesense_sensing.h"

#include <limits>

namespace forgesense::sensing {

LinearCalibrationResult calibrate_to_i16(
    std::int32_t raw_value,
    const LinearCalibration& calibration) {
    LinearCalibrationResult result{};
    if (raw_value < kRaw24Min || raw_value > kRaw24Max) {
        result.diagnostics = kDiagRawOutOfRange;
        return result;
    }
    if (calibration.raw_zero < kRaw24Min || calibration.raw_zero > kRaw24Max ||
        calibration.gain_denominator <= 0) {
        result.diagnostics = kDiagBadCalibration;
        return result;
    }

    const std::int64_t centered =
        static_cast<std::int64_t>(raw_value) - calibration.raw_zero;
    const std::int64_t scaled =
        (centered * calibration.gain_numerator) /
            calibration.gain_denominator +
        calibration.output_offset;

    if (scaled < std::numeric_limits<std::int16_t>::min()) {
        result.value = std::numeric_limits<std::int16_t>::min();
        result.diagnostics = kDiagNumericSaturation;
    } else if (scaled > std::numeric_limits<std::int16_t>::max()) {
        result.value = std::numeric_limits<std::int16_t>::max();
        result.diagnostics = kDiagNumericSaturation;
    } else {
        result.value = static_cast<std::int16_t>(scaled);
    }
    result.valid = true;
    return result;
}

std::uint32_t integer_sqrt_u64(std::uint64_t value) {
    std::uint64_t result = 0;
    std::uint64_t bit = std::uint64_t{1} << 62;
    while (bit > value) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (value >= result + bit) {
            value -= result + bit;
            result = (result >> 1) + bit;
        } else {
            result >>= 1;
        }
        bit >>= 2;
    }
    return static_cast<std::uint32_t>(result);
}

VibrationRmsWindow::VibrationRmsWindow(std::uint16_t window_samples)
    : window_samples_(window_samples == 0 ? 1 : window_samples) {}

void VibrationRmsWindow::reset() {
    samples_collected_ = 0;
    sum_squares_ = 0;
}

bool VibrationRmsWindow::ingest(
    std::int16_t conditioned_milli_g,
    std::uint16_t& rms_milli_g) {
    const std::int64_t sample = conditioned_milli_g;
    const std::uint64_t square = static_cast<std::uint64_t>(sample * sample);
    sum_squares_ += square;
    ++samples_collected_;

    if (samples_collected_ < window_samples_) {
        return false;
    }

    const std::uint64_t mean_square = sum_squares_ / window_samples_;
    const std::uint32_t rms = integer_sqrt_u64(mean_square);
    rms_milli_g = static_cast<std::uint16_t>(
        rms > std::numeric_limits<std::uint16_t>::max()
            ? std::numeric_limits<std::uint16_t>::max()
            : rms);
    reset();
    return true;
}

}  // namespace forgesense::sensing
