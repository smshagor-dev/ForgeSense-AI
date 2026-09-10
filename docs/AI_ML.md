# AI and Machine Learning

## Role

ML estimates machine condition from recent sensor behavior. It does not own the
hard safety path.

## First ML tasks

1. anomaly scoring from temperature, vibration, and current-derived features;
2. coarse health classification when labels support it;
3. optional fault-family classification after representative real data exists.

## Baselines first

Every ML candidate should be compared against simple baselines such as fixed
thresholds, rolling statistics, linear/logistic models, tree-based methods, or
other appropriately small models. A neural model must earn its complexity through
measured improvement.

## Data contract

Every dataset release or experiment must record:

- dataset identifier and version;
- provenance;
- sensor definitions and units;
- sampling rates;
- machine/test configuration;
- scenario labels and how they were assigned;
- preprocessing version;
- split policy;
- exclusions;
- known limitations.

Synthetic data must be explicitly labeled synthetic and never presented as real
machine evidence.

## Leakage prevention

Time-adjacent windows from the same fault run can create misleading accuracy if
randomly split. Evaluation should use grouping/time-aware separation appropriate
to the experiment.

## Required metrics

Depending on task:

- precision;
- recall;
- F1;
- false alarms per operating time;
- missed-fault rate;
- detection lead time;
- AUROC/AUPRC where appropriate;
- calibration/uncertainty evidence where used;
- inference latency;
- peak memory;
- model size.

Class imbalance must be reported.

## Deployment contract

Exported models must be tied to:

```text
model_id
model_version
feature_schema_version
training_data_version
normalization_version
quantization/export version
expected input range
output interpretation
acceptance metrics
```

The firmware must reject model/feature incompatibility rather than silently infer
with the wrong schema.

## Drift and uncertainty

Later work should measure sensor drift, machine-to-machine variation, operating
regime changes, confidence calibration, and out-of-distribution behavior. A model
that is uncertain should be allowed to abstain; abstention must not weaken FPGA
hard safety logic.
