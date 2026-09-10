# Machine-Learning Reference Baseline

The first executable model is a compact diagonal-Gaussian anomaly detector. It
exists to establish data contracts, metrics, export behavior, and end-to-end
integration before more complex TinyML models are justified.

It is intentionally not presented as final predictive-maintenance intelligence.

```bash
PYTHONPATH=simulator:ml python -m forgesense_ml.train --out build/model.json
```

The exported JSON artifact records model and feature-schema versions. Firmware
integration must reject incompatible versions.
