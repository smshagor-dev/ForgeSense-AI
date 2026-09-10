#pragma once

#include "forgesense_telemetry.h"

#include <cstdint>

namespace forgesense::edge {

class TelemetryPublisher {
public:
    void ingest_sensor(const ParsedSensorFrame& frame, std::uint32_t received_ms) {
        snapshot_.ingest_sensor(frame, received_ms);
    }
    void ingest_status(const ParsedStatusFrame& frame, std::uint32_t received_ms) {
        snapshot_.ingest_status(frame, received_ms);
    }
    void ingest_ml(
        const MlObservation& observation,
        std::uint16_t sequence,
        std::uint32_t source_timestamp_ms,
        std::uint32_t received_ms) {
        snapshot_.ingest_ml(
            observation, sequence, source_timestamp_ms, received_ms);
    }
    void set_link_counters(const TelemetryLinkCounters& counters) {
        snapshot_.set_link_counters(counters);
    }

    // Returns false only when an enabled telemetry record could not be encoded
    // or written completely. Disabled telemetry is treated as a successful no-op.
    bool maybe_publish(std::uint32_t now_ms, bool force = false);

private:
    DeviceTelemetrySnapshot snapshot_{};
    std::uint32_t last_publish_ms_{0};
    bool have_published_{false};
};

}  // namespace forgesense::edge
