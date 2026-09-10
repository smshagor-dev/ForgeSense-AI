#include "forgesense_inference.h"
#include "forgesense_reference_model_generated.h"

#include <algorithm>
#include <cmath>

namespace forgesense {
namespace {

std::uint16_t to_q15(float value) {
    const float clamped = std::clamp(value, 0.0F, 1.0F);
    return static_cast<std::uint16_t>(std::lround(clamped * 32767.0F));
}

std::uint8_t to_q8(float value) {
    const float clamped = std::clamp(value, 0.0F, 1.0F);
    return static_cast<std::uint8_t>(std::lround(clamped * 255.0F));
}

}  // namespace

ModelConfig reference_simulation_model() {
    ModelConfig model{};
    model.model_id = generated::kModelId;
    model.model_version = generated::kModelVersion;
    model.feature_schema_version = generated::kFeatureSchemaVersion;
    model.mean = generated::kMean;
    model.scale = generated::kScale;
    model.warning_threshold = generated::kWarningThreshold;
    model.critical_threshold = generated::kCriticalThreshold;
    return model;
}

InferenceResult infer(
    const ModelConfig& model,
    const std::array<float, 3>& features) {
    float z2_sum = 0.0F;
    for (std::size_t i = 0; i < features.size(); ++i) {
        const float scale = std::max(model.scale[i], 1.0e-4F);
        const float z = (features[i] - model.mean[i]) / scale;
        z2_sum += z * z;
    }
    const float squared_z_mean = z2_sum / 3.0F;
    const float score =
        std::clamp(1.0F - std::exp(-0.5F * squared_z_mean), 0.0F, 1.0F);

    HealthClass health = HealthClass::Normal;
    if (score >= model.critical_threshold) {
        health = HealthClass::Critical;
    } else if (score >= model.warning_threshold) {
        health = HealthClass::Warning;
    }

    const float d_warning = std::fabs(score - model.warning_threshold);
    const float d_critical = std::fabs(score - model.critical_threshold);
    const float confidence =
        std::min(0.5F + std::min(d_warning, d_critical), 0.99F);

    return {score, health, confidence, squared_z_mean};
}

void EdgeInferenceRuntime::reset() {
    rows_.fill({});
    write_index_ = 0;
    count_ = 0;
}

std::array<float, 3> EdgeInferenceRuntime::mean_window() const {
    std::array<float, 3> result{};
    if (count_ == 0) {
        return result;
    }
    for (std::size_t row = 0; row < count_; ++row) {
        for (std::size_t col = 0; col < result.size(); ++col) {
            result[col] += rows_[row][col];
        }
    }
    for (float& value : result) {
        value /= static_cast<float>(count_);
    }
    return result;
}

bool EdgeInferenceRuntime::ingest(
    const SensorSnapshot& snapshot,
    MlObservation& out) {
    if (!snapshot.all_valid()) {
        reset();
        return false;
    }

    rows_[write_index_] = {
        static_cast<float>(snapshot.temperature_deci_c) / 10.0F,
        static_cast<float>(snapshot.vibration_milli_g) / 1000.0F,
        static_cast<float>(snapshot.current_milli_a) / 1000.0F,
    };
    write_index_ = (write_index_ + 1) % kWindowSize;
    if (count_ < kWindowSize) {
        ++count_;
    }
    if (!ready()) {
        return false;
    }

    const auto result = infer(model_, mean_window());
    out.model_id = model_.model_id;
    out.model_version = model_.model_version;
    out.feature_schema_version = model_.feature_schema_version;
    out.flags = kValidObservation;
    out.anomaly_q15 = to_q15(result.anomaly_score);
    out.health_class = result.health_class;
    out.confidence_q8 = to_q8(result.confidence);
    out.inference_age_ms = 0;
    return true;
}

}  // namespace forgesense
