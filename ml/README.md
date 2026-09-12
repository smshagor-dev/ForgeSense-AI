# ForgeSense AI Machine-Learning Data and Reference Models

ForgeSense keeps machine-learning data generation, model evaluation, and embedded export separate from the deterministic FPGA safety authority. ML output may inform the FPGA through the versioned protocol, but ML data or model code cannot change hard safety limits.

## Full synthetic training dataset v2

The repository contains a reproducible full synthetic dataset generator:

```text
ml/forgesense_ml/full_dataset.py
tools/generate_full_ml_dataset.py
ml/contracts/full_dataset_v2.json
```

Generate the default full package from the repository root:

```bash
make ml-full-dataset
```

or directly:

```bash
PYTHONPATH=simulator:ml python tools/generate_full_ml_dataset.py \
  --out-dir build/ml-dataset-v2
```

The default package uses **26 scenario types** and **15 independent deterministic runs per scenario**. The split is performed by `run_id`, not by randomly shuffling adjacent samples, so a physical/digital-twin run can never leak between train, validation, and test.

### Scenario coverage

The full package covers normal operation; bearing degradation; overcurrent; cooling loss; combined bearing/overcurrent and cooling/overcurrent faults; temperature, vibration, and current bias; temperature, vibration, and current drift; high-noise temperature, vibration, and current sensors; stuck sensor values; observable sensor saturation/clipping; per-channel dropouts; multi-sensor dropout; and combined bearing degradation with vibration-sensor drift.

### Dataset outputs

The generator writes:

```text
raw-train.csv
raw-validation.csv
raw-test.csv
windows-train.csv
windows-validation.csv
windows-test.csv
baseline-normal-train.csv
scenario-summary.csv
manifest.json
checksums.sha256
README.md
```

The raw files retain digital-twin ground truth and measured sensor values together with validity, load, speed, fault activation, severity, anomaly label, and three-class health target.

The window files contain leakage-safe 8-sample feature windows with mean, standard deviation, minimum, maximum, delta, validity fractions, load/speed means, fault fraction, binary anomaly target, and health class.

Health classes are:

```text
0 = normal
1 = warning
2 = critical
```

`baseline-normal-train.csv` contains only valid settled normal samples and is the correct source for the current diagonal-Gaussian normal-envelope model.

### Training rules

For the current reference anomaly model, train only from `baseline-normal-train.csv`.

For supervised tree/neural models, train on `windows-train.csv`, tune only with `windows-validation.csv`, and report final performance once on `windows-test.csv`.

For sequence models using raw samples, group every operation by `run_id`. Never split adjacent samples from one run across partitions.

### Dataset regression gate

Run:

```bash
make ml-full-dataset-check
```

The check verifies deterministic output, split isolation, expected ground-truth/measured columns, engineered-window fields, provenance hashes, and the explicit synthetic-data authority boundary.

## Reference baseline

The first executable model remains a compact diagonal-Gaussian anomaly detector. It exists to establish data contracts, metrics, export behavior, and end-to-end integration before a more complex TinyML model is justified.

```bash
PYTHONPATH=simulator:ml python -m forgesense_ml.train --out build/model.json
```

The exported JSON artifact records model and feature-schema versions. Firmware integration must reject incompatible versions.

## Evidence boundary

The v2 training package is synthetic digital-twin data. It is useful for software development, feature engineering, model architecture work, regression tests, and pre-hardware evaluation, but it is **not** a physical industrial dataset and must not be reported as production accuracy evidence.

Final model qualification requires retained physical datasets from the selected electronics/sensors and representative machinery, including real mounting, EMI, temperature, vibration, load, wear, and failure behavior.
