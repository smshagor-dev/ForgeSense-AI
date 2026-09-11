# Calibration Session Assembly

## Purpose

The calibration diagnostic stream records what ForgeSense observed. It does not provide independent reference truth. `tools/assemble_calibration_capture.py` joins those read-only diagnostic captures with separately measured reference current, reference temperature, instrument uncertainty, board identity, and bench metadata.

The output is a standard `forgesense.calibration_capture.v1` artifact that can be passed directly to `tools/capture_calibration.py` or converted to a review-only proposal in the same command.

The assembler does not apply calibration, write FPGA or ESP32 coefficients, enable the external load, or relax deterministic hard-safety limits.

## Evidence chain

The intended chain is:

```text
physical sensor/device
        |
        v
read-only FPGA calibration image
        |
        v
forgesense.calibration_diagnostic_capture.v1
        |
        +---------------- independent reference meter / thermometer
        |                                  |
        v                                  v
forgesense.calibration_session.v1 manifest
        |
        v
tools/assemble_calibration_capture.py
        |
        v
forgesense.calibration_capture.v1
        |
        v
tools/capture_calibration.py
        |
        v
forgesense.calibration_proposal.v1
        |
        v
repeated-run review
```

ForgeSense observations and reference truth remain deliberately separate until the assembly step.

## Session manifest

Start from:

`hardware/calibration/calibration_session_template_v1.json`

The manifest records:

- a unique capture/session identifier;
- the exact 40-hex repository commit;
- FPGA, ESP32-S3, and sensor-board revisions;
- independent reference instruments and calibration state;
- bench/environment notes;
- expanded reference uncertainty (`k=2`);
- current-reference operating points;
- temperature-reference operating points;
- stationary accelerometer evidence;
- optional fit-quality limits.

All `diagnostic_file` paths are resolved relative to the session manifest unless an absolute path is supplied.

## Current characterization

At least five independent current reference points are required.

Each point contains:

```json
{
  "diagnostic_file": "evidence/current-02.json",
  "reference_current_a": 1.0
}
```

The reference current must come from an independent meter/source method. It must not be calculated from the ADS131M02 channel being calibrated.

For every point the assembler:

- rejects failed, corrupt, sequence-broken, or authority-tampered diagnostic captures;
- keeps only samples explicitly marked usable for calibration;
- computes the mean ADS131M02 channel-0 raw code;
- records the raw-code population standard deviation and sample count;
- retains the independent reference current unchanged;
- hashes the raw diagnostic JSON with SHA-256.

The generated point remains traceable to its source diagnostic file.

## Temperature characterization

At least three independent reference temperature points are required.

Each point contains:

```json
{
  "diagnostic_file": "evidence/temp-25c.json",
  "reference_temperature_c": 25.0
}
```

The reference temperature must come from an independent reference instrument or controlled source.

The assembler computes the mean trusted TMP117 reading and within-capture standard deviation while retaining the independent reference value.

## Stationary accelerometer characterization

The session lists one or more stationary diagnostic files and the expected gravity vector:

```json
{
  "expected_stationary_mg": {"x": 0.0, "y": 0.0, "z": 1000.0},
  "diagnostic_files": [
    "evidence/accel-stationary-01.json"
  ]
}
```

At least 20 trusted stationary samples must remain after validation. The assembler copies trusted X/Y/Z milli-g observations into the standard calibration-capture structure and records source ranges for traceability.

This is a static orientation/bias characterization, not a complete scale-factor, cross-axis, vibration-bandwidth, or frequency-response calibration.

## Diagnostic evidence requirements

Every diagnostic source must use schema:

```text
forgesense.calibration_diagnostic_capture.v1
```

The assembler accepts either the direct diagnostic object or the CLI wrapper:

```json
{
  "mode": "calibration",
  "result": {
    "schema": "forgesense.calibration_diagnostic_capture.v1"
  }
}
```

A source is rejected unless:

- `capture_pass` is true;
- sequence gaps are zero;
- sequence faults are zero;
- CRC/frame errors are zero;
- at least one trusted usable sample exists;
- authority states `read_only = true`;
- actuator control is forbidden;
- runtime calibration application is forbidden;
- hard-safety relaxation is forbidden.

This prevents manually altered or failed diagnostic evidence from silently entering the calibration fit.

## Evidence hashing

Every unique diagnostic file used by the session is hashed from its raw file bytes with SHA-256. The hash and source path are inserted into the generated calibration capture.

Do not edit a diagnostic file after assembling a capture. Any change produces a different SHA-256 and requires the capture to be regenerated.

## Assemble the capture

Example:

```bash
python tools/assemble_calibration_capture.py \
  evidence/session-01.json \
  --out build/calibration-capture-01.json
```

The output includes explicit authority metadata:

```text
assembled_from_read_only_diagnostics = true
independent_reference_values_required = true
automatic_runtime_application = false
may_relax_hard_safety_limits = false
```

It also includes aggregation metadata such as sample counts and observed within-capture standard deviations.

## Assemble and generate a proposal

A proposal can be generated in the same command:

```bash
python tools/assemble_calibration_capture.py \
  evidence/session-01.json \
  --out build/calibration-capture-01.json \
  --proposal-out build/calibration-proposal-01.json
```

The assembler reuses the standard proposal builder, so the resulting capture must be structurally compatible with the existing current, temperature, accelerometer, uncertainty, provenance, and review rules.

If the proposal fit does not meet quality limits, the capture is still valuable retained evidence but the command returns a non-zero result for the proposal path and `proposal_quality_pass` remains false.

## Repeated-run rule

One assembled capture is not enough to authorize a coefficient change.

Create independent sessions for at least three repeated calibration runs and pass their generated proposals through:

```bash
python tools/review_calibration.py ...
```

The repeated-run review remains a separate gate for coefficient spread, reference uncertainty, board/commit consistency, and evidence quality.

## Verification

Run:

```bash
make calibration-assembler-check
```

The gate checks:

- trusted diagnostic aggregation;
- signed/raw observation retention;
- independent reference requirements;
- raw evidence SHA-256 retention;
- duplicate-source rejection within a characterization;
- failed/sequence-broken evidence rejection;
- tampered authority rejection;
- proposal compatibility;
- absence of runtime calibration or actuator authority.
