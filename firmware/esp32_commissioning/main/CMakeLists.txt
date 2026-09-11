idf_component_register(
    SRCS "app_main.cpp"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_driver_usb_serial_jtag
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_20)
