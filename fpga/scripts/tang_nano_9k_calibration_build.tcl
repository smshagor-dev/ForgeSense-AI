# ForgeSense Tang Nano 9K read-only calibration diagnostic build.
# Run from repository root with: gw_sh fpga/scripts/tang_nano_9k_calibration_build.tcl

set_device GW1NR-LV9QN88PC6/I5

add_file fpga/constraints/tang_nano_9k.cst
add_file fpga/constraints/tang_nano_9k.sdc
add_file fpga/rtl/protocol/crc16_ccitt_pkg.vhd
add_file fpga/rtl/io/i2c_byte_engine.vhd
add_file fpga/rtl/io/spi_mode0_byte_engine.vhd
add_file fpga/rtl/io/spi_mode1_byte_engine.vhd
add_file fpga/rtl/io/uart_tx.vhd
add_file fpga/rtl/sensing/sample_scheduler.vhd
add_file fpga/rtl/sensing/timebase_ms.vhd
add_file fpga/rtl/sensing/sensor_device_math_pkg.vhd
add_file fpga/rtl/sensing/tmp117_controller.vhd
add_file fpga/rtl/sensing/adxl355_controller.vhd
add_file fpga/rtl/sensing/ads131m02_controller.vhd
add_file fpga/rtl/protocol/calibration_diag_tx.vhd
add_file fpga/rtl/top/forgesense_tang_nano_9k_calibration_top.vhd

set_option -top_module forgesense_tang_nano_9k_calibration_top
run all
