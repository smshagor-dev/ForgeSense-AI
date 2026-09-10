#include "forgesense_calibration.h"

#include <cstdint>

namespace forgesense::sensing {
namespace {

void put_u16(std::uint8_t* p, std::uint16_t v) {
    p[0] = static_cast<std::uint8_t>(v);
    p[1] = static_cast<std::uint8_t>(v >> 8U);
}

void put_u32(std::uint8_t* p, std::uint32_t v) {
    for (unsigned i = 0; i < 4; ++i) p[i] = static_cast<std::uint8_t>(v >> (8U * i));
}

void put_i32(std::uint8_t* p, std::int32_t v) {
    put_u32(p, static_cast<std::uint32_t>(v));
}

std::uint16_t get_u16(const std::uint8_t* p) {
    return static_cast<std::uint16_t>(p[0]) |
           static_cast<std::uint16_t>(static_cast<std::uint16_t>(p[1]) << 8U);
}

std::uint32_t get_u32(const std::uint8_t* p) {
    std::uint32_t v = 0;
    for (unsigned i = 0; i < 4; ++i) v |= static_cast<std::uint32_t>(p[i]) << (8U * i);
    return v;
}

std::int32_t get_i32(const std::uint8_t* p) {
    return static_cast<std::int32_t>(get_u32(p));
}

void put_cal(std::uint8_t* p, const LinearCalibration& c) {
    put_i32(p + 0, c.raw_zero);
    put_i32(p + 4, c.gain_numerator);
    put_i32(p + 8, c.gain_denominator);
    put_i32(p + 12, c.output_offset);
}

LinearCalibration get_cal(const std::uint8_t* p) {
    return LinearCalibration{get_i32(p + 0), get_i32(p + 4), get_i32(p + 8), get_i32(p + 12)};
}

}  // namespace

std::uint32_t crc32_ieee(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xFFFFFFFFU;
    for (std::size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1U) ^ (0xEDB88320U & mask);
        }
    }
    return ~crc;
}

bool calibration_is_usable(const LinearCalibration& c) {
    return c.gain_denominator > 0 && c.raw_zero >= kRaw24Min && c.raw_zero <= kRaw24Max;
}

bool encode_calibration_record(const CalibrationRecord& record, std::array<std::uint8_t, kCalibrationBlobSize>& out) {
    if (!calibration_is_usable(record.temperature) || !calibration_is_usable(record.current)) return false;
    out.fill(0);
    put_u32(out.data() + 0, kCalibrationMagic);
    put_u16(out.data() + 4, kCalibrationVersion);
    put_u16(out.data() + 6, static_cast<std::uint16_t>(kCalibrationBlobSize));
    put_u32(out.data() + 8, record.sequence);
    put_cal(out.data() + 12, record.temperature);
    put_cal(out.data() + 28, record.current);
    put_u32(out.data() + 44, crc32_ieee(out.data(), 44));
    return true;
}

bool decode_calibration_record(const std::uint8_t* data, std::size_t size, CalibrationRecord& out) {
    if (data == nullptr || size != kCalibrationBlobSize) return false;
    if (get_u32(data + 0) != kCalibrationMagic) return false;
    if (get_u16(data + 4) != kCalibrationVersion) return false;
    if (get_u16(data + 6) != kCalibrationBlobSize) return false;
    if (get_u32(data + 44) != crc32_ieee(data, 44)) return false;
    CalibrationRecord decoded{};
    decoded.sequence = get_u32(data + 8);
    decoded.temperature = get_cal(data + 12);
    decoded.current = get_cal(data + 28);
    if (!calibration_is_usable(decoded.temperature) || !calibration_is_usable(decoded.current)) return false;
    out = decoded;
    return true;
}

}  // namespace forgesense::sensing
