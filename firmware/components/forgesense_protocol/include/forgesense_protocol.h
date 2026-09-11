#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense {

constexpr std::uint8_t kProtocolVersion = 1;
constexpr std::uint8_t kMessageMlObservation = 0x10;
constexpr std::uint8_t kMessageSensorSnapshot = 0x11;
constexpr std::uint8_t kMessageStatus = 0x30;
constexpr std::uint16_t kValidObservation = 0x0001;

constexpr std::uint16_t kSensorValidTemperature = 0x0001;
constexpr std::uint16_t kSensorValidVibration = 0x0002;
constexpr std::uint16_t kSensorValidCurrent = 0x0004;
constexpr std::uint16_t kSensorAllValid =
    kSensorValidTemperature | kSensorValidVibration | kSensorValidCurrent;

constexpr std::size_t kMlFrameSize = 28;
constexpr std::size_t kSensorFrameSize = 22;
constexpr std::size_t kStatusFrameSize = 18;

constexpr std::uint8_t kStatusLoadEnable = 0x01;
constexpr std::uint8_t kStatusWarningActive = 0x02;
constexpr std::uint8_t kStatusFaultLatched = 0x04;
constexpr std::uint8_t kStatusOperationalReady = 0x08;

constexpr std::uint16_t kSafetyHardWarning = 0x0001;
constexpr std::uint16_t kSafetyHardCritical = 0x0002;
constexpr std::uint16_t kSafetyCommTimeout = 0x0004;
constexpr std::uint16_t kSafetyMlWarning = 0x0008;
constexpr std::uint16_t kSafetyMlCritical = 0x0010;
constexpr std::uint16_t kSafetyEmergency = 0x0020;
constexpr std::uint16_t kSafetySensorsValid = 0x0040;
constexpr std::uint16_t kSafetyDeviceIdentityOk = 0x0080;
constexpr std::uint16_t kSafetyDeviceTransportError = 0x0100;
constexpr std::uint16_t kSafetyTmp117Trusted = 0x0200;
constexpr std::uint16_t kSafetyAdxl355Trusted = 0x0400;
constexpr std::uint16_t kSafetyAds131m02Trusted = 0x0800;
constexpr std::uint16_t kSafetyTmp117Error = 0x1000;
constexpr std::uint16_t kSafetyAdxl355Error = 0x2000;
constexpr std::uint16_t kSafetyAds131m02Error = 0x4000;

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

struct StatusSnapshot {
    std::uint8_t state_code{};
    std::uint8_t control_flags{};
    std::uint16_t safety_flags{};

    bool load_enable() const { return (control_flags & kStatusLoadEnable) != 0; }
    bool warning_active() const { return (control_flags & kStatusWarningActive) != 0; }
    bool fault_latched() const { return (control_flags & kStatusFaultLatched) != 0; }
    bool operational_ready() const { return (control_flags & kStatusOperationalReady) != 0; }
    bool device_identity_ok() const { return (safety_flags & kSafetyDeviceIdentityOk) != 0; }
    bool device_transport_error() const { return (safety_flags & kSafetyDeviceTransportError) != 0; }
    bool tmp117_trusted() const { return (safety_flags & kSafetyTmp117Trusted) != 0; }
    bool adxl355_trusted() const { return (safety_flags & kSafetyAdxl355Trusted) != 0; }
    bool ads131m02_trusted() const { return (safety_flags & kSafetyAds131m02Trusted) != 0; }
    bool tmp117_error() const { return (safety_flags & kSafetyTmp117Error) != 0; }
    bool adxl355_error() const { return (safety_flags & kSafetyAdxl355Error) != 0; }
    bool ads131m02_error() const { return (safety_flags & kSafetyAds131m02Error) != 0; }
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

struct ParsedStatusFrame {
    std::uint16_t sequence{};
    std::uint32_t timestamp_ms{};
    StatusSnapshot status{};
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

ParseStatus parse_status_frame(
    const std::uint8_t* data,
    std::size_t size,
    ParsedStatusFrame& out);

bool encode_ml_frame(
    const MlObservation& observation,
    std::uint16_t sequence,
    std::uint32_t timestamp_ms,
    std::array<std::uint8_t, kMlFrameSize>& out);

bool sequence_is_newer(std::uint16_t candidate, std::uint16_t previous);

}  // namespace forgesense
