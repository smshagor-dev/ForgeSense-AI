# ForgeSense Tang Nano 9K first-bitstream smoke build.
# Run from repository root with: gw_sh fpga/scripts/tang_nano_9k_smoke_build.tcl

set_device GW1NR-LV9QN88PC6/I5

add_file fpga/constraints/tang_nano_9k.cst
add_file fpga/constraints/tang_nano_9k.sdc
add_file fpga/rtl/io/uart_rx.vhd
add_file fpga/rtl/io/uart_tx.vhd
add_file fpga/rtl/top/forgesense_tang_nano_9k_smoke_top.vhd

set_option -top_module forgesense_tang_nano_9k_smoke_top
run all
