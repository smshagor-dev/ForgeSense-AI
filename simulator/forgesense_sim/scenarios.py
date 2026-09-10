from __future__ import annotations

from dataclasses import dataclass

from .plant import FaultProfile, MachinePlant, SensorSnapshot


@dataclass(frozen=True)
class Scenario:
    name: str
    samples: int = 400
    dt_s: float = 0.1
    seed: int = 7
    fault_start: int | None = None
    fault_kind: str | None = None


def build_scenario(name: str) -> Scenario:
    known = {
        "normal": Scenario("normal"),
        "bearing_degradation": Scenario("bearing_degradation", samples=500, fault_start=220, fault_kind="bearing"),
        "overcurrent": Scenario("overcurrent", samples=400, fault_start=180, fault_kind="overcurrent"),
        "cooling_loss": Scenario("cooling_loss", samples=700, fault_start=260, fault_kind="cooling_loss"),
        "sensor_dropout": Scenario("sensor_dropout", samples=400, fault_start=180, fault_kind="sensor_dropout"),
    }
    try:
        return known[name]
    except KeyError as exc:
        raise ValueError(f"unknown scenario: {name}") from exc


def _fault_for(scenario: Scenario, index: int) -> FaultProfile:
    if scenario.fault_start is None or index < scenario.fault_start:
        return FaultProfile()
    progress = min((index - scenario.fault_start) / max(scenario.samples - scenario.fault_start - 1, 1), 1.0)
    if scenario.fault_kind == "bearing":
        return FaultProfile(bearing=progress)
    if scenario.fault_kind == "overcurrent":
        return FaultProfile(overcurrent=min(0.35 + progress, 1.0))
    if scenario.fault_kind == "cooling_loss":
        return FaultProfile(cooling_loss=min(0.25 + progress, 1.0))
    return FaultProfile()


def run_scenario(scenario: Scenario) -> list[SensorSnapshot]:
    plant = MachinePlant(seed=scenario.seed)
    snapshots: list[SensorSnapshot] = []
    for index in range(scenario.samples):
        load = 0.56 + 0.15 * ((index // 60) % 3) / 2.0
        sample = plant.step(load=load, dt_s=scenario.dt_s, fault=_fault_for(scenario, index))
        dropout = scenario.fault_kind == "sensor_dropout" and scenario.fault_start is not None and scenario.fault_start <= index < scenario.fault_start + 25
        snapshots.append(plant.sense(sample, dropout_vibration=dropout))
    return snapshots
