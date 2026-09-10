idf_component_register(
    SRCS
        "app_main.cpp"
        "link_service.cpp"
        "event_store_nvs.cpp"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_timer
        nvs_flash
        forgesense_protocol
        forgesense_inference
        forgesense_events
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_20)
