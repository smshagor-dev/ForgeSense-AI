#include "forgesense_stream.h"

namespace forgesense {
namespace {

template <std::size_t N>
void reset_stream_size(std::size_t& size, std::array<std::uint8_t, N>& buffer) {
    size = 0;
    buffer.fill(0);
}

template <std::size_t N>
void restart_stream(
    std::uint8_t byte,
    std::size_t& size,
    std::array<std::uint8_t, N>& buffer) {
    size = 0;
    if (byte == 0xA5) {
        buffer[0] = byte;
        size = 1;
    }
}

template <std::size_t N>
bool push_prefix(
    std::uint8_t byte,
    std::size_t& size,
    std::array<std::uint8_t, N>& buffer) {
    if (size == 0) {
        if (byte == 0xA5) {
            buffer[0] = byte;
            size = 1;
        }
        return true;
    }

    if (size == 1) {
        if (byte == 0x5A) {
            buffer[1] = byte;
            size = 2;
        } else if (byte == 0xA5) {
            buffer[0] = byte;
            size = 1;
        } else {
            size = 0;
        }
        return true;
    }
    return false;
}

}  // namespace

void FpgaStreamDecoder::reset() {
    reset_stream_size(size_, buffer_);
    expected_size_ = 0;
    message_type_ = 0;
}

void FpgaStreamDecoder::restart_from(std::uint8_t byte) {
    restart_stream(byte, size_, buffer_);
    expected_size_ = 0;
    message_type_ = 0;
}

StreamEvent FpgaStreamDecoder::push(
    std::uint8_t byte,
    ParsedFpgaMessage& out) {
    if (push_prefix(byte, size_, buffer_)) {
        return StreamEvent::None;
    }

    if (size_ >= buffer_.size()) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    buffer_[size_++] = byte;

    if (size_ == 3 && buffer_[2] != kProtocolVersion) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    if (size_ == 4) {
        message_type_ = buffer_[3];
        if (message_type_ == kMessageSensorSnapshot) {
            expected_size_ = kSensorFrameSize;
        } else if (message_type_ == kMessageStatus) {
            expected_size_ = kStatusFrameSize;
        } else {
            ++rejected_frames_;
            restart_from(byte);
            return StreamEvent::Rejected;
        }
    }
    if (size_ == 8) {
        const bool length_ok =
            (message_type_ == kMessageSensorSnapshot &&
             buffer_[6] == 0x08 && buffer_[7] == 0x00) ||
            (message_type_ == kMessageStatus &&
             buffer_[6] == 0x04 && buffer_[7] == 0x00);
        if (!length_ok) {
            ++rejected_frames_;
            restart_from(byte);
            return StreamEvent::Rejected;
        }
    }
    if (expected_size_ == 0 || size_ < expected_size_) {
        return StreamEvent::None;
    }

    ParseStatus status = ParseStatus::BadType;
    if (message_type_ == kMessageSensorSnapshot) {
        status = parse_sensor_frame(buffer_.data(), expected_size_, out.sensor);
        out.kind = FpgaMessageKind::Sensor;
    } else if (message_type_ == kMessageStatus) {
        status = parse_status_frame(buffer_.data(), expected_size_, out.status);
        out.kind = FpgaMessageKind::Status;
    }

    reset();
    if (status == ParseStatus::Ok) {
        ++accepted_frames_;
        return StreamEvent::Frame;
    }
    ++rejected_frames_;
    return StreamEvent::Rejected;
}

void MlStreamDecoder::reset() {
    reset_stream_size(size_, buffer_);
}

void MlStreamDecoder::restart_from(std::uint8_t byte) {
    restart_stream(byte, size_, buffer_);
}

StreamEvent MlStreamDecoder::push(std::uint8_t byte, ParsedMlFrame& out) {
    if (push_prefix(byte, size_, buffer_)) {
        return StreamEvent::None;
    }

    buffer_[size_++] = byte;

    if (size_ == 3 && buffer_[2] != kProtocolVersion) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    if (size_ == 4 && buffer_[3] != kMessageMlObservation) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    if (size_ == 8 && (buffer_[6] != 0x0E || buffer_[7] != 0x00)) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    if (size_ < kMlFrameSize) {
        return StreamEvent::None;
    }

    const auto status = parse_ml_frame(buffer_.data(), buffer_.size(), out);
    size_ = 0;
    if (status == ParseStatus::Ok) {
        ++accepted_frames_;
        return StreamEvent::Frame;
    }
    ++rejected_frames_;
    return StreamEvent::Rejected;
}

void SensorStreamDecoder::reset() {
    reset_stream_size(size_, buffer_);
}

void SensorStreamDecoder::restart_from(std::uint8_t byte) {
    restart_stream(byte, size_, buffer_);
}

StreamEvent SensorStreamDecoder::push(std::uint8_t byte, ParsedSensorFrame& out) {
    if (push_prefix(byte, size_, buffer_)) {
        return StreamEvent::None;
    }

    buffer_[size_++] = byte;

    if (size_ == 3 && buffer_[2] != kProtocolVersion) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    if (size_ == 4 && buffer_[3] != kMessageSensorSnapshot) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    if (size_ == 8 && (buffer_[6] != 0x08 || buffer_[7] != 0x00)) {
        ++rejected_frames_;
        restart_from(byte);
        return StreamEvent::Rejected;
    }
    if (size_ < kSensorFrameSize) {
        return StreamEvent::None;
    }

    const auto status = parse_sensor_frame(buffer_.data(), buffer_.size(), out);
    size_ = 0;
    if (status == ParseStatus::Ok) {
        ++accepted_frames_;
        return StreamEvent::Frame;
    }
    ++rejected_frames_;
    return StreamEvent::Rejected;
}

GateStatus FreshnessGate::accept(const ParsedMlFrame& frame) {
    const auto& observation = frame.observation;
    if ((observation.flags & kValidObservation) == 0) {
        return GateStatus::InvalidFlag;
    }
    if (observation.model_id != model_id_) {
        return GateStatus::ModelId;
    }
    if (observation.model_version != model_version_) {
        return GateStatus::ModelVersion;
    }
    if (observation.feature_schema_version != feature_schema_) {
        return GateStatus::FeatureSchema;
    }
    if (observation.inference_age_ms > max_age_ms_) {
        return GateStatus::StaleInference;
    }
    if (have_sequence_ && !sequence_is_newer(frame.sequence, last_sequence_)) {
        return GateStatus::ReplayOrDuplicate;
    }
    last_sequence_ = frame.sequence;
    have_sequence_ = true;
    return GateStatus::Accepted;
}

}  // namespace forgesense
