#include <array>
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

void usb_to_fpga_task(void*) {
    std::array<std::uint8_t, kBufferSize> buffer{};
    while (true) {
        const int received = usb_serial_jtag_read_bytes(
            buffer.data(), buffer.size(), pdMS_TO_TICKS(20));
        if (received > 0) {
            uart_write_bytes(kFpgaUart, buffer.data(), received);
        }
    }
}

void fpga_to_usb_task(void*) {
    std::array<std::uint8_t, kBufferSize> buffer{};
    while (true) {
        const int received = uart_read_bytes(
            kFpgaUart, buffer.data(), buffer.size(), pdMS_TO_TICKS(20));
        if (received > 0) {
            usb_serial_jtag_write_bytes(
                buffer.data(), static_cast<std::size_t>(received), pdMS_TO_TICKS(20));
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
        .rx_flow_ctrl_thresh = 0,
        .source_clk = UART_SCLK_DEFAULT,
        .flags = {},
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
