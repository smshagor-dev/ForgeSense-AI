#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense {

constexpr std::uint8_t kProtocolVersion = 1;
constexpr std::uint8_t kMessageMlObservation = 0x10;
constexpr std::uint8_t kMessageSensorSnapshot = 0x11;
constexpr std::uint16_t kValidObservation = 0x0001;

constexpr std::uint16_t kSensorValidTemperature = 0x0001;
constexpr std::uint16_t kSensorValidVibration = 0x0002;
constexpr std::uint16_t kSensorValidCurrent = 0x0004;
constexpr std::uint16_t kSensorAllValid =
    kSensorValidTemperature | kSensorValidVibration | kSensorValidCurrent;

constexpr std::size_t kMlFrameSize = 28;
constexpr std::size_t kSensorFrameSize = 22;

enum class HealthClass : std::uint8_t {
    Normal = 0,
    Warning = 1,
    Critical = 2,
    Abstain = 3
};

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

struct SensorSnapshot {
    std::int16_t temperature_deci_c{};
    std::uint16_t vibration_milli_g{};
    std::uint16_t current_milli_a{};
    std::uint16_t flags{};

    bool all_valid() const {
        return (flags & kSensorAllValid) == kSensorAllValid;
    }
};

enum class ParseStatus {
    Ok,
    Truncated,
    BadSof,
    BadVersion,
    BadLength,
    BadCrc,
    BadType,
    BadHealthClass,
    BadRange
};

struct ParsedMlFrame {
    std::uint16_t sequence{};
    std::uint32_t timestamp_ms{};
    MlObservation observation{};
};

struct ParsedSensorFrame {
    std::uint16_t sequence{};
    std::uint32_t timestamp_ms{};
    SensorSnapshot snapshot{};
};

std::uint16_t crc16_ccitt(const std::uint8_t* data, std::size_t size);

ParseStatus parse_ml_frame(
    const std::uint8_t* data,
    std::size_t size,
    ParsedMlFrame& out);

ParseStatus parse_sensor_frame(
    const std::uint8_t* data,
    std::size_t size,
    ParsedSensorFrame& out);

bool encode_ml_frame(
    const MlObservation& observation,
    std::uint16_t sequence,
    std::uint32_t timestamp_ms,
    std::array<std::uint8_t, kMlFrameSize>& out);

bool sequence_is_newer(std::uint16_t candidate, std::uint16_t previous);

}  // namespace forgesense
