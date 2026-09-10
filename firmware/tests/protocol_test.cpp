#include "forgesense_protocol.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    using namespace forgesense;
    assert(sequence_is_newer(0, 65535));
    assert(!sequence_is_newer(65535, 0));
    const std::array<std::uint8_t, 9> check{'1','2','3','4','5','6','7','8','9'};
    assert(crc16_ccitt(check.data(), check.size()) == 0x29B1);
    const std::array<std::uint8_t, 28> golden{
        0xA5,0x5A,0x01,0x10,0x07,0x00,0x0E,0x00,
        0x39,0x30,0x00,0x00,0x01,0x00,0x01,0x00,
        0x01,0x00,0x01,0x00,0xFF,0x67,0x01,0xE0,
        0x19,0x00,0xE3,0xC8
    };
    ParsedMlFrame parsed{};
    assert(parse_ml_frame(golden.data(), golden.size(), parsed) == ParseStatus::Ok);
    assert(parsed.sequence == 7);
    assert(parsed.timestamp_ms == 12345);
    assert(parsed.observation.model_id == 1);
    assert(parsed.observation.anomaly_q15 == 0x67FF);
    assert(parsed.observation.health_class == HealthClass::Warning);
    assert(parsed.observation.inference_age_ms == 25);
    auto corrupted = golden;
    corrupted[20] ^= 0x01;
    assert(parse_ml_frame(corrupted.data(), corrupted.size(), parsed) == ParseStatus::BadCrc);
    std::cout << "firmware protocol tests PASS\n";
    return 0;
}
