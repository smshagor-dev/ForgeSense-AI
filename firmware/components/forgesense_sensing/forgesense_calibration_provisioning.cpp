#include "forgesense_calibration_provisioning.h"

#include <array>
#include <cstring>

namespace forgesense::sensing {
namespace {

struct DecodedSlot {
    bool present{false};
    bool valid{false};
    CalibrationRecord record{};
};

DecodedSlot decode_slot(const CalibrationSlotView& slot) {
    DecodedSlot out{};
    out.present = slot.present;
    if (!slot.present) {
        return out;
    }
    if (slot.data == nullptr || slot.size != kCalibrationBlobSize) {
        return out;
    }
    out.valid = decode_calibration_record(slot.data, slot.size, out.record);
    return out;
}

bool same_blob(const CalibrationSlotView& a, const CalibrationSlotView& b) {
    return a.present && b.present && a.data != nullptr && b.data != nullptr &&
           a.size == kCalibrationBlobSize && b.size == kCalibrationBlobSize &&
           std::memcmp(a.data, b.data, kCalibrationBlobSize) == 0;
}

}  // namespace

bool calibration_sequence_is_newer(
    std::uint32_t candidate,
    std::uint32_t installed_floor) {
    return candidate != 0U && candidate > installed_floor;
}

CalibrationSelection select_calibration_slot(
    const CalibrationSlotView& slot0,
    const CalibrationSlotView& slot1,
    std::uint32_t installed_floor) {
    const DecodedSlot decoded0 = decode_slot(slot0);
    const DecodedSlot decoded1 = decode_slot(slot1);

    if ((decoded0.present && !decoded0.valid) ||
        (decoded1.present && !decoded1.valid)) {
        return {CalibrationSelectionStatus::Corrupt, 0, {}};
    }

    if (!decoded0.valid && !decoded1.valid) {
        return installed_floor == 0U
                   ? CalibrationSelection{CalibrationSelectionStatus::Empty, 0, {}}
                   : CalibrationSelection{CalibrationSelectionStatus::RollbackDetected, 0, {}};
    }

    if (decoded0.valid && decoded1.valid &&
        decoded0.record.sequence == decoded1.record.sequence &&
        !same_blob(slot0, slot1)) {
        return {CalibrationSelectionStatus::Ambiguous, 0, {}};
    }

    std::uint8_t selected_slot = 0;
    CalibrationRecord selected = decoded0.record;
    if (!decoded0.valid ||
        (decoded1.valid && decoded1.record.sequence > decoded0.record.sequence)) {
        selected_slot = 1;
        selected = decoded1.record;
    }

    if (selected.sequence == 0U || selected.sequence < installed_floor) {
        return {CalibrationSelectionStatus::RollbackDetected, selected_slot, selected};
    }

    return {CalibrationSelectionStatus::Selected, selected_slot, selected};
}

}  // namespace forgesense::sensing
