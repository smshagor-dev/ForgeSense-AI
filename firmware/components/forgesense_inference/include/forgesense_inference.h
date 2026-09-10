#pragma once

#include "forgesense_protocol.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace forgesense {

struct ModelConfig {
    std::uint16_t model_id{1};
    std::uint16_t model_version{1};
    std::uint16_t feature_schema_version{1};
    std::array<float, 3> mean{};
    std::array<float, 3> scale{};
    float warning_threshold{0.72F};
    float critical_threshold{0.90F};
};

struct InferenceResult {
    float anomaly_score{};
    HealthClass health_class{HealthClass::Abstain};
    float confidence{};
    float squared_z_mean{};
};

ModelConfig reference_simulation_model();
InferenceResult infer(const ModelConfig& model, const std::array<float, 3>& features);

class EdgeInferenceRuntime {
public:
    static constexpr std::size_t kWindowSize = 8;

    explicit EdgeInferenceRuntime(ModelConfig model = reference_simulation_model())
        : model_(model) {}

    bool ingest(const SensorSnapshot& snapshot, MlObservation& out);
    void reset();
    bool ready() const { return count_ == kWindowSize; }
    std::size_t sample_count() const { return count_; }

private:
    ModelConfig model_;
    std::array<std::array<float, 3>, kWindowSize> rows_{};
    std::size_t write_index_{0};
    std::size_t count_{0};

    std::array<float, 3> mean_window() const;
};

}  // namespace forgesense
