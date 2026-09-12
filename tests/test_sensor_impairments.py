from __future__ import annotations

import pytest

from forgesense_sim.plant import (
    ChannelImpairment,
    FaultProfile,
    MachinePlant,
    MachineSample,
    SensorImpairmentProfile,
)


def sample() -> MachineSample:
    return MachineSample(
        sample_index=10,
        time_s=5.0,
        load=0.5,
        temperature_c=30.0,
        vibration_rms_g=0.2,
        current_a=1.5,
        speed_rpm=1500.0,
        fault=FaultProfile(),
    )


def test_bias_drift_saturation_stuck_and_dropout_are_deterministic() -> None:
    plant = MachinePlant(seed=123)
    profile = SensorImpairmentProfile(
        temperature=ChannelImpairment(noise_sigma=0.0, bias=1.0, drift_per_s=0.2),
        vibration=ChannelImpairment(noise_sigma=0.0, stuck_value=0.75, saturation_max=0.5),
        current=ChannelImpairment(noise_sigma=0.0, bias=1.0, saturation_max=2.0, dropout=True),
    )
    snapshot = plant.sense(sample(), impairments=profile)
    assert snapshot.temperature_c == pytest.approx(32.0)
    assert snapshot.vibration_rms_g == pytest.approx(0.5)
    assert snapshot.current_a == pytest.approx(2.0)
    assert snapshot.valid_temperature is True
    assert snapshot.valid_vibration is True
    assert snapshot.valid_current is False


def test_negative_physical_channels_remain_non_negative() -> None:
    plant = MachinePlant(seed=1)
    profile = SensorImpairmentProfile(
        vibration=ChannelImpairment(noise_sigma=0.0, bias=-10.0),
        current=ChannelImpairment(noise_sigma=0.0, bias=-10.0),
    )
    snapshot = plant.sense(sample(), impairments=profile)
    assert snapshot.vibration_rms_g == 0.0
    assert snapshot.current_a == 0.0


def test_invalid_impairment_profile_is_rejected() -> None:
    plant = MachinePlant(seed=1)
    with pytest.raises(ValueError, match="noise_sigma"):
        plant.sense(
            sample(),
            impairments=SensorImpairmentProfile(
                temperature=ChannelImpairment(noise_sigma=-0.1)
            ),
        )
    with pytest.raises(ValueError, match="saturation_min"):
        plant.sense(
            sample(),
            impairments=SensorImpairmentProfile(
                current=ChannelImpairment(saturation_min=2.0, saturation_max=1.0)
            ),
        )


def test_legacy_dropout_arguments_remain_supported() -> None:
    plant = MachinePlant(seed=1)
    snapshot = plant.sense(sample(), dropout_temperature=True)
    assert snapshot.valid_temperature is False
