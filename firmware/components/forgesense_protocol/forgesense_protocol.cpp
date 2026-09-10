#include "forgesense_protocol.h"

namespace forgesense {
namespace {

constexpr std::size_t kHeaderSize = 12;
constexpr std::size_t kMlPayloadSize = 14;
constexpr std::size_t kSensorPayloadSize = 8;

std::uint16_t read_u16(const std::uint8_t* p) {
    return static_cast<std::uint16_t>(p[0]) |
           (static_cast<std::uint16_t>(p[1]) << 8);
}

std::int16_t read_i16(const std::uint8_t* p) {
    return static_cast<std::int16_t>(read_u16(p));
}

std::uint32_t read_u32(const std::uint8_t* p) {
    return static_cast<std::uint32_t>(p[0]) |
           (static_cast<std::uint32_t>(p[1]) << 8) |
           (static_cast<std::uint32_t>(p[2]) << 16) |
           (static_cast<std::uint32_t>(p[3]) << 24);
}

void write_u16(std::uint8_t* p, std::uint16_t value) {
    p[0] = static_cast<std::uint8_t>(value & 0xFF);
    p[1] = static_cast<std::uint8_t>((value >> 8) & 0xFF);
}

void write_u32(std::uint8_t* p, std::uint32_t value) {
    p[0] = static_cast<std::uint8_t>(value & 0xFF);
    p[1] = static_cast<std::uint8_t>((value >> 8) & 0xFF);
    p[2] = static_cast<std::uint8_t>((value >> 16) & 0xFF);
    p[3] = static_cast<std::uint8_t>((value >> 24) & 0xFF);
}

bool health_valid(std::uint8_t value) {
    return value <= static_cast<std::uint8_t>(HealthClass::Abstain);
}

ParseStatus validate_common(
    const std::uint8_t* data,
    std::size_t size,
    std::uint8_t expected_type,
    std::uint16_t expected_payload_size) {
    if (data == nullptr || size < kHeaderSize + 2) {
        return ParseStatus::Truncated;
    }
    if (data[0] != 0xA5 || data[1] != 0x5A) {
        return ParseStatus::BadSof;
    }
    if (data[2] != kProtocolVersion) {
        return ParseStatus::BadVersion;
    }
    if (data[3] != expected_type) {
        return ParseStatus::BadType;
    }
    const auto payload_size = read_u16(data + 6);
    const std::size_t expected_frame_size =
        kHeaderSize + expected_payload_size + 2;
    if (payload_size != expected_payload_size || size != expected_frame_size) {
        return ParseStatus::BadLength;
    }
    const auto received_crc = read_u16(data + size - 2);
    const auto calculated_crc = crc16_ccitt(data + 2, size - 4);
    if (received_crc != calculated_crc) {
        return ParseStatus::BadCrc;
    }
    return ParseStatus::Ok;
}

}  // namespace

std::uint16_t crc16_ccitt(const std::uint8_t* data, std::size_t size) {
    std::uint16_t crc = 0xFFFF;
    for (std::size_t i = 0; i < size; ++i) {
        crc ^= static_cast<std::uint16_t>(data[i]) << 8;
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc & 0x8000)
                ? static_cast<std::uint16_t>((crc << 1) ^ 0x1021)
                : static_cast<std::uint16_t>(crc << 1);
        }
    }
    return crc;
}

ParseStatus parse_ml_frame(
    const std::uint8_t* data,
    std::size_t size,
    ParsedMlFrame& out) {
    const auto common =
        validate_common(data, size, kMessageMlObservation, kMlPayloadSize);
    if (common != ParseStatus::Ok) {
        return common;
    }

    const std::uint8_t* payload = data + kHeaderSize;
    if (!health_valid(payload[10])) {
        return ParseStatus::BadHealthClass;
    }

    const auto anomaly_q15 = read_u16(payload + 8);
    if (anomaly_q15 > 32767) {
        return ParseStatus::BadRange;
    }

    out.sequence = read_u16(data + 4);
    out.timestamp_ms = read_u32(data + 8);
    out.observation.model_id = read_u16(payload + 0);
    out.observation.model_version = read_u16(payload + 2);
    out.observation.feature_schema_version = read_u16(payload + 4);
    out.observation.flags = read_u16(payload + 6);
    out.observation.anomaly_q15 = anomaly_q15;
    out.observation.health_class = static_cast<HealthClass>(payload[10]);
    out.observation.confidence_q8 = payload[11];
    out.observation.inference_age_ms = read_u16(payload + 12);
    return ParseStatus::Ok;
}

ParseStatus parse_sensor_frame(
    const std::uint8_t* data,
    std::size_t size,
    ParsedSensorFrame& out) {
    const auto common =
        validate_common(data, size, kMessageSensorSnapshot, kSensorPayloadSize);
    if (common != ParseStatus::Ok) {
        return common;
    }

    const std::uint8_t* payload = data + kHeaderSize;
    out.sequence = read_u16(data + 4);
    out.timestamp_ms = read_u32(data + 8);
    out.snapshot.temperature_deci_c = read_i16(payload + 0);
    out.snapshot.vibration_milli_g = read_u16(payload + 2);
    out.snapshot.current_milli_a = read_u16(payload + 4);
    out.snapshot.flags = read_u16(payload + 6);
    return ParseStatus::Ok;
}

bool encode_ml_frame(
    const MlObservation& observation,
    std::uint16_t sequence,
    std::uint32_t timestamp_ms,
    std::array<std::uint8_t, kMlFrameSize>& out) {
    if (observation.anomaly_q15 > 32767 ||
        !health_valid(static_cast<std::uint8_t>(observation.health_class))) {
        return false;
    }

    out.fill(0);
    out[0] = 0xA5;
    out[1] = 0x5A;
    out[2] = kProtocolVersion;
    out[3] = kMessageMlObservation;
    write_u16(out.data() + 4, sequence);
    write_u16(out.data() + 6, static_cast<std::uint16_t>(kMlPayloadSize));
    write_u32(out.data() + 8, timestamp_ms);

    std::uint8_t* payload = out.data() + kHeaderSize;
    write_u16(payload + 0, observation.model_id);
    write_u16(payload + 2, observation.model_version);
    write_u16(payload + 4, observation.feature_schema_version);
    write_u16(payload + 6, observation.flags);
    write_u16(payload + 8, observation.anomaly_q15);
    payload[10] = static_cast<std::uint8_t>(observation.health_class);
    payload[11] = observation.confidence_q8;
    write_u16(payload + 12, observation.inference_age_ms);

    const auto crc = crc16_ccitt(out.data() + 2, kMlFrameSize - 4);
    write_u16(out.data() + kMlFrameSize - 2, crc);
    return true;
}

bool sequence_is_newer(std::uint16_t candidate, std::uint16_t previous) {
    const auto delta = static_cast<std::uint16_t>(candidate - previous);
    return delta != 0 && delta < 0x8000;
}

}  // namespace forgesense
