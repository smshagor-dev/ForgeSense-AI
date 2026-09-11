#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "calibration_store_nvs.hpp"
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "esp_err.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "forgesense_calibration.h"
#include "forgesense_calibration_provisioning.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "maintenance_authorization.hpp"
#include "maintenance_protocol.hpp"
#include "nvs_flash.h"
#include "sdkconfig.h"

namespace {

using forgesense::maintenance::CalibrationNvsStore;
using forgesense::maintenance::MaintenanceAuthorizationVerifier;
using forgesense::maintenance::MaintenanceFrame;
using forgesense::maintenance::MaintenanceFrameParser;
using forgesense::maintenance::MaintenanceOpcode;
using forgesense::maintenance::MaintenanceStatus;
using forgesense::sensing::CalibrationRecord;

constexpr std::size_t kUsbReadBufferSize = 256;
constexpr std::size_t kStatusPayloadSize = 27;
constexpr std::size_t kAuthorizationStatusPayloadSize = 34;
constexpr std::size_t kPrepareFixedRequestSize = 90;
constexpr std::size_t kPrepareResponseSize = 13;
constexpr std::size_t kCommitRequestSize = 12;
constexpr std::size_t kCommitResponseSize = 9;

CalibrationNvsStore g_store;
MaintenanceAuthorizationVerifier g_authorization;
bool g_store_ready = false;
bool g_gate_config_valid = false;
std::array<std::uint8_t, 6> g_device_mac{};
std::uint32_t g_boot_nonce = 0;
bool g_pending_valid = false;
std::uint32_t g_pending_expected_floor = 0;
std::uint32_t g_commit_nonce = 0;
CalibrationRecord g_pending_record{};
std::array<std::uint8_t, forgesense::sensing::kCalibrationBlobSize> g_pending_blob{};

std::uint16_t read_le16(const std::uint8_t* data) {
    return static_cast<std::uint16_t>(
        static_cast<std::uint16_t>(data[0]) |
        (static_cast<std::uint16_t>(data[1]) << 8U));
}

std::uint32_t read_le32(const std::uint8_t* data) {
    return static_cast<std::uint32_t>(data[0]) |
           (static_cast<std::uint32_t>(data[1]) << 8U) |
           (static_cast<std::uint32_t>(data[2]) << 16U) |
           (static_cast<std::uint32_t>(data[3]) << 24U);
}

void write_le32(std::uint8_t* out, std::uint32_t value) {
    out[0] = static_cast<std::uint8_t>(value & 0xFFU);
    out[1] = static_cast<std::uint8_t>((value >> 8U) & 0xFFU);
    out[2] = static_cast<std::uint8_t>((value >> 16U) & 0xFFU);
    out[3] = static_cast<std::uint8_t>((value >> 24U) & 0xFFU);
}

void clear_pending() {
    g_pending_valid = false;
    g_pending_expected_floor = 0;
    g_commit_nonce = 0;
    g_pending_record = {};
    g_pending_blob.fill(0);
}

std::uint32_t fresh_nonce() {
    std::uint32_t value = 0;
    while (value == 0U || value == 0xFFFFFFFFU) {
        value = esp_random();
    }
    return value;
}

bool configure_input_gpio(int pin) {
    if (pin < 0 || pin > 48) {
        return false;
    }
    gpio_config_t config{};
    config.pin_bit_mask = 1ULL << static_cast<unsigned>(pin);
    config.mode = GPIO_MODE_INPUT;
    config.pull_up_en = GPIO_PULLUP_DISABLE;
    config.pull_down_en = GPIO_PULLDOWN_DISABLE;
    config.intr_type = GPIO_INTR_DISABLE;
    return gpio_config(&config) == ESP_OK;
}

bool gate_asserted(int pin, int active_level) {
    if (!g_gate_config_valid || pin < 0) {
        return false;
    }
    return gpio_get_level(static_cast<gpio_num_t>(pin)) == active_level;
}

bool maintenance_asserted() {
    return gate_asserted(
        CONFIG_FORGESENSE_MAINTENANCE_ENABLE_GPIO,
        CONFIG_FORGESENSE_MAINTENANCE_ENABLE_ACTIVE_LEVEL);
}

bool load_inhibit_asserted() {
    return gate_asserted(
        CONFIG_FORGESENSE_LOAD_INHIBIT_SENSE_GPIO,
        CONFIG_FORGESENSE_LOAD_INHIBIT_ACTIVE_LEVEL);
}

bool physical_gates_asserted() {
    return maintenance_asserted() && load_inhibit_asserted();
}

void write_all_usb(const std::uint8_t* data, std::size_t size) {
    std::size_t offset = 0;
    while (offset < size) {
        const int written = usb_serial_jtag_write_bytes(
            data + offset, size - offset, pdMS_TO_TICKS(100));
        if (written > 0) {
            offset += static_cast<std::size_t>(written);
        } else {
            vTaskDelay(pdMS_TO_TICKS(1));
        }
    }
}

void send_response(
    MaintenanceOpcode opcode,
    const std::uint8_t* payload,
    std::size_t payload_size) {
    std::array<std::uint8_t, forgesense::maintenance::kMaintenanceMaxFrameSize> encoded{};
    std::size_t encoded_size = 0;
    if (!forgesense::maintenance::encode_maintenance_frame(
            static_cast<std::uint8_t>(opcode), payload, payload_size, encoded, encoded_size)) {
        return;
    }
    write_all_usb(encoded.data(), encoded_size);
}

void send_status_only(MaintenanceOpcode opcode, MaintenanceStatus status) {
    const std::uint8_t payload[1] = {static_cast<std::uint8_t>(status)};
    send_response(opcode, payload, sizeof(payload));
}

std::uint32_t record_crc32(const CalibrationRecord& record) {
    std::array<std::uint8_t, forgesense::sensing::kCalibrationBlobSize> encoded{};
    if (!forgesense::sensing::encode_calibration_record(record, encoded)) {
        return 0;
    }
    return read_le32(encoded.data() + 44U);
}

void handle_query_status() {
    std::array<std::uint8_t, kStatusPayloadSize> payload{};
    payload[0] = static_cast<std::uint8_t>(MaintenanceStatus::Ok);
    std::memcpy(payload.data() + 1U, g_device_mac.data(), g_device_mac.size());
    write_le32(payload.data() + 7U, g_boot_nonce);
    payload[11] = maintenance_asserted() ? 1U : 0U;
    payload[12] = load_inhibit_asserted() ? 1U : 0U;
    payload[13] = g_store_ready ? 1U : 0U;
    payload[14] = (g_store_ready && g_store.has_active()) ? 1U : 0U;
    write_le32(payload.data() + 15U, g_store_ready ? g_store.installed_floor() : 0U);

    std::uint32_t active_crc = 0;
    CalibrationRecord active{};
    if (g_store_ready && g_store.load_active(active)) {
        active_crc = record_crc32(active);
    }
    write_le32(payload.data() + 19U, active_crc);
    write_le32(payload.data() + 23U, g_pending_valid ? g_pending_record.sequence : 0U);
    send_response(MaintenanceOpcode::StatusResponse, payload.data(), payload.size());
}

void handle_query_authorization() {
    std::array<std::uint8_t, kAuthorizationStatusPayloadSize> payload{};
    payload[0] = static_cast<std::uint8_t>(MaintenanceStatus::Ok);
    payload[1] = g_authorization.ready() ? 1U : 0U;
    if (g_authorization.ready()) {
        const auto& fingerprint = g_authorization.public_key_sha256();
        std::memcpy(payload.data() + 2U, fingerprint.data(), fingerprint.size());
    }
    send_response(MaintenanceOpcode::AuthorizationResponse, payload.data(), payload.size());
}

void handle_prepare(const MaintenanceFrame& frame) {
    if (frame.payload_size <= kPrepareFixedRequestSize ||
        frame.payload_size >
            kPrepareFixedRequestSize + forgesense::maintenance::kAuthorizationMaxSignatureSize) {
        clear_pending();
        send_status_only(MaintenanceOpcode::PrepareResponse, MaintenanceStatus::BadRequest);
        return;
    }
    if (!physical_gates_asserted()) {
        clear_pending();
        send_status_only(MaintenanceOpcode::PrepareResponse, MaintenanceStatus::PhysicalGateOpen);
        return;
    }
    if (!g_store_ready) {
        clear_pending();
        send_status_only(MaintenanceOpcode::PrepareResponse, MaintenanceStatus::StoreUnavailable);
        return;
    }
    if (!g_authorization.ready()) {
        clear_pending();
        send_status_only(
            MaintenanceOpcode::PrepareResponse,
            MaintenanceStatus::AuthorizationUnavailable);
        return;
    }

    const std::uint32_t boot_nonce = read_le32(frame.payload.data());
    const std::uint32_t expected_floor = read_le32(frame.payload.data() + 4U);
    if (boot_nonce != g_boot_nonce) {
        clear_pending();
        send_status_only(MaintenanceOpcode::PrepareResponse, MaintenanceStatus::SessionMismatch);
        return;
    }
    if (expected_floor != g_store.installed_floor()) {
        clear_pending();
        send_status_only(MaintenanceOpcode::PrepareResponse, MaintenanceStatus::SequenceMismatch);
        return;
    }

    std::array<std::uint8_t, forgesense::maintenance::kAuthorizationArtifactRootSize>
        artifact_root{};
    std::memcpy(artifact_root.data(), frame.payload.data() + 8U, artifact_root.size());
    const std::uint8_t* record_bytes = frame.payload.data() + 40U;
    const std::uint16_t signature_size = read_le16(frame.payload.data() + 88U);
    if (signature_size == 0U ||
        signature_size > forgesense::maintenance::kAuthorizationMaxSignatureSize ||
        frame.payload_size != kPrepareFixedRequestSize + signature_size) {
        clear_pending();
        send_status_only(MaintenanceOpcode::PrepareResponse, MaintenanceStatus::BadRequest);
        return;
    }

    CalibrationRecord decoded{};
    if (!forgesense::sensing::decode_calibration_record(
            record_bytes, forgesense::sensing::kCalibrationBlobSize, decoded) ||
        !forgesense::sensing::calibration_sequence_is_newer(decoded.sequence, expected_floor)) {
        clear_pending();
        send_status_only(MaintenanceOpcode::PrepareResponse, MaintenanceStatus::RecordInvalid);
        return;
    }

    const std::uint8_t* signature_der = frame.payload.data() + kPrepareFixedRequestSize;
    if (!g_authorization.verify(
            g_device_mac,
            expected_floor,
            artifact_root,
            record_bytes,
            forgesense::sensing::kCalibrationBlobSize,
            signature_der,
            signature_size)) {
        clear_pending();
        send_status_only(
            MaintenanceOpcode::PrepareResponse,
            MaintenanceStatus::AuthorizationFailed);
        return;
    }

    g_pending_record = decoded;
    std::memcpy(g_pending_blob.data(), record_bytes, g_pending_blob.size());
    g_pending_expected_floor = expected_floor;
    g_commit_nonce = fresh_nonce();
    g_pending_valid = true;

    std::array<std::uint8_t, kPrepareResponseSize> payload{};
    payload[0] = static_cast<std::uint8_t>(MaintenanceStatus::Ok);
    write_le32(payload.data() + 1U, decoded.sequence);
    write_le32(payload.data() + 5U, read_le32(record_bytes + 44U));
    write_le32(payload.data() + 9U, g_commit_nonce);
    send_response(MaintenanceOpcode::PrepareResponse, payload.data(), payload.size());
}

void handle_commit(const MaintenanceFrame& frame) {
    if (frame.payload_size != kCommitRequestSize) {
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::BadRequest);
        return;
    }
    if (!physical_gates_asserted()) {
        clear_pending();
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::PhysicalGateOpen);
        return;
    }
    if (!g_store_ready) {
        clear_pending();
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::StoreUnavailable);
        return;
    }
    if (!g_authorization.ready()) {
        clear_pending();
        send_status_only(
            MaintenanceOpcode::CommitResponse,
            MaintenanceStatus::AuthorizationUnavailable);
        return;
    }

    const std::uint32_t boot_nonce = read_le32(frame.payload.data());
    const std::uint32_t commit_nonce = read_le32(frame.payload.data() + 4U);
    const std::uint32_t expected_pending_sequence = read_le32(frame.payload.data() + 8U);
    if (boot_nonce != g_boot_nonce) {
        clear_pending();
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::SessionMismatch);
        return;
    }
    if (!g_pending_valid || commit_nonce != g_commit_nonce ||
        expected_pending_sequence != g_pending_record.sequence) {
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::PendingMismatch);
        return;
    }
    if (g_store.installed_floor() != g_pending_expected_floor ||
        !forgesense::sensing::calibration_sequence_is_newer(
            g_pending_record.sequence, g_store.installed_floor())) {
        clear_pending();
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::SequenceMismatch);
        return;
    }

    if (!g_store.stage_and_commit(g_pending_record)) {
        clear_pending();
        g_store_ready = false;
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::CommitFailed);
        return;
    }

    CalibrationRecord active{};
    std::array<std::uint8_t, forgesense::sensing::kCalibrationBlobSize> active_blob{};
    if (!g_store.load_active(active) ||
        !forgesense::sensing::encode_calibration_record(active, active_blob) ||
        active_blob != g_pending_blob) {
        clear_pending();
        g_store_ready = false;
        send_status_only(MaintenanceOpcode::CommitResponse, MaintenanceStatus::CommitFailed);
        return;
    }

    const std::uint32_t installed_sequence = active.sequence;
    const std::uint32_t installed_crc = read_le32(active_blob.data() + 44U);
    clear_pending();

    std::array<std::uint8_t, kCommitResponseSize> payload{};
    payload[0] = static_cast<std::uint8_t>(MaintenanceStatus::Ok);
    write_le32(payload.data() + 1U, installed_sequence);
    write_le32(payload.data() + 5U, installed_crc);
    send_response(MaintenanceOpcode::CommitResponse, payload.data(), payload.size());
}

