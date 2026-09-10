#pragma once

#include "forgesense_protocol.h"
#include "forgesense_stream.h"

#include <cstdint>

namespace forgesense::edge {

class LinkService {
public:
    bool begin();
    bool receive_sensor(ParsedSensorFrame& out, std::uint32_t timeout_ms);
    bool send_observation(
        const MlObservation& observation,
        std::uint16_t sequence,
        std::uint32_t timestamp_ms);

    std::uint32_t accepted_sensor_frames() const {
        return sensor_decoder_.accepted_frames();
    }

    std::uint32_t rejected_sensor_frames() const {
        return sensor_decoder_.rejected_frames();
    }

    std::uint32_t stale_sensor_frames() const {
        return stale_sensor_frames_;
    }

private:
    SensorStreamDecoder sensor_decoder_;
    SequenceGate sensor_sequence_gate_;
    std::uint32_t stale_sensor_frames_{0};
    int uart_port_{-1};
};

}  // namespace forgesense::edge
