#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense::maintenance {

constexpr std::array<std::uint8_t, 4> kMaintenanceMagic{'F', 'S', 'M', '1'};
constexpr std::uint8_t kMaintenanceVersion = 1;
constexpr std::size_t kMaintenanceMaxPayload = 64;
constexpr std::size_t kMaintenanceHeaderSize = 8;
constexpr std::size_t kMaintenanceCrcSize = 4;
constexpr std::size_t kMaintenanceMaxFrameSize =
    kMaintenanceHeaderSize + kMaintenanceMaxPayload + kMaintenanceCrcSize;

enum class MaintenanceOpcode : std::uint8_t {
    QueryStatus = 0x01,
    PrepareRecord = 0x02,
    CommitRecord = 0x03,
    StatusResponse = 0x81,
    PrepareResponse = 0x82,
    CommitResponse = 0x83,
};

enum class MaintenanceStatus : std::uint8_t {
    Ok = 0,
    BadRequest = 1,
    PhysicalGateOpen = 2,
    StoreUnavailable = 3,
    SessionMismatch = 4,
    SequenceMismatch = 5,
    RecordInvalid = 6,
    PendingMismatch = 7,
    CommitFailed = 8,
    InternalError = 9,
};

struct MaintenanceFrame {
    std::uint8_t opcode{0};
    std::size_t payload_size{0};
    std::array<std::uint8_t, kMaintenanceMaxPayload> payload{};
};

std::uint32_t maintenance_crc32_ieee(const std::uint8_t* data, std::size_t size);

bool encode_maintenance_frame(
    std::uint8_t opcode,
    const std::uint8_t* payload,
    std::size_t payload_size,
    std::array<std::uint8_t, kMaintenanceMaxFrameSize>& out,
    std::size_t& out_size);

class MaintenanceFrameParser {
public:
    bool feed(std::uint8_t byte, MaintenanceFrame& out);
    void reset();

private:
    void restart_with(std::uint8_t byte);

    std::array<std::uint8_t, kMaintenanceMaxFrameSize> buffer_{};
    std::size_t size_{0};
    std::size_t expected_size_{0};
};

}  // namespace forgesense::maintenance
