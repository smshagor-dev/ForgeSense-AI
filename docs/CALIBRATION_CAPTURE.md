# Bench Calibration Capture

## Purpose

ForgeSense calibration capture converts measured low-voltage bench data into a reviewable engineering proposal. It does not modify FPGA or ESP32 runtime calibration, does not change hard thresholds, and is not a safety-limit approval.

The utility covers three evidence paths:

- current sensing: multi-point ADS131M02 raw code versus independently measured reference current;
- temperature: TMP117 reading versus independently measured reference temperature, summarized as a constant offset characterization;
- vibration sensing: stationary ADXL355 XYZ measurements versus a documented expected gravity orientation, summarized as axis bias.

## Evidence first

Start from:

`hardware/calibration/calibration_capture_template_v1.json`

Replace every placeholder with real values from the bench. The template example numbers are structure examples only; they are not physical evidence.

Each retained capture identifies:

- exact repository commit;
- FPGA board revision;
- ESP32 board revision;
- sensor-board revision;
- instruments and calibration status;
- ambient conditions where available;
- retained evidence file hashes;
- current reference points;
- temperature reference points;
- stationary accelerometer samples.

Evidence file SHA-256 values are mandatory so the proposal can be traced back to the raw capture used to derive it.

## Generate a proposal

```bash
python tools/capture_calibration.py \
  evidence/calibration-capture.json \
  --out build/calibration-proposal.json
```

The output is `forgesense.calibration_proposal.v1` and explicitly contains:

```text
review_required = true
automatic_runtime_application = false
may_relax_hard_safety_limits = false
```

A generated file is therefore an engineering review input only.

## Current fit

The current path fits:

```text
reference current in mA = slope * ADS131M02 raw code + intercept
```

The proposal reports:

- number of points;
- raw-code span;
- slope and intercept;
- RMSE;
- maximum absolute residual;
- R²;
- bounded rational gain numerator/denominator candidate;
- integer output-offset candidate;
- proposal-quality verdict.

Quality limits evaluate whether the evidence is useful enough for engineering review. Passing them does not authorize a new motor limit or comparator threshold.

The current capture should cover the intended operating range using a controlled reference load/source and an independently measured current value. Do not generate a fit from one operating point.

## TMP117 characterization

The temperature path computes the mean difference:

```text
reference_temperature - TMP117_temperature
```

It reports a constant offset candidate and the residual RMSE after that offset is removed. Multiple reference temperatures are required so a single-point coincidence cannot be treated as characterization.

If residuals show significant slope/nonlinearity, reject the constant-offset proposal and investigate the physical setup instead of forcing the fit.

## ADXL355 stationary bias

The accelerometer path expects a documented stationary orientation, defaulting to:

```text
X = 0 mg
Y = 0 mg
Z = +1000 mg
```

It computes mean measured XYZ values, bias relative to that orientation, and correction candidates. The capture requires multiple samples. This is a static bias characterization, not vibration-bandwidth or scale-factor calibration.

Mounting orientation must be known before interpreting the expected gravity vector.

## Review boundary

The proposal must be reviewed together with:

- raw evidence files;
- instrument traceability/calibration state;
- board revisions;
- temperature and supply conditions;
- current-sense schematic revision;
- residual plots or equivalent analysis when needed;
- repeatability across more than one run where the result affects protection behavior.

The existing FPGA calibration and hard-safety configuration remain unchanged until a separate reviewed change explicitly updates source-controlled coefficients and verification evidence.

There is intentionally no runtime command in this utility for applying calibration or relaxing safety limits.

## Verification

Run:

```bash
make calibration-check
```

The source-level gate verifies the proposal-only authority rules and synthetic fit tests. Synthetic tests validate arithmetic and rejection behavior; they are not substitutes for physical measurements.
