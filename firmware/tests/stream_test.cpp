#include "forgesense_stream.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    using namespace forgesense;

    const std::array<std::uint8_t, kMlFrameSize> ml{
        0xA5,0x5A,0x01,0x10,0x07,0x00,0x0E,0x00,
        0x39,0x30,0x00,0x00,0x01,0x00,0x01,0x00,
        0x01,0x00,0x01,0x00,0xFF,0x67,0x01,0xE0,
        0x19,0x00,0xE3,0xC8
    };

    MlStreamDecoder ml_decoder;
    ParsedMlFrame parsed_ml{};
    for (const auto byte : std::array<std::uint8_t, 4>{0x00,0xA5,0x00,0x55}) {
        (void)ml_decoder.push(byte, parsed_ml);
    }
    StreamEvent ml_event = StreamEvent::None;
    for (const auto byte : ml) {
        ml_event = ml_decoder.push(byte, parsed_ml);
    }
    assert(ml_event == StreamEvent::Frame);
    assert(ml_decoder.accepted_frames() == 1);

    FreshnessGate gate;
    assert(gate.accept(parsed_ml) == GateStatus::Accepted);
    assert(gate.accept(parsed_ml) == GateStatus::ReplayOrDuplicate);

    const std::array<std::uint8_t, kSensorFrameSize> sensor{
        0xA5,0x5A,0x01,0x11,0x34,0x12,0x08,0x00,
        0x04,0x03,0x02,0x01,0x1F,0x01,0x8E,0x00,
        0xB4,0x05,0x07,0x00,0xD9,0xB7
    };
    SensorStreamDecoder sensor_decoder;
    ParsedSensorFrame parsed_sensor{};
    StreamEvent sensor_event = StreamEvent::None;
    for (const auto byte : sensor) {
        sensor_event = sensor_decoder.push(byte, parsed_sensor);
    }
    assert(sensor_event == StreamEvent::Frame);
    assert(parsed_sensor.snapshot.all_valid());

    SequenceGate sensor_gate;
    assert(sensor_gate.accept(parsed_sensor.sequence));
    assert(!sensor_gate.accept(parsed_sensor.sequence));
    assert(sensor_gate.accept(static_cast<std::uint16_t>(parsed_sensor.sequence + 1U)));

    auto corrupted_sensor = sensor;
    corrupted_sensor[15] ^= 0x01;
    StreamEvent bad_event = StreamEvent::None;
    for (const auto byte : corrupted_sensor) {
        bad_event = sensor_decoder.push(byte, parsed_sensor);
    }
    assert(bad_event == StreamEvent::Rejected);
    assert(sensor_decoder.rejected_frames() >= 1);

    std::cout << "firmware stream tests PASS\n";
    return 0;
}
