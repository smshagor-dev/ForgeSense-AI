# Virtual Machine and Sensor Simulator

The simulator provides deterministic machine-condition traces before physical
hardware is purchased. It is a reference integration environment, not a
high-fidelity motor-physics model.

Run a scenario:

```bash
PYTHONPATH=simulator python -m forgesense_sim.cli bearing_degradation --out build/bearing.jsonl
```

Supported scenarios are `normal`, `bearing_degradation`, `overcurrent`,
`cooling_loss`, and `sensor_dropout`.

The same seed and scenario configuration must produce the same trace.
