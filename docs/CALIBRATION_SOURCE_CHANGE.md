# Approved Calibration Source Changes

## Purpose

ForgeSense keeps calibration evidence generation, engineering approval, source review, and runtime provisioning as separate authority boundaries.

A repeated-run campaign becoming `review_ready = true` is not enough to change firmware or FPGA calibration. The reviewer-ready package must first be explicitly approved for a source-controlled change. `tools/prepare_approved_calibration_source_change.py` then converts the approved floating candidates into the integer representation supported by `CalibrationRecord` v1, evaluates quantization against retained calibration evidence, snapshots hard-safety sources, and produces an add-only profile patch for source review.

The tool never performs a runtime write and never modifies hard-safety limits.

## Evidence chain

```text
read-only physical diagnostics
        |
        v
calibration sessions
        |
        v
repeated-run campaign + review
        |
        v
verified reviewer change package
        |
        v
explicit calibration approval manifest
        |
        v
integer quantization + evidence-point regression
        |
        v
hard-safety source baseline snapshot
        |
        v
add-only approved calibration profile patch
        |
        v
source-control review
```

Provisioning remains outside this workflow.

## Approval manifest

Start from:

```text
hardware/calibration/calibration_approval_template_v1.json
```

Schema:

```text
forgesense.calibration_approval.v1
```

The approval binds the reviewer decision to:

- campaign identifier;
- exact repository commit;
- evidence-root SHA-256;
- retained reviewer change-package SHA-256;
- reviewer name and role;
- UTC review timestamp;
- rationale;
- exact approved and deferred channels.

For `CalibrationRecord` v1, the required channel disposition is:

```text
approved_channels = [current, temperature]
deferred_channels = [accelerometer]
```

Accelerometer correction is deliberately deferred because the current 48-byte `CalibrationRecord` has temperature and current fields only. The workflow fails closed if an approval tries to silently include accelerometer correction.

The approval must also state:

```text
source_control_change_required = true
runtime_write_approved = false
automatic_runtime_application = false
hard_safety_limit_change_approved = false
```

## Source-change policy

The controlled policy is:

```text
hardware/calibration/calibration_source_change_policy_v1.json
```

Schema:

```text
forgesense.calibration_source_change_policy.v1
```

The policy defines:

- maximum rational denominator for current gain;
- maximum allowed current quantization error;
- non-negative current requirement at retained reference points;
- normalized output range;
- maximum allowed temperature offset quantization error;
- explicit absence of accelerometer runtime mapping;
- approved source-profile directory;
- prohibition on runtime-file modification;
- prohibition on overwriting an existing approved profile;
- hard-safety baseline files that must remain byte-identical.

The initial policy uses a maximum current gain denominator of `1,000,000`, matching the proposal-generation rationalization limit.

## Current coefficient conversion

The reviewer package provides:

```text
mean_slope_ma_per_count_candidate
mean_intercept_ma_candidate
```

The source-change tool converts these to the existing integer `LinearCalibration` representation:

```text
raw_zero = 0
gain_numerator / gain_denominator ~= slope mA/count
output_offset ~= intercept mA
```

`Fraction.limit_denominator()` is used deterministically under the policy maximum denominator.

The firmware transform is reproduced with truncation toward zero:

```text
output = trunc((raw - raw_zero) * gain_numerator / gain_denominator)
       + output_offset
```

The tool collects the retained `adc_raw` calibration points from every campaign capture and compares the integer transform against the approved floating candidate at those raw points.

The source-change package is rejected when:

- the slope is non-positive;
- integer fields exceed signed 32-bit range;
- a retained raw point exceeds signed 24-bit range;
- quantization error exceeds policy;
- mapped output exceeds normalized current range;
- mapped output becomes negative at a retained reference point.

This regression checks integer representation error. It does not replace the earlier fit-quality, repeated-run, uncertainty, or physical-evidence gates.

## Temperature coefficient conversion

The PHY temperature input is already signed deci-degrees Celsius. The approved constant temperature offset therefore maps to:

```text
raw_zero = 0
gain_numerator = 1
gain_denominator = 1
output_offset = round(mean_offset_c_candidate * 10)
```

The source-change gate records the resulting degree-Celsius quantization error and rejects it if the policy limit is exceeded.

## Accelerometer disposition

The reviewer package still carries the repeated-run accelerometer bias candidate and uncertainty evidence.

The approved source profile records that candidate for traceability but marks:

```text
status = deferred
runtime_mapping_supported = false
```

No accelerometer correction field is generated and no unsupported runtime behavior is invented.

Adding accelerometer calibration requires a separately reviewed calibration-record/interface extension.

## Hard-safety non-regression

Before producing the source patch, the tool hashes the policy-controlled hard-safety baseline files:

```text
fpga/rtl/safety/hard_limit_monitor.vhd
hardware/profiles/sensor_contract_v1.json
hardware/profiles/reference_circuit_v1.json
hardware/profiles/hardware_baseline_v1.json
hardware/profiles/power_entry_v1.json
docs/SAFETY_MODEL.md
```

