#include "forgesense_phy.h"

#include <cstdint>

namespace forgesense::sensing {
namespace {

constexpr std::uint16_t bit(SensorDiagnostic d) {
    return static_cast<std::uint16_t>(d);
}

}  // namespace

SensorPhyReference::SensorPhyReference(std::uint16_t vibration_window_samples)
    : vibration_window_(vibration_window_samples) {}

void SensorPhyReference::set_calibration(const CalibrationRecord& record) {
    calibration_ = record;
    calibration_valid_ = calibration_is_usable(record.temperature) && calibration_is_usable(record.current);
    reset();
}

void SensorPhyReference::reset() {
    vibration_window_.reset();
}

NormalizedPhySnapshot SensorPhyReference::ingest(
    const RawScalarSample& temperature,
    const RawScalarSample& current,
    const ConditionedVibrationSample& vibration) {
    NormalizedPhySnapshot out{};
    if (!calibration_valid_) out.diagnostics |= bit(SensorDiagnostic::CalibrationInvalid);

    if (temperature.valid) {
        if (temperature.raw < kRaw24Min || temperature.raw > kRaw24Max) {
            out.diagnostics |= bit(SensorDiagnostic::RawRange);
        } else if (calibration_valid_) {
            const auto r = calibrate_to_i16(temperature.raw, calibration_.temperature);
            if (r.valid) {
                out.temperature_deci_c = r.value;
                out.temperature_update = true;
            }
            if (r.diagnostics & kDiagNumericSaturation) out.diagnostics |= bit(SensorDiagnostic::NumericSaturation);
        }
    } else {
        out.diagnostics |= bit(SensorDiagnostic::NoSample);
    }

    if (current.valid) {
        if (current.raw < kRaw24Min || current.raw > kRaw24Max) {
            out.diagnostics |= bit(SensorDiagnostic::RawRange);
        } else if (calibration_valid_) {
            const auto r = calibrate_to_i16(current.raw, calibration_.current);
            if (r.valid && r.value >= 0) {
                out.current_milli_a = static_cast<std::uint16_t>(r.value);
                out.current_update = true;
            } else if (r.valid) {
                out.diagnostics |= bit(SensorDiagnostic::RawRange);
            }
            if (r.diagnostics & kDiagNumericSaturation) out.diagnostics |= bit(SensorDiagnostic::NumericSaturation);
        }
    } else {
        out.diagnostics |= bit(SensorDiagnostic::NoSample);
    }

    if (vibration.valid) {
        std::uint16_t rms = 0;
        if (vibration_window_.ingest(vibration.milli_g, rms)) {
            out.vibration_milli_g_rms = rms;
            out.vibration_update = true;
        } else {
            out.diagnostics |= bit(SensorDiagnostic::VibrationWindowNotReady);
        }
    } else {
        out.diagnostics |= bit(SensorDiagnostic::NoSample);
    }
    return out;
}

}  // namespace forgesense::sensing
