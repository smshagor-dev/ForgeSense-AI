#include "forgesense_events.h"

namespace forgesense {
namespace {

void write_u16(std::uint8_t* p, std::uint16_t value) {
    p[0] = static_cast<std::uint8_t>(value & 0xFF);
    p[1] = static_cast<std::uint8_t>((value >> 8) & 0xFF);
}

void write_i16(std::uint8_t* p, std::int16_t value) {
    write_u16(p, static_cast<std::uint16_t>(value));
}

void write_u32(std::uint8_t* p, std::uint32_t value) {
    p[0] = static_cast<std::uint8_t>(value & 0xFF);
    p[1] = static_cast<std::uint8_t>((value >> 8) & 0xFF);
    p[2] = static_cast<std::uint8_t>((value >> 16) & 0xFF);
    p[3] = static_cast<std::uint8_t>((value >> 24) & 0xFF);
}

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

}  // namespace

std::uint32_t crc32_ieee(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xFFFFFFFFU;
    for (std::size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask =
                static_cast<std::uint32_t>(
                    -static_cast<std::int32_t>(crc & 1U));
            crc = (crc >> 1U) ^ (0xEDB88320U & mask);
        }
    }
    return crc ^ 0xFFFFFFFFU;
}

std::array<std::uint8_t, kEventRecordSize> encode_event_record(
    const EventRecord& record) {
    std::array<std::uint8_t, kEventRecordSize> out{};
    write_u32(out.data() + 0, kEventMagic);
    out[4] = kEventRecordVersion;
    out[5] = static_cast<std::uint8_t>(record.severity);
    out[6] = static_cast<std::uint8_t>(record.source);
    out[7] = static_cast<std::uint8_t>(record.code);
    write_u32(out.data() + 8, record.sequence);
    write_u32(out.data() + 12, record.monotonic_ms);
    out[16] = record.state_code;
    out[17] = record.flags;
    write_u16(out.data() + 18, record.snapshot.flags);
    write_i16(out.data() + 20, record.snapshot.temperature_deci_c);
    write_u16(out.data() + 22, record.snapshot.vibration_milli_g);
    write_u16(out.data() + 24, record.snapshot.current_milli_a);
    write_u16(out.data() + 26, record.anomaly_q15);
    write_u32(out.data() + 28, record.detail);
    const auto crc = crc32_ieee(out.data(), kEventRecordSize - 4);
    write_u32(out.data() + 32, crc);
    return out;
}

EventDecodeStatus decode_event_record(
    const std::uint8_t* data,
    std::size_t size,
    EventRecord& out) {
    if (data == nullptr || size != kEventRecordSize) {
        return EventDecodeStatus::BadSize;
    }
    if (read_u32(data + 0) != kEventMagic) {
        return EventDecodeStatus::BadMagic;
    }
    if (data[4] != kEventRecordVersion) {
        return EventDecodeStatus::BadVersion;
    }
    const auto received_crc = read_u32(data + 32);
    if (crc32_ieee(data, 32) != received_crc) {
        return EventDecodeStatus::BadCrc;
    }

    out.severity = static_cast<EventSeverity>(data[5]);
    out.source = static_cast<EventSource>(data[6]);
    out.code = static_cast<EventCode>(data[7]);
    out.sequence = read_u32(data + 8);
    out.monotonic_ms = read_u32(data + 12);
    out.state_code = data[16];
    out.flags = data[17];
    out.snapshot.flags = read_u16(data + 18);
    out.snapshot.temperature_deci_c = read_i16(data + 20);
    out.snapshot.vibration_milli_g = read_u16(data + 22);
    out.snapshot.current_milli_a = read_u16(data + 24);
    out.anomaly_q15 = read_u16(data + 26);
    out.detail = read_u32(data + 28);
    return EventDecodeStatus::Ok;
}

}  // namespace forgesense
