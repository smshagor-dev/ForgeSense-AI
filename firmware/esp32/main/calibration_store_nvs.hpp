#pragma once

#include "forgesense_calibration.h"
#include "forgesense_calibration_provisioning.h"
#include "nvs.h"

#include <array>
#include <cstdint>

namespace forgesense::edge {

class CalibrationNvsStore {
public:
    CalibrationNvsStore() = default;
    ~CalibrationNvsStore();

    CalibrationNvsStore(const CalibrationNvsStore&) = delete;
    CalibrationNvsStore& operator=(const CalibrationNvsStore&) = delete;

    bool begin();
    bool load_active(sensing::CalibrationRecord& out) const;
    bool stage_and_commit(const sensing::CalibrationRecord& candidate);

    std::uint32_t installed_floor() const { return installed_floor_; }
    bool has_active() const { return has_active_; }
    std::uint8_t active_slot() const { return active_slot_; }

private:
    bool read_slot(std::uint8_t slot, std::array<std::uint8_t, sensing::kCalibrationBlobSize>& out, bool& present) const;
    bool write_metadata(std::uint8_t active_slot, std::uint32_t floor);

    nvs_handle_t handle_{0};
    std::uint32_t installed_floor_{0};
    std::uint8_t active_slot_{0};
    bool has_active_{false};
    bool opened_{false};
    sensing::CalibrationRecord active_record_{};
};

}  // namespace forgesense::edge
