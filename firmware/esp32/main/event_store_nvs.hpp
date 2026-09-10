#pragma once

#include "forgesense_events.h"
#include "nvs.h"

#include <cstdint>

namespace forgesense::edge {

class NvsEventStore {
public:
    NvsEventStore() = default;
    ~NvsEventStore();

    NvsEventStore(const NvsEventStore&) = delete;
    NvsEventStore& operator=(const NvsEventStore&) = delete;

    bool begin();
    bool append(EventRecord record);
    std::uint32_t next_sequence() const { return next_sequence_; }

private:
    nvs_handle_t handle_{0};
    std::uint32_t next_sequence_{0};
    bool opened_{false};
};

}  // namespace forgesense::edge
