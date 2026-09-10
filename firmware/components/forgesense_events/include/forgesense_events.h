#pragma once

#include "forgesense_protocol.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense {

enum class EventSeverity : std::uint8_t {
    Info = 0,
    Warning = 1,
    Critical = 2
};

enum class EventSource : std::uint8_t {
    System = 0,
    Fpga = 1,
    Edge = 2,
    Link = 3
};

enum class EventCode : std::uint8_t {
    Boot = 1,
    SensorInvalid = 2,
    LinkLost = 3,
    LinkRecovered = 4,
    MlWarning = 5,
    MlCritical = 6,
    HardCritical = 7,
    Emergency = 8,
    Recovery = 9
};

constexpr std::uint32_t kEventMagic = 0x56455346U;  // "FSEV" little-endian bytes.
constexpr std::uint8_t kEventRecordVersion = 1;
constexpr std::size_t kEventRecordSize = 36;

struct EventRecord {
    EventSeverity severity{EventSeverity::Info};
    EventSource source{EventSource::System};
    EventCode code{EventCode::Boot};
    std::uint32_t sequence{};
    std::uint32_t monotonic_ms{};
    std::uint8_t state_code{0xFF};
    std::uint8_t flags{};
    SensorSnapshot snapshot{};
    std::uint16_t anomaly_q15{};
    std::uint32_t detail{};
};

enum class EventDecodeStatus {
    Ok,
    BadSize,
    BadMagic,
    BadVersion,
    BadCrc
};

std::uint32_t crc32_ieee(const std::uint8_t* data, std::size_t size);

std::array<std::uint8_t, kEventRecordSize> encode_event_record(
    const EventRecord& record);

EventDecodeStatus decode_event_record(
    const std::uint8_t* data,
    std::size_t size,
    EventRecord& out);

}  // namespace forgesense
