#include "event_store_nvs.hpp"
#include "forgesense_events.h"
#include "forgesense_inference.h"
#include "link_service.hpp"
#include "telemetry_publisher.hpp"

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
    TelemetryPublisher telemetry;

    if (!events.begin()) {
        ESP_LOGE(kTag, "event store initialization failed");
        return;
    }
    if (!link.begin()) {
        ESP_LOGE(kTag, "FPGA UART link initialization failed");
        return;
    }

    auto sync_link_counters = [&]() {
        telemetry.set_link_counters({
            link.accepted_fpga_frames(),
            link.rejected_fpga_frames(),
            link.stale_sensor_frames(),
            link.stale_status_frames(),
            link.dropped_pending_messages(),
        });
    };

    auto publish_telemetry = [&](std::uint32_t timestamp_ms, bool force = false) {
        sync_link_counters();
        if (!telemetry.maybe_publish(timestamp_ms, force)) {
            ESP_LOGW(kTag, "failed to publish telemetry record");
        }
    };

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
    publish_telemetry(now_ms(), true);

    while (true) {
        ParsedFpgaMessage message{};
        if (!link.receive(message, 100)) {
            const std::uint32_t current_ms = now_ms();
            const std::uint32_t age_ms = current_ms - last_sensor_rx_ms;
            bool link_loss_transition = false;
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
                link_loss_transition = true;
                ESP_LOGW(kTag, "sensor link timeout");
            }
            publish_telemetry(current_ms, link_loss_transition);
            continue;
        }

        if (message.kind == FpgaMessageKind::Status) {
            const std::uint32_t received_ms = now_ms();
            telemetry.ingest_status(message.status, received_ms);

            const auto& status = message.status.status;
            const bool hard_critical_now =
                (status.safety_flags & kSafetyHardCritical) != 0;
            const bool hard_critical_before =
                (previous_safety_flags & kSafetyHardCritical) != 0;
            const bool emergency_now =
                (status.safety_flags & kSafetyEmergency) != 0;
            const bool emergency_before =
                (previous_safety_flags & kSafetyEmergency) != 0;
            const bool state_changed = status.state_code != previous_state_code;

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

            const bool urgent_status =
                state_changed ||
                (hard_critical_now != hard_critical_before) ||
                (emergency_now != emergency_before);
            previous_safety_flags = status.safety_flags;
            previous_state_code = status.state_code;
            publish_telemetry(received_ms, urgent_status);
            continue;
        }

        const ParsedSensorFrame& sensor_frame = message.sensor;
        const std::uint32_t sensor_received_ms = now_ms();
        telemetry.ingest_sensor(sensor_frame, sensor_received_ms);
        last_sensor = sensor_frame.snapshot;
        last_sensor_rx_ms = sensor_received_ms;
        const bool link_recovered = link_loss_logged;
        if (link_recovered) {
            (void)events.append(make_event(
                EventSeverity::Info,
                EventSource::Link,
                EventCode::LinkRecovered,
                sensor_frame.snapshot));
            link_loss_logged = false;
        }

        if (!sensor_frame.snapshot.all_valid()) {
            inference.reset();
            const bool sensor_became_invalid = !sensor_invalid_logged;
            if (sensor_became_invalid) {
                (void)events.append(make_event(
                    EventSeverity::Critical,
                    EventSource::Fpga,
                    EventCode::SensorInvalid,
                    sensor_frame.snapshot,
                    0,
                    sensor_frame.snapshot.flags));
                sensor_invalid_logged = true;
            }
            publish_telemetry(
                sensor_received_ms, sensor_became_invalid || link_recovered);
            continue;
        }
        sensor_invalid_logged = false;

        const std::uint32_t inference_started_ms = now_ms();
        MlObservation observation{};
        if (!inference.ingest(sensor_frame.snapshot, observation)) {
            publish_telemetry(sensor_received_ms, link_recovered);
            continue;
        }

        const std::uint32_t processing_age_ms = now_ms() - inference_started_ms;
        observation.inference_age_ms = static_cast<std::uint16_t>(
            std::min<std::uint32_t>(processing_age_ms, 0xFFFFU));

        const std::uint16_t sent_sequence = ml_sequence;
        const std::uint32_t sent_timestamp_ms = now_ms();
        if (!link.send_observation(observation, sent_sequence, sent_timestamp_ms)) {
            ESP_LOGW(kTag, "failed to transmit ML observation");
            publish_telemetry(now_ms());
            continue;
        }
        ml_sequence = static_cast<std::uint16_t>(ml_sequence + 1U);
        telemetry.ingest_ml(
            observation, sent_sequence, sent_timestamp_ms, now_ms());

        const bool health_changed = observation.health_class != previous_health;
        if (health_changed) {
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
        publish_telemetry(now_ms(), health_changed || link_recovered);
    }
}
