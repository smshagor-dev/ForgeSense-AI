#pragma once

#include "forgesense_calibration.h"

#include <cstdint>

namespace forgesense::sensing {

enum class SensorDiagnostic : std::uint16_t {
    None = 0,
    NoSample = 1U << 0,
    RawRange = 1U << 1,
    CalibrationInvalid = 1U << 2,
    NumericSaturation = 1U << 3,
    VibrationWindowNotReady = 1U << 4,
    VibrationRange = 1U << 5,
};

struct RawScalarSample {
    std::int32_t raw{0};
    bool valid{false};
};

struct ConditionedVibrationSample {
    std::int16_t milli_g{0};
    bool valid{false};
};

struct NormalizedPhySnapshot {
    std::int16_t temperature_deci_c{0};
    std::uint16_t current_milli_a{0};
    std::uint16_t vibration_milli_g_rms{0};
    bool temperature_update{false};
    bool current_update{false};
    bool vibration_update{false};
    std::uint16_t diagnostics{0};
};

class SensorPhyReference {
public:
    explicit SensorPhyReference(std::uint16_t vibration_window_samples = 64);

    void set_calibration(const CalibrationRecord& record);
    void reset();

    NormalizedPhySnapshot ingest(
        const RawScalarSample& temperature,
        const RawScalarSample& current,
        const ConditionedVibrationSample& vibration);

private:
    CalibrationRecord calibration_{};
    bool calibration_valid_{false};
    VibrationRmsWindow vibration_window_;
};

}  // namespace forgesense::sensing
