#include "event_store_nvs.hpp"

#include "esp_err.h"
#include "sdkconfig.h"

#include <cstdio>

namespace forgesense::edge {

NvsEventStore::~NvsEventStore() {
    if (opened_) {
        nvs_close(handle_);
    }
}

bool NvsEventStore::begin() {
    if (nvs_open("fs_events", NVS_READWRITE, &handle_) != ESP_OK) {
        return false;
    }
    opened_ = true;

    std::uint32_t stored_next = 0;
    const esp_err_t err = nvs_get_u32(handle_, "next", &stored_next);
    if (err == ESP_OK) {
        next_sequence_ = stored_next;
        return true;
    }
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        next_sequence_ = 0;
        return true;
    }
    return false;
}

bool NvsEventStore::append(EventRecord record) {
    if (!opened_) {
        return false;
    }

    record.sequence = next_sequence_;
    const auto encoded = encode_event_record(record);
    const std::uint32_t slot =
        next_sequence_ % CONFIG_FORGESENSE_EVENT_RING_SIZE;

    char key[8]{};
    std::snprintf(key, sizeof(key), "e%03lu", static_cast<unsigned long>(slot));

    if (nvs_set_blob(handle_, key, encoded.data(), encoded.size()) != ESP_OK) {
        return false;
    }
    const std::uint32_t new_next = next_sequence_ + 1U;
    if (nvs_set_u32(handle_, "next", new_next) != ESP_OK) {
        return false;
    }
    if (nvs_commit(handle_) != ESP_OK) {
        return false;
    }
    next_sequence_ = new_next;
    return true;
}

}  // namespace forgesense::edge
