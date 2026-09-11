#include "forgesense_protocol.h"

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

int main() {
    constexpr std::array<std::uint8_t, forgesense::kStatusFrameSize> frame{
        0xA5, 0x5A, 0x01, 0x30, 0x02, 0x00, 0x04, 0x00,
        0x44, 0x33, 0x22, 0x11, 0x01, 0x08, 0xC0, 0x0E,
        0x76, 0x02
    };

    forgesense::ParsedStatusFrame parsed{};
    assert(forgesense::parse_status_frame(frame.data(), frame.size(), parsed) == forgesense::ParseStatus::Ok);
    assert(parsed.sequence == 2);
    assert(parsed.timestamp_ms == 0x11223344U);
    assert(parsed.status.state_code == 1);
    assert(parsed.status.operational_ready());
    assert(parsed.status.device_identity_ok());
    assert(!parsed.status.device_transport_error());
    assert(parsed.status.tmp117_trusted());
    assert(parsed.status.adxl355_trusted());
    assert(parsed.status.ads131m02_trusted());
    assert(!parsed.status.tmp117_error());
    assert(!parsed.status.adxl355_error());
    assert(!parsed.status.ads131m02_error());
    assert((parsed.status.safety_flags & forgesense::kSafetySensorsValid) != 0);

    std::cout << "commissioning status test PASS\n";
    return 0;
}
