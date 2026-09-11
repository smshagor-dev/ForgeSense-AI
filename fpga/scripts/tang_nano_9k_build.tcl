# ForgeSense AI Tang Nano 9K Gowin command-line build.
# Run from repository root with: gw_sh fpga/scripts/tang_nano_9k_build.tcl

set_device GW1NR-LV9QN88PC6/I5

add_file fpga/constraints/tang_nano_9k.cst
add_file fpga/constraints/tang_nano_9k.sdc

# Packages and low-level primitives first.
add_file fpga/rtl/safety/safety_pkg.vhd
add_file fpga/rtl/protocol/crc16_ccitt_pkg.vhd
add_file fpga/rtl/sensing/sensor_contract_pkg.vhd
add_file fpga/rtl/sensing/sensor_device_math_pkg.vhd
add_file fpga/rtl/sensing/sensor_phy_diagnostics_pkg.vhd

add_file fpga/rtl/io/input_sync.vhd
add_file fpga/rtl/io/uart_rx.vhd
add_file fpga/rtl/io/uart_tx.vhd
add_file fpga/rtl/io/link_tx_arbiter.vhd
add_file fpga/rtl/io/spi_mode0_byte_engine.vhd
add_file fpga/rtl/io/spi_mode1_byte_engine.vhd
add_file fpga/rtl/io/i2c_byte_engine.vhd

add_file fpga/rtl/safety/watchdog.vhd
add_file fpga/rtl/safety/hard_limit_monitor.vhd
add_file fpga/rtl/safety/safety_fsm.vhd

add_file fpga/rtl/protocol/link_receiver.vhd
add_file fpga/rtl/protocol/intelligence_gate.vhd
add_file fpga/rtl/protocol/sensor_link_tx.vhd
add_file fpga/rtl/protocol/status_link_tx.vhd

add_file fpga/rtl/sensing/linear_sensor_adapter.vhd
add_file fpga/rtl/sensing/vibration_rms_window.vhd
add_file fpga/rtl/sensing/sensor_frontend.vhd
add_file fpga/rtl/sensing/sensor_supervisor.vhd
add_file fpga/rtl/sensing/generic_adc_sample_adapter.vhd
add_file fpga/rtl/sensing/digital_temperature_adapter.vhd
add_file fpga/rtl/sensing/accelerometer_conditioner.vhd
add_file fpga/rtl/sensing/sensor_self_test.vhd
add_file fpga/rtl/sensing/sample_scheduler.vhd
add_file fpga/rtl/sensing/timebase_ms.vhd
add_file fpga/rtl/sensing/tmp117_controller.vhd
add_file fpga/rtl/sensing/adxl355_controller.vhd
add_file fpga/rtl/sensing/ads131m02_controller.vhd

add_file fpga/rtl/top/safety_core.vhd
add_file fpga/rtl/top/forgesense_core.vhd
add_file fpga/rtl/top/forgesense_platform_core.vhd
add_file fpga/rtl/top/forgesense_board_core.vhd
add_file fpga/rtl/top/forgesense_sensor_board_core.vhd
add_file fpga/rtl/top/forgesense_phy_board_core.vhd
add_file fpga/rtl/top/forgesense_reference_sensor_io.vhd
add_file fpga/rtl/top/forgesense_tang_nano_9k_top.vhd

set_option -top_module forgesense_tang_nano_9k_top
run all
