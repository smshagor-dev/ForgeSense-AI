#include "forgesense_protocol.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    using namespace forgesense;

    assert(sequence_is_newer(0, 65535));
    assert(!sequence_is_newer(65535, 0));

    const std::array<std::uint8_t, 9> check{
        '1','2','3','4','5','6','7','8','9'};
    assert(crc16_ccitt(check.data(), check.size()) == 0x29B1);

    const std::array<std::uint8_t, kMlFrameSize> golden_ml{
        0xA5,0x5A,0x01,0x10,0x07,0x00,0x0E,0x00,
        0x39,0x30,0x00,0x00,0x01,0x00,0x01,0x00,
        0x01,0x00,0x01,0x00,0xFF,0x67,0x01,0xE0,
        0x19,0x00,0xE3,0xC8
    };

    ParsedMlFrame parsed_ml{};
    assert(parse_ml_frame(
        golden_ml.data(), golden_ml.size(), parsed_ml) == ParseStatus::Ok);
    assert(parsed_ml.sequence == 7);
    assert(parsed_ml.timestamp_ms == 12345);
    assert(parsed_ml.observation.model_id == 1);
    assert(parsed_ml.observation.anomaly_q15 == 0x67FF);
    assert(parsed_ml.observation.health_class == HealthClass::Warning);
    assert(parsed_ml.observation.inference_age_ms == 25);

    std::array<std::uint8_t, kMlFrameSize> encoded_ml{};
    assert(encode_ml_frame(
        parsed_ml.observation,
        parsed_ml.sequence,
        parsed_ml.timestamp_ms,
        encoded_ml));
    assert(encoded_ml == golden_ml);

    auto corrupted = golden_ml;
    corrupted[20] ^= 0x01;
    assert(parse_ml_frame(
        corrupted.data(), corrupted.size(), parsed_ml) == ParseStatus::BadCrc);

    const std::array<std::uint8_t, kSensorFrameSize> golden_sensor{
        0xA5,0x5A,0x01,0x11,0x34,0x12,0x08,0x00,
        0x04,0x03,0x02,0x01,0x1F,0x01,0x8E,0x00,
        0xB4,0x05,0x07,0x00,0xD9,0xB7
    };
    ParsedSensorFrame parsed_sensor{};
    assert(parse_sensor_frame(
        golden_sensor.data(),
        golden_sensor.size(),
        parsed_sensor) == ParseStatus::Ok);
    assert(parsed_sensor.sequence == 0x1234);
    assert(parsed_sensor.timestamp_ms == 0x01020304);
    assert(parsed_sensor.snapshot.temperature_deci_c == 287);
    assert(parsed_sensor.snapshot.vibration_milli_g == 142);
    assert(parsed_sensor.snapshot.current_milli_a == 1460);
    assert(parsed_sensor.snapshot.all_valid());

    std::cout << "firmware protocol tests PASS\n";
    return 0;
}
