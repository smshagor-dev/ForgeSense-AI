#include "link_service.hpp"

#include "driver/uart.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "sdkconfig.h"

#include <array>

namespace forgesense::edge {

void LinkService::enqueue(const ParsedFpgaMessage& message) {
    if (pending_count_ == kPendingCapacity) {
        pending_head_ = (pending_head_ + 1U) % kPendingCapacity;
        --pending_count_;
        ++dropped_pending_messages_;
    }
    const std::size_t tail =
        (pending_head_ + pending_count_) % kPendingCapacity;
    pending_[tail] = message;
    ++pending_count_;
}

bool LinkService::dequeue(ParsedFpgaMessage& out) {
    if (pending_count_ == 0) {
        return false;
    }
    out = pending_[pending_head_];
    pending_head_ = (pending_head_ + 1U) % kPendingCapacity;
    --pending_count_;
    return true;
}

bool LinkService::begin() {
    uart_port_ = CONFIG_FORGESENSE_UART_PORT;
    const auto port = static_cast<uart_port_t>(uart_port_);

    uart_config_t config{};
    config.baud_rate = CONFIG_FORGESENSE_UART_BAUD;
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;

    if (uart_param_config(port, &config) != ESP_OK) {
        return false;
    }
    if (uart_set_pin(
            port,
            CONFIG_FORGESENSE_UART_TX_GPIO,
            CONFIG_FORGESENSE_UART_RX_GPIO,
            UART_PIN_NO_CHANGE,
            UART_PIN_NO_CHANGE) != ESP_OK) {
        return false;
    }
    return uart_driver_install(port, 2048, 2048, 0, nullptr, 0) == ESP_OK;
}

bool LinkService::receive(
    ParsedFpgaMessage& out,
    std::uint32_t timeout_ms) {
    if (dequeue(out)) {
        return true;
    }
    if (uart_port_ < 0) {
        return false;
    }

    std::array<std::uint8_t, 96> bytes{};
    const int count = uart_read_bytes(
        static_cast<uart_port_t>(uart_port_),
        bytes.data(),
        bytes.size(),
        pdMS_TO_TICKS(timeout_ms));
    if (count <= 0) {
        return false;
    }

    ParsedFpgaMessage candidate{};
    for (int i = 0; i < count; ++i) {
        const auto event = fpga_decoder_.push(
            bytes[static_cast<std::size_t>(i)], candidate);
        if (event != StreamEvent::Frame) {
            continue;
        }

        if (candidate.kind == FpgaMessageKind::Sensor) {
            if (!sensor_sequence_gate_.accept(candidate.sensor.sequence)) {
                ++stale_sensor_frames_;
                continue;
            }
        } else {
            if (!status_sequence_gate_.accept(candidate.status.sequence)) {
                ++stale_status_frames_;
                continue;
            }
        }
        enqueue(candidate);
    }
    return dequeue(out);
}

bool LinkService::send_observation(
    const MlObservation& observation,
    std::uint16_t sequence,
    std::uint32_t timestamp_ms) {
    if (uart_port_ < 0) {
        return false;
    }

    std::array<std::uint8_t, kMlFrameSize> frame{};
    if (!encode_ml_frame(observation, sequence, timestamp_ms, frame)) {
        return false;
    }
    const int written = uart_write_bytes(
        static_cast<uart_port_t>(uart_port_),
        frame.data(),
        frame.size());
    return written == static_cast<int>(frame.size());
}

}  // namespace forgesense::edge
