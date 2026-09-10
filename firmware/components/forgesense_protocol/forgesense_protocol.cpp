#include "forgesense_protocol.h"

namespace forgesense {
namespace {
constexpr std::size_t kHeaderSize = 12;
constexpr std::size_t kMlPayloadSize = 14;
constexpr std::size_t kFrameSize = kHeaderSize + kMlPayloadSize + 2;

std::uint16_t read_u16(const std::uint8_t* p) {
    return static_cast<std::uint16_t>(p[0]) | (static_cast<std::uint16_t>(p[1]) << 8);
}

std::uint32_t read_u32(const std::uint8_t* p) {
    return static_cast<std::uint32_t>(p[0]) |
           (static_cast<std::uint32_t>(p[1]) << 8) |
           (static_cast<std::uint32_t>(p[2]) << 16) |
           (static_cast<std::uint32_t>(p[3]) << 24);
}

bool health_valid(std::uint8_t value) {
    return value <= static_cast<std::uint8_t>(HealthClass::Abstain);
}
}  // namespace

std::uint16_t crc16_ccitt(const std::uint8_t* data, std::size_t size) {
    std::uint16_t crc = 0xFFFF;
    for (std::size_t i = 0; i < size; ++i) {
        crc ^= static_cast<std::uint16_t>(data[i]) << 8;
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc & 0x8000) ? static_cast<std::uint16_t>((crc << 1) ^ 0x1021) : static_cast<std::uint16_t>(crc << 1);
        }
    }
    return crc;
}

ParseStatus parse_ml_frame(const std::uint8_t* data, std::size_t size, ParsedMlFrame& out) {
    if (data == nullptr || size < kHeaderSize + 2) return ParseStatus::Truncated;
    if (data[0] != 0xA5 || data[1] != 0x5A) return ParseStatus::BadSof;
    if (data[2] != kProtocolVersion) return ParseStatus::BadVersion;
    if (data[3] != kMessageMlObservation) return ParseStatus::BadType;
    const auto payload_size = read_u16(data + 6);
    if (payload_size != kMlPayloadSize || size != kFrameSize) return ParseStatus::BadLength;
    const auto received_crc = read_u16(data + size - 2);
    const auto calculated_crc = crc16_ccitt(data + 2, size - 4);
    if (received_crc != calculated_crc) return ParseStatus::BadCrc;
    const std::uint8_t* payload = data + kHeaderSize;
    if (!health_valid(payload[10])) return ParseStatus::BadHealthClass;
    out.sequence = read_u16(data + 4);
    out.timestamp_ms = read_u32(data + 8);
    out.observation.model_id = read_u16(payload + 0);
    out.observation.model_version = read_u16(payload + 2);
    out.observation.feature_schema_version = read_u16(payload + 4);
    out.observation.flags = read_u16(payload + 6);
    out.observation.anomaly_q15 = read_u16(payload + 8);
    out.observation.health_class = static_cast<HealthClass>(payload[10]);
    out.observation.confidence_q8 = payload[11];
    out.observation.inference_age_ms = read_u16(payload + 12);
    return ParseStatus::Ok;
}

bool sequence_is_newer(std::uint16_t candidate, std::uint16_t previous) {
    const auto delta = static_cast<std::uint16_t>(candidate - previous);
    return delta != 0 && delta < 0x8000;
}

}  // namespace forgesense
