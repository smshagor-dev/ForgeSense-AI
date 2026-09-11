idf_component_register(
    SRCS
        "forgesense_sensing.cpp"
        "forgesense_calibration.cpp"
        "forgesense_calibration_provisioning.cpp"
        "forgesense_phy.cpp"
    INCLUDE_DIRS "include"
)

target_compile_features(${COMPONENT_LIB} PRIVATE cxx_std_20)