void handle_frame(const MaintenanceFrame& frame) {
    switch (static_cast<MaintenanceOpcode>(frame.opcode)) {
        case MaintenanceOpcode::QueryStatus:
            if (frame.payload_size == 0U) {
                handle_query_status();
            } else {
                send_status_only(MaintenanceOpcode::StatusResponse, MaintenanceStatus::BadRequest);
            }
            break;
        case MaintenanceOpcode::PrepareRecord:
            handle_prepare(frame);
            break;
        case MaintenanceOpcode::CommitRecord:
            handle_commit(frame);
            break;
        case MaintenanceOpcode::QueryAuthorization:
            if (frame.payload_size == 0U) {
                handle_query_authorization();
            } else {
                send_status_only(
                    MaintenanceOpcode::AuthorizationResponse,
                    MaintenanceStatus::BadRequest);
            }
            break;
        default:
            send_status_only(MaintenanceOpcode::StatusResponse, MaintenanceStatus::BadRequest);
            break;
    }
}

}  // namespace

extern "C" void app_main(void) {
    usb_serial_jtag_driver_config_t usb_config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    usb_config.rx_buffer_size = 1024;
    usb_config.tx_buffer_size = 1024;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb_config));

    const int maintenance_gpio = CONFIG_FORGESENSE_MAINTENANCE_ENABLE_GPIO;
    const int inhibit_gpio = CONFIG_FORGESENSE_LOAD_INHIBIT_SENSE_GPIO;
    g_gate_config_valid =
        maintenance_gpio >= 0 && inhibit_gpio >= 0 && maintenance_gpio != inhibit_gpio &&
        configure_input_gpio(maintenance_gpio) && configure_input_gpio(inhibit_gpio);

    const bool identity_ready = esp_efuse_mac_get_default(g_device_mac.data()) == ESP_OK;
    if (!identity_ready) {
        g_gate_config_valid = false;
    }
    const bool authorization_ready =
        identity_ready &&
        g_authorization.begin(CONFIG_FORGESENSE_MAINTENANCE_AUTHORITY_PUBKEY_DER_HEX);
    if (!authorization_ready) {
        clear_pending();
    }
    g_boot_nonce = fresh_nonce();

    const esp_err_t nvs_result = nvs_flash_init();
    if (identity_ready && nvs_result == ESP_OK) {
        g_store_ready = g_store.begin();
    } else {
        // Deliberately do not erase NVS on initialization errors. Calibration
        // state is evidence-bearing persistent data and failures are fail-closed.
        g_store_ready = false;
    }

    MaintenanceFrameParser parser;
    std::array<std::uint8_t, kUsbReadBufferSize> buffer{};
    while (true) {
        const int received = usb_serial_jtag_read_bytes(
            buffer.data(), buffer.size(), pdMS_TO_TICKS(50));
        if (received <= 0) {
            continue;
        }
        for (int index = 0; index < received; ++index) {
            MaintenanceFrame frame{};
            if (parser.feed(buffer[static_cast<std::size_t>(index)], frame)) {
                handle_frame(frame);
            }
        }
    }
}
