idf_component_register(
    SRCS
        "app_main.cpp"
        "calibration_store_nvs.cpp"
        "maintenance_authorization.cpp"
        "maintenance_protocol.cpp"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_driver_usb_serial_jtag
        esp_hw_support
        esp_system
        mbedtls
        nvs_flash
        forgesense_sensing
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_20)
