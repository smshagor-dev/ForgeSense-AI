#pragma once

#include "forgesense_calibration.h"

#include <cstddef>
#include <cstdint>

namespace forgesense::sensing {

struct CalibrationSlotView {
    const std::uint8_t* data{nullptr};
    std::size_t size{0};
    bool present{false};
};

enum class CalibrationSelectionStatus : std::uint8_t {
    Empty = 0,
    Selected = 1,
    Ambiguous = 2,
    RollbackDetected = 3,
    Corrupt = 4,
};

struct CalibrationSelection {
    CalibrationSelectionStatus status{CalibrationSelectionStatus::Empty};
    std::uint8_t slot_index{0};
    CalibrationRecord record{};
};

bool calibration_sequence_is_newer(std::uint32_t candidate, std::uint32_t installed_floor);

CalibrationSelection select_calibration_slot(
    const CalibrationSlotView& slot0,
    const CalibrationSlotView& slot1,
    std::uint32_t installed_floor);

}  // namespace forgesense::sensing
