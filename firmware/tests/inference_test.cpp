#include "forgesense_inference.h"

#include <cassert>
#include <iostream>

int main() {
    using namespace forgesense;

    EdgeInferenceRuntime runtime;
    MlObservation observation{};

    SensorSnapshot normal{};
    normal.temperature_deci_c = 284;
    normal.vibration_milli_g = 138;
    normal.current_milli_a = 1457;
    normal.flags = kSensorAllValid;

    for (std::size_t i = 0; i < EdgeInferenceRuntime::kWindowSize - 1; ++i) {
        assert(!runtime.ingest(normal, observation));
    }
    assert(runtime.ingest(normal, observation));
    assert(observation.health_class == HealthClass::Normal);
    assert(observation.model_id == 1);
    assert(observation.feature_schema_version == 1);

    SensorSnapshot invalid = normal;
    invalid.flags = kSensorValidTemperature | kSensorValidCurrent;
    assert(!runtime.ingest(invalid, observation));
    assert(!runtime.ready());

    EdgeInferenceRuntime severe_runtime;
    SensorSnapshot severe{};
    severe.temperature_deci_c = 350;
    severe.vibration_milli_g = 800;
    severe.current_milli_a = 2200;
    severe.flags = kSensorAllValid;
    for (std::size_t i = 0; i < EdgeInferenceRuntime::kWindowSize; ++i) {
        (void)severe_runtime.ingest(severe, observation);
    }
    assert(observation.health_class == HealthClass::Critical);
    assert(observation.anomaly_q15 > 30000);

    std::cout << "firmware inference tests PASS\n";
    return 0;
}
