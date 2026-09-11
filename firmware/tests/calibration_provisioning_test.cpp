#include "forgesense_calibration_provisioning.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

namespace {

std::array<std::uint8_t, forgesense::sensing::kCalibrationBlobSize> make_blob(
    std::uint32_t sequence,
    std::int32_t current_num = 1,
    std::int32_t current_den = 2000) {
    using namespace forgesense::sensing;
    CalibrationRecord record{};
    record.sequence = sequence;
    record.temperature = {0, 1, 1, 2};
    record.current = {0, current_num, current_den, 0};
    std::array<std::uint8_t, kCalibrationBlobSize> blob{};
    assert(encode_calibration_record(record, blob));
    return blob;
}

}  // namespace

int main() {
    using namespace forgesense::sensing;

    assert(!calibration_sequence_is_newer(0, 0));
    assert(calibration_sequence_is_newer(1, 0));
    assert(!calibration_sequence_is_newer(4, 4));
    assert(!calibration_sequence_is_newer(3, 4));
    assert(calibration_sequence_is_newer(5, 4));
    assert(!calibration_sequence_is_newer(0xFFFFFFFFU, 4));

    const auto seq4 = make_blob(4);
    const auto seq5 = make_blob(5);
    CalibrationSlotView empty{};
    CalibrationSlotView view4{seq4.data(), seq4.size(), true};
    CalibrationSlotView view5{seq5.data(), seq5.size(), true};

    auto selected = select_calibration_slot(empty, empty, 0);
    assert(selected.status == CalibrationSelectionStatus::Empty);

    selected = select_calibration_slot(view4, view5, 4);
    assert(selected.status == CalibrationSelectionStatus::Selected);
    assert(selected.slot_index == 1);
    assert(selected.record.sequence == 5);

    selected = select_calibration_slot(view4, empty, 5);
    assert(selected.status == CalibrationSelectionStatus::RollbackDetected);

    auto corrupt = seq5;
    corrupt[20] ^= 0x55;
    CalibrationSlotView corrupt_view{corrupt.data(), corrupt.size(), true};
    selected = select_calibration_slot(view4, corrupt_view, 4);
    assert(selected.status == CalibrationSelectionStatus::Corrupt);

    const auto seq5_different = make_blob(5, 3, 4000);
    CalibrationSlotView seq5_alt{seq5_different.data(), seq5_different.size(), true};
    selected = select_calibration_slot(view5, seq5_alt, 5);
    assert(selected.status == CalibrationSelectionStatus::Ambiguous);

    selected = select_calibration_slot(view5, view5, 5);
    assert(selected.status == CalibrationSelectionStatus::Selected);
    assert(selected.record.sequence == 5);

    const auto terminal = make_blob(0xFFFFFFFFU);
    CalibrationSlotView terminal_view{terminal.data(), terminal.size(), true};
    selected = select_calibration_slot(terminal_view, empty, 4);
    assert(selected.status == CalibrationSelectionStatus::RollbackDetected);

    std::cout << "calibration_provisioning_test PASS\n";
    return 0;
}