The resulting `safety-baseline.json` records the exact SHA-256 of each file and states that hard-safety limit change approval is false. This covers digital hard limits plus the source-controlled analog/protection assumptions used by the active hardware baseline.

The generated patch is restricted to one new file under:

```text
hardware/calibration/approved/
```

It does not modify the FPGA hard-limit monitor, sensor contract, firmware runtime, ESP32 code, dashboard, analog protection profiles, power-entry settings, or provisioning path.

`tools/verify_calibration_source_change.py` re-hashes the baseline files. Any drift after package generation fails verification.

This is a structural hard-safety non-regression gate. It does not claim that physical calibration has been certified or that all safety behavior has been physically revalidated.

## Generate an approved source-change package

After the reviewer-ready package exists and the approval manifest has been completed:

```bash
python tools/prepare_approved_calibration_source_change.py \
  build/calibration-campaign-001 \
  --change-package-dir build/calibration-change-001 \
  --approval evidence/calibration-approval-001.json \
  --source-root evidence \
  --campaign-manifest evidence/campaign-001.json \
  --repo-root . \
  --policy hardware/calibration/calibration_source_change_policy_v1.json \
  --out-dir build/calibration-source-change-001
```

The retained reviewer package is reconstructed from the original campaign evidence before the approval is accepted. The retained `change-package.json`, `signing-request.json`, and exact signing payload must still match the verified campaign-derived package.

The output is:

```text
calibration-source-change-001/
  source-change.json
  approved-profile.json
  source-change.patch
  safety-baseline.json
  artifact-index.json
```

`source-change.patch` is an add-only patch for the approved profile. It is review input, not an automatic patch application command.

## Source-change schemas

The approved profile uses:

```text
forgesense.approved_calibration_source_profile.v1
```

The source-change summary uses:

```text
forgesense.calibration_source_change.v1
```

The artifact index uses:

```text
forgesense.calibration_source_change_artifact_index.v1
```

The profile records candidate `CalibrationRecord` fields, current regression points, temperature quantization error, deferred accelerometer evidence, campaign provenance, approval provenance, and the no-runtime-write authority boundary.

## Structural verification

Run:

```bash
python tools/verify_calibration_source_change.py \
  build/calibration-source-change-001 \
  --approval evidence/calibration-approval-001.json \
  --change-package-dir build/calibration-change-001 \
  --repo-root . \
  --policy hardware/calibration/calibration_source_change_policy_v1.json \
  --report-out build/calibration-source-change-001-verification.json
```

The structural verifier checks:

- artifact-index root SHA-256;
- exact expected artifact set;
- every artifact SHA-256;
- reviewer approval binding;
- reviewer change-package binding;
- policy binding;
- profile and source-change authority;
- current and temperature quantization regression state;
- explicit accelerometer deferral;
- add-only patch structure and target directory;
- hard-safety baseline hashes;
- absence of runtime/hard-safety source changes.

If the approved profile patch has already been applied, verification accepts the repository target only when its bytes are identical to `approved-profile.json`. A different pre-existing file is rejected.

## Full evidence re-derivation verification

For the stronger verification path, re-derive the reviewer package and integer coefficients from the original campaign evidence:

```bash
python tools/verify_calibration_source_derivation.py \
  build/calibration-source-change-001 \
  --bundle build/calibration-campaign-001 \
  --change-package-dir build/calibration-change-001 \
  --approval evidence/calibration-approval-001.json \
  --source-root evidence \
  --campaign-manifest evidence/campaign-001.json \
  --repo-root . \
  --policy hardware/calibration/calibration_source_change_policy_v1.json \
  --report-out build/calibration-source-change-001-derivation.json
```

This verifier does not trust the generated source-change package merely because its self-hashes are internally consistent. It reconstructs the reviewer package from the original campaign evidence, revalidates the approval semantics, reloads the retained current raw points, recomputes current and temperature quantization, and compares the approved profile coefficients and regression records with the independently re-derived result.

The full verification therefore binds the final profile back to the same original evidence chain used to produce the reviewer package.

## Authority boundary

The entire workflow preserves:

```text
runtime_write_permitted = false
automatic_runtime_application = false
may_control_actuators = false
may_relax_hard_safety_limits = false
```

A reviewer approval permits preparation of a source-controlled calibration profile proposal only. It does not authorize a runtime write, flash operation, FPGA coefficient update, ESP32 calibration update, or hard-safety limit modification.

A later provisioning design must have a separate authority model, rollback protection, deterministic regression coverage, and explicit hardware validation.

## Repository verification gate

Run:

```bash
make calibration-source-change-check
```

The gate covers deterministic current quantization, negative-current rejection, temperature quantization, mandatory accelerometer deferral, source-change artifact verification, patch tamper rejection, hard-safety baseline drift rejection, post-apply identical-profile verification, and source-level presence of the full evidence re-derivation verifier.

Synthetic test values verify workflow arithmetic and authority behavior only. They are not retained physical calibration evidence.
