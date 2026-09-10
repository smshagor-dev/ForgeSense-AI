#pragma once

#include "forgesense_protocol.h"
#include "forgesense_stream.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense::edge {

class LinkService {
public:
    bool begin();
    bool receive(ParsedFpgaMessage& out, std::uint32_t timeout_ms);
    bool send_observation(
        const MlObservation& observation,
        std::uint16_t sequence,
        std::uint32_t timestamp_ms);

    std::uint32_t accepted_fpga_frames() const {
        return fpga_decoder_.accepted_frames();
    }

    std::uint32_t rejected_fpga_frames() const {
        return fpga_decoder_.rejected_frames();
    }

    std::uint32_t stale_sensor_frames() const { return stale_sensor_frames_; }
    std::uint32_t stale_status_frames() const { return stale_status_frames_; }
    std::uint32_t dropped_pending_messages() const { return dropped_pending_messages_; }

private:
    static constexpr std::size_t kPendingCapacity = 8;

    FpgaStreamDecoder fpga_decoder_;
    SequenceGate sensor_sequence_gate_;
    SequenceGate status_sequence_gate_;
    std::array<ParsedFpgaMessage, kPendingCapacity> pending_{};
    std::size_t pending_head_{0};
    std::size_t pending_count_{0};
    std::uint32_t stale_sensor_frames_{0};
    std::uint32_t stale_status_frames_{0};
    std::uint32_t dropped_pending_messages_{0};
    int uart_port_{-1};

    void enqueue(const ParsedFpgaMessage& message);
    bool dequeue(ParsedFpgaMessage& out);
};

}  // namespace forgesense::edge
