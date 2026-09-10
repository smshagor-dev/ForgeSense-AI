#include "forgesense_stream.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    using namespace forgesense;
    const std::array<std::uint8_t, 28> golden{
        0xA5,0x5A,0x01,0x10,0x07,0x00,0x0E,0x00,
        0x39,0x30,0x00,0x00,0x01,0x00,0x01,0x00,
        0x01,0x00,0x01,0x00,0xFF,0x67,0x01,0xE0,
        0x19,0x00,0xE3,0xC8
    };

    MlStreamDecoder stream;
    ParsedMlFrame parsed{};
    StreamEvent event = StreamEvent::None;
    for (auto byte : std::array<std::uint8_t, 4>{0x00, 0xA5, 0x01, 0x44}) {
        event = stream.push(byte, parsed);
    }
    assert(event != StreamEvent::Frame);

    for (auto byte : golden) {
        event = stream.push(byte, parsed);
    }
    assert(event == StreamEvent::Frame);
    assert(parsed.sequence == 7);
    assert(stream.accepted_frames() == 1);

    FreshnessGate gate;
    assert(gate.accept(parsed) == GateStatus::Accepted);
    assert(gate.accept(parsed) == GateStatus::ReplayOrDuplicate);

    auto corrupted = golden;
    corrupted[20] ^= 0x01;
    for (auto byte : corrupted) {
        event = stream.push(byte, parsed);
    }
    assert(event == StreamEvent::Rejected);

    auto next = golden;
    next[4] = 8;
    next[26] = 0;
    next[27] = 0;
    const auto crc = crc16_ccitt(next.data() + 2, 24);
    next[26] = static_cast<std::uint8_t>(crc & 0xFF);
    next[27] = static_cast<std::uint8_t>(crc >> 8);
    for (auto byte : next) {
        event = stream.push(byte, parsed);
    }
    assert(event == StreamEvent::Frame);
    assert(parsed.sequence == 8);
    assert(gate.accept(parsed) == GateStatus::Accepted);

    std::cout << "firmware stream and freshness tests PASS\n";
    return 0;
}
