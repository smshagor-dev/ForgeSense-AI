#pragma once

#include <cstddef>
#include <cstdint>

namespace forgesense {

constexpr std::uint8_t kProtocolVersion = 1;
constexpr std::uint8_t kMessageMlObservation = 0x10;
constexpr std::uint16_t kValidObservation = 0x0001;

enum class HealthClass : std::uint8_t { Normal = 0, Warning = 1, Critical = 2, Abstain = 3 };

struct MlObservation {
    std::uint16_t model_id{};
    std::uint16_t model_version{};
    std::uint16_t feature_schema_version{};
    std::uint16_t flags{};
    std::uint16_t anomaly_q15{};
    HealthClass health_class{HealthClass::Abstain};
    std::uint8_t confidence_q8{};
    std::uint16_t inference_age_ms{};
};

enum class ParseStatus { Ok, Truncated, BadSof, BadVersion, BadLength, BadCrc, BadType, BadHealthClass };

struct ParsedMlFrame {
    std::uint16_t sequence{};
    std::uint32_t timestamp_ms{};
    MlObservation observation{};
};

std::uint16_t crc16_ccitt(const std::uint8_t* data, std::size_t size);
ParseStatus parse_ml_frame(const std::uint8_t* data, std::size_t size, ParsedMlFrame& out);
bool sequence_is_newer(std::uint16_t candidate, std::uint16_t previous);

}  // namespace forgesense
