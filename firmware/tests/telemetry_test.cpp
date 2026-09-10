#include "forgesense_telemetry.h"

#include <array>
#include <cassert>
#include <iostream>
#include <string_view>

int main() {
    using namespace forgesense;
    DeviceTelemetrySnapshot telemetry;
    std::array<char, kDeviceTelemetryMaxLine> line{};
    const auto empty_size = telemetry.encode_line(100, line.data(), line.size());
    assert(empty_size > 0);
    std::string_view empty(line.data(), empty_size);
    assert(empty.starts_with("@FS1 {\"schema\":\"forgesense.edge.telemetry.v1\""));
    assert(empty.find("\"sensor\":null") != std::string_view::npos);

    ParsedSensorFrame sensor{};
    sensor.sequence = 9; sensor.timestamp_ms = 1000;
    sensor.snapshot.temperature_deci_c = -25;
    sensor.snapshot.vibration_milli_g = 321;
    sensor.snapshot.current_milli_a = 1450;
    sensor.snapshot.flags = kSensorAllValid;
    telemetry.ingest_sensor(sensor, 1100);

    ParsedStatusFrame status{};
    status.sequence = 4; status.timestamp_ms = 1050;
    status.status.state_code = 2;
    status.status.control_flags = kStatusLoadEnable | kStatusWarningActive | kStatusOperationalReady;
    status.status.safety_flags = kSafetyHardWarning | kSafetySensorsValid;
    telemetry.ingest_status(status, 1120);

    MlObservation ml{};
    ml.model_id = 1; ml.model_version = 3; ml.feature_schema_version = 2;
    ml.flags = kValidObservation; ml.anomaly_q15 = 23456;
    ml.health_class = HealthClass::Warning; ml.confidence_q8 = 201; ml.inference_age_ms = 14;
    telemetry.ingest_ml(ml, 77, 1150, 1160);
    telemetry.set_link_counters({55, 3, 2, 1, 4});

    const auto size = telemetry.encode_line(1200, line.data(), line.size());
    assert(size > 0);
    const std::string_view payload(line.data(), size);
    assert(payload.find("\"revision\":4") != std::string_view::npos);
    assert(payload.find("\"temperature_deci_c\":-25") != std::string_view::npos);
    assert(payload.find("\"state_code\":2") != std::string_view::npos);
    assert(payload.find("\"anomaly_q15\":23456") != std::string_view::npos);
    assert(payload.find("\"accepted_fpga_frames\":55") != std::string_view::npos);
    assert(payload.back() == '\n');

    const auto revision = telemetry.revision();
    telemetry.set_link_counters({55, 3, 2, 1, 4});
    assert(telemetry.revision() == revision);

    std::array<char, 32> too_small{};
    assert(telemetry.encode_line(1200, too_small.data(), too_small.size()) == 0);
    assert(too_small.back() == '\0');

    DeviceTelemetrySnapshot wrap;
    sensor.sequence = 10;
    wrap.ingest_sensor(sensor, 0xFFFFFFF0U);
    const auto wrap_size = wrap.encode_line(0x00000010U, line.data(), line.size());
    assert(wrap_size > 0);
    assert(std::string_view(line.data(), wrap_size).find("\"received_age_ms\":32") != std::string_view::npos);

    std::cout << "telemetry_test PASS\n";
    return 0;
}
