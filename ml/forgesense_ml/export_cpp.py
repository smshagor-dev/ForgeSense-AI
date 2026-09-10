from __future__ import annotations

from .baseline import DiagonalGaussianModel


def _f(value: float) -> str:
    text = f"{value:.9g}"
    if "e" not in text and "." not in text:
        text += ".0"
    return f"{text}F"


def render_cpp_reference_header(model: DiagonalGaussianModel) -> str:
    mean = ", ".join(_f(value) for value in model.mean)
    scale = ", ".join(_f(value) for value in model.scale)
    return f"""#pragma once

#include <array>
#include <cstdint>

namespace forgesense::generated {{

inline constexpr std::uint16_t kModelId = {model.model_id};
inline constexpr std::uint16_t kModelVersion = {model.model_version};
inline constexpr std::uint16_t kFeatureSchemaVersion = {model.feature_schema_version};
inline constexpr std::array<float, 3> kMean = {{{mean}}};
inline constexpr std::array<float, 3> kScale = {{{scale}}};
inline constexpr float kWarningThreshold = {_f(model.warning_threshold)};
inline constexpr float kCriticalThreshold = {_f(model.critical_threshold)};

}}  // namespace forgesense::generated
"""
