#include "forgesense_telemetry.h"

#include <cstdarg>
#include <cstdio>

namespace forgesense {
namespace {

class BufferWriter {
public:
    BufferWriter(char* out, std::size_t capacity) : out_(out), capacity_(capacity) {
        if (capacity_ > 0) out_[0] = '\0';
    }

    bool append(const char* format, ...) {
        if (!ok_ || out_ == nullptr || length_ >= capacity_) {
            ok_ = false;
            return false;
        }
        va_list args;
        va_start(args, format);
        const int count = std::vsnprintf(out_ + length_, capacity_ - length_, format, args);
        va_end(args);
        if (count < 0 || static_cast<std::size_t>(count) >= capacity_ - length_) {
            ok_ = false;
            if (capacity_ > 0) out_[capacity_ - 1] = '\0';
            return false;
        }
        length_ += static_cast<std::size_t>(count);
        return true;
    }

    bool ok() const { return ok_; }
    std::size_t length() const { return length_; }

private:
    char* out_{};
    std::size_t capacity_{};
    std::size_t length_{};
    bool ok_{true};
};

std::uint32_t age_ms(std::uint32_t now_ms, std::uint32_t received_ms) {
    return now_ms - received_ms;
}

}  // namespace

void DeviceTelemetrySnapshot::reset() {
    have_sensor_ = false;
    have_status_ = false;
    have_ml_ = false;
    sensor_ = {};
    status_ = {};
    ml_ = {};
    ml_sequence_ = 0;
    ml_source_timestamp_ms_ = 0;
    sensor_received_ms_ = 0;
    status_received_ms_ = 0;
    ml_received_ms_ = 0;
    counters_ = {};
    ++revision_;
}

void DeviceTelemetrySnapshot::ingest_sensor(const ParsedSensorFrame& frame, std::uint32_t received_ms) {
    sensor_ = frame;
    sensor_received_ms_ = received_ms;
    have_sensor_ = true;
    ++revision_;
}

void DeviceTelemetrySnapshot::ingest_status(const ParsedStatusFrame& frame, std::uint32_t received_ms) {
    status_ = frame;
    status_received_ms_ = received_ms;
    have_status_ = true;
    ++revision_;
}

void DeviceTelemetrySnapshot::ingest_ml(const MlObservation& observation, std::uint16_t sequence, std::uint32_t source_timestamp_ms, std::uint32_t received_ms) {
    ml_ = observation;
    ml_sequence_ = sequence;
    ml_source_timestamp_ms_ = source_timestamp_ms;
    ml_received_ms_ = received_ms;
    have_ml_ = true;
    ++revision_;
}

void DeviceTelemetrySnapshot::set_link_counters(const TelemetryLinkCounters& counters) {
    if (counters.accepted_fpga_frames != counters_.accepted_fpga_frames ||
        counters.rejected_fpga_frames != counters_.rejected_fpga_frames ||
        counters.stale_sensor_frames != counters_.stale_sensor_frames ||
        counters.stale_status_frames != counters_.stale_status_frames ||
        counters.dropped_pending_messages != counters_.dropped_pending_messages) {
        counters_ = counters;
        ++revision_;
    }
}

std::size_t DeviceTelemetrySnapshot::encode_line(std::uint32_t now_ms, char* out, std::size_t capacity) const {
    if (out == nullptr || capacity == 0) return 0;
    BufferWriter writer(out, capacity);
    writer.append("%s{\"schema\":\"%s\",\"revision\":%u,\"device_ms\":%u,", kDeviceTelemetryPrefix, kDeviceTelemetrySchema, static_cast<unsigned>(revision_), static_cast<unsigned>(now_ms));

    if (have_sensor_) {
        writer.append("\"sensor\":{\"sequence\":%u,\"source_timestamp_ms\":%u,\"received_age_ms\":%u,\"temperature_deci_c\":%d,\"vibration_milli_g\":%u,\"current_milli_a\":%u,\"flags\":%u},",
            static_cast<unsigned>(sensor_.sequence), static_cast<unsigned>(sensor_.timestamp_ms), static_cast<unsigned>(age_ms(now_ms, sensor_received_ms_)), static_cast<int>(sensor_.snapshot.temperature_deci_c), static_cast<unsigned>(sensor_.snapshot.vibration_milli_g), static_cast<unsigned>(sensor_.snapshot.current_milli_a), static_cast<unsigned>(sensor_.snapshot.flags));
    } else writer.append("\"sensor\":null,");

    if (have_status_) {
        writer.append("\"fpga_status\":{\"sequence\":%u,\"source_timestamp_ms\":%u,\"received_age_ms\":%u,\"state_code\":%u,\"control_flags\":%u,\"safety_flags\":%u},",
            static_cast<unsigned>(status_.sequence), static_cast<unsigned>(status_.timestamp_ms), static_cast<unsigned>(age_ms(now_ms, status_received_ms_)), static_cast<unsigned>(status_.status.state_code), static_cast<unsigned>(status_.status.control_flags), static_cast<unsigned>(status_.status.safety_flags));
    } else writer.append("\"fpga_status\":null,");

    if (have_ml_) {
        writer.append("\"ml\":{\"sequence\":%u,\"source_timestamp_ms\":%u,\"received_age_ms\":%u,\"model_id\":%u,\"model_version\":%u,\"feature_schema_version\":%u,\"flags\":%u,\"anomaly_q15\":%u,\"health_class\":%u,\"confidence_q8\":%u,\"inference_age_ms\":%u},",
            static_cast<unsigned>(ml_sequence_), static_cast<unsigned>(ml_source_timestamp_ms_), static_cast<unsigned>(age_ms(now_ms, ml_received_ms_)), static_cast<unsigned>(ml_.model_id), static_cast<unsigned>(ml_.model_version), static_cast<unsigned>(ml_.feature_schema_version), static_cast<unsigned>(ml_.flags), static_cast<unsigned>(ml_.anomaly_q15), static_cast<unsigned>(ml_.health_class), static_cast<unsigned>(ml_.confidence_q8), static_cast<unsigned>(ml_.inference_age_ms));
    } else writer.append("\"ml\":null,");

    writer.append("\"link\":{\"accepted_fpga_frames\":%u,\"rejected_fpga_frames\":%u,\"stale_sensor_frames\":%u,\"stale_status_frames\":%u,\"dropped_pending_messages\":%u}}\n",
        static_cast<unsigned>(counters_.accepted_fpga_frames), static_cast<unsigned>(counters_.rejected_fpga_frames), static_cast<unsigned>(counters_.stale_sensor_frames), static_cast<unsigned>(counters_.stale_status_frames), static_cast<unsigned>(counters_.dropped_pending_messages));
    return writer.ok() ? writer.length() : 0;
}

}  // namespace forgesense
