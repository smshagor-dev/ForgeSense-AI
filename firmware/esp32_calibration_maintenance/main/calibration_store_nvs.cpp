#include "calibration_store_nvs.hpp"

#include "esp_err.h"

#include <algorithm>

namespace forgesense::maintenance {
namespace {

constexpr const char* kNamespace = "fs_cal";
constexpr const char* kSlotKeys[2] = {"slot0", "slot1"};
constexpr const char* kActiveKey = "active";
constexpr const char* kFloorKey = "floor";

}  // namespace

CalibrationNvsStore::~CalibrationNvsStore() {
    if (opened_) {
        nvs_close(handle_);
    }
}

void CalibrationNvsStore::reset_failed_open() {
    if (opened_) {
        nvs_close(handle_);
    }
    handle_ = 0;
    installed_floor_ = 0;
    active_slot_ = 0;
    has_active_ = false;
    opened_ = false;
    ready_ = false;
    active_record_ = {};
}

bool CalibrationNvsStore::read_slot(
    std::uint8_t slot,
    std::array<std::uint8_t, sensing::kCalibrationBlobSize>& out,
    bool& present) const {
    if (!opened_ || slot > 1U) {
        return false;
    }
    std::size_t size = out.size();
    const esp_err_t err = nvs_get_blob(handle_, kSlotKeys[slot], out.data(), &size);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        present = false;
        out.fill(0);
        return true;
    }
    if (err != ESP_OK || size != out.size()) {
        return false;
    }
    present = true;
    return true;
}

bool CalibrationNvsStore::write_metadata(std::uint8_t active_slot, std::uint32_t floor) {
    if (nvs_set_u8(handle_, kActiveKey, active_slot) != ESP_OK) {
        return false;
    }
    if (nvs_set_u32(handle_, kFloorKey, floor) != ESP_OK) {
        return false;
    }
    return nvs_commit(handle_) == ESP_OK;
}

bool CalibrationNvsStore::begin() {
    if (ready_) {
        return true;
    }
    if (opened_) {
        reset_failed_open();
    }
    if (nvs_open(kNamespace, NVS_READWRITE, &handle_) != ESP_OK) {
        return false;
    }
    opened_ = true;

    std::uint32_t stored_floor = 0;
    const esp_err_t floor_err = nvs_get_u32(handle_, kFloorKey, &stored_floor);
    if (floor_err != ESP_OK && floor_err != ESP_ERR_NVS_NOT_FOUND) {
        reset_failed_open();
        return false;
    }

    std::array<std::uint8_t, sensing::kCalibrationBlobSize> slot0{};
    std::array<std::uint8_t, sensing::kCalibrationBlobSize> slot1{};
    bool present0 = false;
    bool present1 = false;
    if (!read_slot(0, slot0, present0) || !read_slot(1, slot1, present1)) {
        reset_failed_open();
        return false;
    }

    const sensing::CalibrationSlotView view0{slot0.data(), slot0.size(), present0};
    const sensing::CalibrationSlotView view1{slot1.data(), slot1.size(), present1};
    const sensing::CalibrationSelection selected =
        sensing::select_calibration_slot(view0, view1, stored_floor);

    if (selected.status == sensing::CalibrationSelectionStatus::Empty) {
        installed_floor_ = 0;
        has_active_ = false;
        ready_ = true;
        return true;
    }
    if (selected.status != sensing::CalibrationSelectionStatus::Selected) {
        reset_failed_open();
        return false;
    }

    installed_floor_ = std::max(stored_floor, selected.record.sequence);
    active_slot_ = selected.slot_index;
    active_record_ = selected.record;
    has_active_ = true;

    std::uint8_t stored_active = 0;
    const esp_err_t active_err = nvs_get_u8(handle_, kActiveKey, &stored_active);
    const bool metadata_needs_repair =
        active_err != ESP_OK || stored_active != active_slot_ || stored_floor != installed_floor_;
    if (metadata_needs_repair && !write_metadata(active_slot_, installed_floor_)) {
        reset_failed_open();
        return false;
    }
    ready_ = true;
    return true;
}

bool CalibrationNvsStore::load_active(sensing::CalibrationRecord& out) const {
    if (!ready_ || !has_active_) {
        return false;
    }
    out = active_record_;
    return true;
}

bool CalibrationNvsStore::stage_and_commit(const sensing::CalibrationRecord& candidate) {
    if (!ready_ || !sensing::calibration_sequence_is_newer(candidate.sequence, installed_floor_)) {
        return false;
    }
    if (!sensing::calibration_is_usable(candidate.temperature) ||
        !sensing::calibration_is_usable(candidate.current)) {
        return false;
    }

    std::array<std::uint8_t, sensing::kCalibrationBlobSize> encoded{};
    if (!sensing::encode_calibration_record(candidate, encoded)) {
        return false;
    }

    const std::uint8_t inactive_slot = has_active_ ? static_cast<std::uint8_t>(1U - active_slot_) : 0U;
    if (nvs_set_blob(handle_, kSlotKeys[inactive_slot], encoded.data(), encoded.size()) != ESP_OK) {
        return false;
    }
    if (nvs_commit(handle_) != ESP_OK) {
        return false;
    }

    std::array<std::uint8_t, sensing::kCalibrationBlobSize> readback{};
    bool present = false;
    if (!read_slot(inactive_slot, readback, present) || !present || readback != encoded) {
        return false;
    }
    sensing::CalibrationRecord decoded{};
    if (!sensing::decode_calibration_record(readback.data(), readback.size(), decoded) ||
        decoded.sequence != candidate.sequence) {
        return false;
    }

    if (!write_metadata(inactive_slot, candidate.sequence)) {
        return false;
    }

    active_slot_ = inactive_slot;
    active_record_ = decoded;
    installed_floor_ = decoded.sequence;
    has_active_ = true;
    return true;
}

}  // namespace forgesense::maintenance
