idf_component_register(
    SRCS "forgesense_telemetry.cpp"
    INCLUDE_DIRS "include"
    REQUIRES forgesense_protocol
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_20)
