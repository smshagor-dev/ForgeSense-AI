#pragma once

#include "forgesense_protocol.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense {

enum class StreamEvent { None, Frame, Rejected };

class MlStreamDecoder {
public:
    StreamEvent push(std::uint8_t byte, ParsedMlFrame& out);
    void reset();
    std::uint32_t accepted_frames() const { return accepted_frames_; }
    std::uint32_t rejected_frames() const { return rejected_frames_; }

private:
    std::array<std::uint8_t, kMlFrameSize> buffer_{};
    std::size_t size_{0};
    std::uint32_t accepted_frames_{0};
    std::uint32_t rejected_frames_{0};
    void restart_from(std::uint8_t byte);
};

class SensorStreamDecoder {
public:
    StreamEvent push(std::uint8_t byte, ParsedSensorFrame& out);
    void reset();
    std::uint32_t accepted_frames() const { return accepted_frames_; }
    std::uint32_t rejected_frames() const { return rejected_frames_; }

private:
    std::array<std::uint8_t, kSensorFrameSize> buffer_{};
    std::size_t size_{0};
    std::uint32_t accepted_frames_{0};
    std::uint32_t rejected_frames_{0};
    void restart_from(std::uint8_t byte);
};

class SequenceGate {
public:
    bool accept(std::uint16_t sequence) {
        if (have_sequence_ && !sequence_is_newer(sequence, last_sequence_)) {
            return false;
        }
        last_sequence_ = sequence;
        have_sequence_ = true;
        return true;
    }

    void reset() {
        have_sequence_ = false;
        last_sequence_ = 0;
    }

private:
    bool have_sequence_{false};
    std::uint16_t last_sequence_{0};
};

enum class GateStatus {
    Accepted,
    InvalidFlag,
    ModelId,
    ModelVersion,
    FeatureSchema,
    StaleInference,
    ReplayOrDuplicate
};

class FreshnessGate {
public:
    FreshnessGate(
        std::uint16_t model_id = 1,
        std::uint16_t model_version = 1,
        std::uint16_t feature_schema = 1,
        std::uint16_t max_age_ms = 1500)
        : model_id_(model_id),
          model_version_(model_version),
          feature_schema_(feature_schema),
          max_age_ms_(max_age_ms) {}

    GateStatus accept(const ParsedMlFrame& frame);
    void reset() {
        have_sequence_ = false;
        last_sequence_ = 0;
    }

private:
    std::uint16_t model_id_;
    std::uint16_t model_version_;
    std::uint16_t feature_schema_;
    std::uint16_t max_age_ms_;
    bool have_sequence_{false};
    std::uint16_t last_sequence_{0};
};

}  // namespace forgesense
