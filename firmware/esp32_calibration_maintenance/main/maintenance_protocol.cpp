#include "maintenance_protocol.hpp"

#include <algorithm>

namespace forgesense::maintenance {
namespace {

void write_le16(std::uint8_t* out, std::uint16_t value) {
    out[0] = static_cast<std::uint8_t>(value & 0xFFU);
    out[1] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
}

void write_le32(std::uint8_t* out, std::uint32_t value) {
    out[0] = static_cast<std::uint8_t>(value & 0xFFU);
    out[1] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
    out[2] = static_cast<std::uint8_t>((value >> 16U) & 0xFFU);
    out[3] = static_cast<std::uint8_t>((value >> 24U) & 0xFFU);
}

std::uint16_t read_le16(const std::uint8_t* data) {
    return static_cast<std::uint16_t>(data[0]) |
           (static_cast<std::uint16_t>(data[1]) << 8U);
}

std::uint32_t read_le32(const std::uint8_t* data) {
    return static_cast<std::uint32_t>(data[0]) |
           (static_cast<std::uint32_t>(data[1]) << 8U) |
           (static_cast<std::uint32_t>(data[2]) << 16U) |
           (static_cast<std::uint32_t>(data[3]) << 24U);
}

}  // namespace

std::uint32_t maintenance_crc32_ieee(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xFFFFFFFFU;
    for (std::size_t index = 0; index < size; ++index) {
        crc ^= static_cast<std::uint32_t>(data[index]);
        for (int bit = 0; bit < 8; ++bit) {
            const bool lsb = (crc & 1U) != 0U;
            crc >>= 1U;
            if (lsb) {
                crc ^= 0xEDB88320U;
            }
        }
    }
    return crc ^ 0xFFFFFFFFU;
}

bool encode_maintenance_frame(
    std::uint8_t opcode,
    const std::uint8_t* payload,
    std::size_t payload_size,
    std::array<std::uint8_t, kMaintenanceMaxFrameSize>& out,
    std::size_t& out_size) {
    if (payload_size > kMaintenanceMaxPayload || (payload_size > 0U && payload == nullptr)) {
        return false;
    }
    std::copy(kMaintenanceMagic.begin(), kMaintenanceMagic.end(), out.begin());
    out[4] = kMaintenanceVersion;
    out[5] = opcode;
    write_le16(out.data() + 6U, static_cast<std::uint16_t>(payload_size));
    if (payload_size > 0U) {
        std::copy(payload, payload + payload_size, out.begin() + kMaintenanceHeaderSize);
    }
    const std::size_t body_size = kMaintenanceHeaderSize + payload_size;
    const std::uint32_t crc = maintenance_crc32_ieee(out.data(), body_size);
    write_le32(out.data() + body_size, crc);
    out_size = body_size + kMaintenanceCrcSize;
    return true;
}

void MaintenanceFrameParser::reset() {
    size_ = 0;
    expected_size_ = 0;
}

void MaintenanceFrameParser::restart_with(std::uint8_t byte) {
    reset();
    if (byte == kMaintenanceMagic[0]) {
        buffer_[0] = byte;
        size_ = 1;
    }
}

bool MaintenanceFrameParser::feed(std::uint8_t byte, MaintenanceFrame& out) {
    if (size_ < kMaintenanceMagic.size()) {
        if (byte == kMaintenanceMagic[size_]) {
            buffer_[size_++] = byte;
        } else {
            restart_with(byte);
        }
        return false;
    }

    if (size_ >= buffer_.size()) {
        restart_with(byte);
        return false;
    }

    buffer_[size_++] = byte;
    if (size_ == 5U && buffer_[4] != kMaintenanceVersion) {
        restart_with(byte);
        return false;
    }
    if (size_ == kMaintenanceHeaderSize) {
        const std::size_t payload_size = read_le16(buffer_.data() + 6U);
        if (payload_size > kMaintenanceMaxPayload) {
            restart_with(byte);
            return false;
        }
        expected_size_ = kMaintenanceHeaderSize + payload_size + kMaintenanceCrcSize;
    }
    if (expected_size_ == 0U || size_ < expected_size_) {
        return false;
    }
    if (size_ != expected_size_) {
        restart_with(byte);
        return false;
    }

    const std::uint32_t claimed_crc = read_le32(buffer_.data() + expected_size_ - kMaintenanceCrcSize);
    const std::uint32_t computed_crc = maintenance_crc32_ieee(
        buffer_.data(), expected_size_ - kMaintenanceCrcSize);
    if (claimed_crc != computed_crc) {
        restart_with(byte);
        return false;
    }

    out.opcode = buffer_[5];
    out.payload_size = read_le16(buffer_.data() + 6U);
    out.payload.fill(0);
    std::copy(
        buffer_.begin() + kMaintenanceHeaderSize,
        buffer_.begin() + kMaintenanceHeaderSize + out.payload_size,
        out.payload.begin());
    reset();
    return true;
}

}  // namespace forgesense::maintenance
