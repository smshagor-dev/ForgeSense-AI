#include "event_store_nvs.hpp"
#include "forgesense_events.h"
#include "forgesense_inference.h"
#include "link_service.hpp"

#include "esp_log.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

#include <algorithm>
#include <cstdint>

namespace {

constexpr char kTag[] = "forgesense";

std::uint32_t now_ms() {
    return static_cast<std::uint32_t>(
        static_cast<std::uint64_t>(esp_timer_get_time() / 1000) & 0xFFFFFFFFU);
}

forgesense::EventRecord make_event(
    forgesense::EventSeverity severity,
    forgesense::EventSource source,
    forgesense::EventCode code,
    const forgesense::SensorSnapshot& snapshot,
    std::uint16_t anomaly_q15 = 0,
    std::uint32_t detail = 0,
    std::uint8_t state_code = 0xFF,
    std::uint8_t flags = 0) {
    forgesense::EventRecord record{};
    record.severity = severity;
    record.source = source;
    record.code = code;
    record.monotonic_ms = now_ms();
    record.state_code = state_code;
    record.flags = flags;
    record.snapshot = snapshot;
    record.anomaly_q15 = anomaly_q15;
    record.detail = detail;
    return record;
}

bool initialize_nvs() {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES ||
        err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        if (nvs_flash_erase() != ESP_OK) {
            return false;
        }
        err = nvs_flash_init();
    }
    return err == ESP_OK;
}

}  // namespace

extern "C" void app_main(void) {
    using namespace forgesense;
    using namespace forgesense::edge;

    if (!initialize_nvs()) {
        ESP_LOGE(kTag, "NVS initialization failed");
        return;
    }

    LinkService link;
    NvsEventStore events;
    EdgeInferenceRuntime inference(reference_simulation_model());

    if (!events.begin()) {
        ESP_LOGE(kTag, "event store initialization failed");
        return;
    }
    if (!link.begin()) {
        ESP_LOGE(kTag, "FPGA UART link initialization failed");
        return;
    }

    SensorSnapshot last_sensor{};
    (void)events.append(make_event(
        EventSeverity::Info,
        EventSource::System,
        EventCode::Boot,
        last_sensor));

    std::uint16_t ml_sequence = 0;
    std::uint32_t last_sensor_rx_ms = now_ms();
    bool link_loss_logged = false;
    bool sensor_invalid_logged = false;
    HealthClass previous_health = HealthClass::Abstain;
    std::uint16_t previous_safety_flags = 0;
    std::uint8_t previous_state_code = 0xFF;

    ESP_LOGI(kTag, "edge runtime started");

    while (true) {
        ParsedFpgaMessage message{};
        if (!link.receive(message, 100)) {
            const std::uint32_t age_ms = now_ms() - last_sensor_rx_ms;
            if (age_ms >= CONFIG_FORGESENSE_LINK_LOSS_MS && !link_loss_logged) {
                inference.reset();
                (void)events.append(make_event(
                    EventSeverity::Critical,
                    EventSource::Link,
                    EventCode::LinkLost,
                    last_sensor,
                    0,
                    age_ms));
                link_loss_logged = true;
                ESP_LOGW(kTag, "sensor link timeout");
            }
            continue;
        }

        if (message.kind == FpgaMessageKind::Status) {
            const auto& status = message.status.status;
            const bool hard_critical_now =
                (status.safety_flags & kSafetyHardCritical) != 0;
            const bool hard_critical_before =
                (previous_safety_flags & kSafetyHardCritical) != 0;
            const bool emergency_now =
                (status.safety_flags & kSafetyEmergency) != 0;
            const bool emergency_before =
                (previous_safety_flags & kSafetyEmergency) != 0;

            if (hard_critical_now && !hard_critical_before) {
                (void)events.append(make_event(
                    EventSeverity::Critical,
                    EventSource::Fpga,
                    EventCode::HardCritical,
                    last_sensor,
                    0,
                    status.safety_flags,
                    status.state_code,
                    status.control_flags));
            }
            if (emergency_now && !emergency_before) {
                (void)events.append(make_event(
                    EventSeverity::Critical,
                    EventSource::Fpga,
                    EventCode::Emergency,
                    last_sensor,
                    0,
                    status.safety_flags,
                    status.state_code,
                    status.control_flags));
            }
            if (status.state_code == 5 && previous_state_code != 5) {
                (void)events.append(make_event(
                    EventSeverity::Info,
                    EventSource::Fpga,
                    EventCode::Recovery,
                    last_sensor,
                    0,
                    status.safety_flags,
                    status.state_code,
                    status.control_flags));
            }

            previous_safety_flags = status.safety_flags;
            previous_state_code = status.state_code;
            continue;
        }

        const ParsedSensorFrame& sensor_frame = message.sensor;
        last_sensor = sensor_frame.snapshot;
        last_sensor_rx_ms = now_ms();
        if (link_loss_logged) {
            (void)events.append(make_event(
                EventSeverity::Info,
                EventSource::Link,
                EventCode::LinkRecovered,
                sensor_frame.snapshot));
            link_loss_logged = false;
        }

        if (!sensor_frame.snapshot.all_valid()) {
            inference.reset();
            if (!sensor_invalid_logged) {
                (void)events.append(make_event(
                    EventSeverity::Critical,
                    EventSource::Fpga,
                    EventCode::SensorInvalid,
                    sensor_frame.snapshot,
                    0,
                    sensor_frame.snapshot.flags));
                sensor_invalid_logged = true;
            }
            continue;
        }
        sensor_invalid_logged = false;

        const std::uint32_t received_ms = now_ms();
        MlObservation observation{};
        if (!inference.ingest(sensor_frame.snapshot, observation)) {
            continue;
        }

        const std::uint32_t processing_age_ms = now_ms() - received_ms;
        observation.inference_age_ms = static_cast<std::uint16_t>(
            std::min<std::uint32_t>(processing_age_ms, 0xFFFFU));

        if (!link.send_observation(observation, ml_sequence, now_ms())) {
            ESP_LOGW(kTag, "failed to transmit ML observation");
            continue;
        }
        ml_sequence = static_cast<std::uint16_t>(ml_sequence + 1U);

        if (observation.health_class != previous_health) {
            if (observation.health_class == HealthClass::Warning) {
                (void)events.append(make_event(
                    EventSeverity::Warning,
                    EventSource::Edge,
                    EventCode::MlWarning,
                    sensor_frame.snapshot,
                    observation.anomaly_q15));
            } else if (observation.health_class == HealthClass::Critical) {
                (void)events.append(make_event(
                    EventSeverity::Critical,
                    EventSource::Edge,
                    EventCode::MlCritical,
                    sensor_frame.snapshot,
                    observation.anomaly_q15));
            }
            previous_health = observation.health_class;
        }
    }
}
