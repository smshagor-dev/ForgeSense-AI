#include <array>
#include <cstddef>
#include <cstdint>

#include "driver/uart.h"
#include "driver/usb_serial_jtag.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace {

constexpr uart_port_t kFpgaUart = UART_NUM_1;
constexpr int kFpgaTxGpio = 17;
constexpr int kFpgaRxGpio = 18;
constexpr int kBaud = 115200;
constexpr std::size_t kBufferSize = 512;

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

void write_all_uart(const std::uint8_t* data, std::size_t size) {
    std::size_t offset = 0;
    while (offset < size) {
        const int written = uart_write_bytes(
            kFpgaUart, data + offset, size - offset);
        if (written > 0) {
            offset += static_cast<std::size_t>(written);
        } else {
            vTaskDelay(pdMS_TO_TICKS(1));
        }
    }
}

void usb_to_fpga_task(void*) {
    std::array<std::uint8_t, kBufferSize> buffer{};
    while (true) {
        const int received = usb_serial_jtag_read_bytes(
            buffer.data(), buffer.size(), pdMS_TO_TICKS(20));
        if (received > 0) {
            write_all_uart(buffer.data(), static_cast<std::size_t>(received));
        }
    }
}

void fpga_to_usb_task(void*) {
    std::array<std::uint8_t, kBufferSize> buffer{};
    while (true) {
        const int received = uart_read_bytes(
            kFpgaUart, buffer.data(), buffer.size(), pdMS_TO_TICKS(20));
        if (received > 0) {
            write_all_usb(buffer.data(), static_cast<std::size_t>(received));
        }
    }
}

}  // namespace

extern "C" void app_main(void) {
    const uart_config_t uart_config = {
        .baud_rate = kBaud,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    ESP_ERROR_CHECK(uart_driver_install(kFpgaUart, 2048, 2048, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(kFpgaUart, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(
        kFpgaUart,
        kFpgaTxGpio,
        kFpgaRxGpio,
        UART_PIN_NO_CHANGE,
        UART_PIN_NO_CHANGE));

    usb_serial_jtag_driver_config_t usb_config = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    usb_config.rx_buffer_size = 1024;
    usb_config.tx_buffer_size = 1024;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb_config));

    xTaskCreate(usb_to_fpga_task, "usb_to_fpga", 3072, nullptr, 10, nullptr);
    xTaskCreate(fpga_to_usb_task, "fpga_to_usb", 3072, nullptr, 10, nullptr);
}
