#pragma once

#include "forgesense_protocol.h"

#include <cstddef>
#include <cstdint>

namespace forgesense {

inline constexpr char kDeviceTelemetrySchema[] = "forgesense.edge.telemetry.v1";
inline constexpr char kDeviceTelemetryPrefix[] = "@FS1 ";
inline constexpr std::size_t kDeviceTelemetryMaxLine = 1024;

struct TelemetryLinkCounters {
    std::uint32_t accepted_fpga_frames{};
    std::uint32_t rejected_fpga_frames{};
    std::uint32_t stale_sensor_frames{};
    std::uint32_t stale_status_frames{};
    std::uint32_t dropped_pending_messages{};
};

class DeviceTelemetrySnapshot {
public:
    void reset();
    void ingest_sensor(const ParsedSensorFrame& frame, std::uint32_t received_ms);
    void ingest_status(const ParsedStatusFrame& frame, std::uint32_t received_ms);
    void ingest_ml(const MlObservation& observation, std::uint16_t sequence, std::uint32_t source_timestamp_ms, std::uint32_t received_ms);
    void set_link_counters(const TelemetryLinkCounters& counters);

    std::uint32_t revision() const { return revision_; }
    bool has_sensor() const { return have_sensor_; }
    bool has_status() const { return have_status_; }
    bool has_ml() const { return have_ml_; }

    std::size_t encode_line(std::uint32_t now_ms, char* out, std::size_t capacity) const;

private:
    bool have_sensor_{false};
    bool have_status_{false};
    bool have_ml_{false};
    ParsedSensorFrame sensor_{};
    ParsedStatusFrame status_{};
    MlObservation ml_{};
    std::uint16_t ml_sequence_{0};
    std::uint32_t ml_source_timestamp_ms_{0};
    std::uint32_t sensor_received_ms_{0};
    std::uint32_t status_received_ms_{0};
    std::uint32_t ml_received_ms_{0};
    TelemetryLinkCounters counters_{};
    std::uint32_t revision_{0};
};

}  // namespace forgesense
