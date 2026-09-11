#include "maintenance_protocol.hpp"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <iostream>

int main() {
    using namespace forgesense::maintenance;

    const std::array<std::uint8_t, 4> payload{0x11, 0x22, 0x33, 0x44};
    std::array<std::uint8_t, kMaintenanceMaxFrameSize> encoded{};
    std::size_t encoded_size = 0;
    assert(encode_maintenance_frame(
        static_cast<std::uint8_t>(MaintenanceOpcode::PrepareRecord),
        payload.data(),
        payload.size(),
        encoded,
        encoded_size));
    assert(encoded_size == kMaintenanceHeaderSize + payload.size() + kMaintenanceCrcSize);
    assert(encoded[0] == 'F' && encoded[1] == 'S' && encoded[2] == 'M' && encoded[3] == '1');
    assert(encoded[4] == kMaintenanceVersion);

    MaintenanceFrameParser parser;
    MaintenanceFrame decoded{};
    bool complete = false;
    for (std::size_t index = 0; index < encoded_size; ++index) {
        complete = parser.feed(encoded[index], decoded);
        if (index + 1U < encoded_size) {
            assert(!complete);
        }
    }
    assert(complete);
    assert(decoded.opcode == static_cast<std::uint8_t>(MaintenanceOpcode::PrepareRecord));
    assert(decoded.payload_size == payload.size());
    for (std::size_t index = 0; index < payload.size(); ++index) {
        assert(decoded.payload[index] == payload[index]);
    }

    std::array<std::uint8_t, 170> signed_prepare{};
    for (std::size_t index = 0; index < signed_prepare.size(); ++index) {
        signed_prepare[index] = static_cast<std::uint8_t>(index & 0xFFU);
    }
    assert(encode_maintenance_frame(
        static_cast<std::uint8_t>(MaintenanceOpcode::PrepareRecord),
        signed_prepare.data(),
        signed_prepare.size(),
        encoded,
        encoded_size));
    parser.reset();
    complete = false;
    for (std::size_t index = 0; index < encoded_size; ++index) {
        complete = parser.feed(encoded[index], decoded);
    }
    assert(complete);
    assert(decoded.payload_size == signed_prepare.size());
    assert(decoded.payload[0] == 0U);
    assert(decoded.payload[169] == 169U);

    auto corrupt = encoded;
    corrupt[encoded_size - 1U] ^= 0x80U;
    parser.reset();
    for (std::size_t index = 0; index < encoded_size; ++index) {
        assert(!parser.feed(corrupt[index], decoded));
    }

    std::array<std::uint8_t, kMaintenanceMaxFrameSize> query{};
    std::size_t query_size = 0;
    assert(encode_maintenance_frame(
        static_cast<std::uint8_t>(MaintenanceOpcode::QueryAuthorization),
        nullptr,
        0,
        query,
        query_size));
    bool recovered = false;
    for (std::size_t index = 0; index < query_size; ++index) {
        recovered = parser.feed(query[index], decoded);
    }
    assert(recovered);
    assert(decoded.opcode == static_cast<std::uint8_t>(MaintenanceOpcode::QueryAuthorization));
    assert(decoded.payload_size == 0U);

    assert(maintenance_crc32_ieee(
        reinterpret_cast<const std::uint8_t*>("123456789"), 9) == 0xCBF43926U);

    std::cout << "maintenance_protocol_test PASS\n";
    return 0;
}
