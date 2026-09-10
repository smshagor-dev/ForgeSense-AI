#include "forgesense_stream.h"

namespace forgesense {

void MlStreamDecoder::reset() {
    size_ = 0;
}

void MlStreamDecoder::restart_from(std::uint8_t byte) {
    size_ = 0;
    if (byte == 0xA5) {
        buffer_[0] = byte;
        size_ = 1;
    }
}

StreamEvent MlStreamDecoder::push(std::uint8_t byte, ParsedMlFrame& out) {
    if (size_ == 0) {
        if (byte == 0xA5) {
            buffer_[0] = byte;
            size_ = 1;
        }
        return StreamEvent::None;
    }

    if (size_ == 1) {
        if (byte == 0x5A) {
            buffer_[1] = byte;
            size_ = 2;
        } else if (byte == 0xA5) {
            buffer_[0] = byte;
            size_ = 1;
        } else {
            size_ = 0;
        }
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
