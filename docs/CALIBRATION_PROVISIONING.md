# Staged Calibration Provisioning

## Purpose

ForgeSense now has a controlled boundary between an approved source calibration profile and a device-storable `CalibrationRecord` image. This boundary is intentionally narrower than a general runtime configuration interface.

The workflow can prepare and independently verify the exact 48-byte calibration record that a controlled maintenance path may later store. The ESP32 firmware also contains a dual-slot NVS storage primitive with strict sequence ordering, staged write/readback verification, and recovery from an interrupted metadata commit.

There is still no UART, dashboard, HTTP, telemetry, or normal-runtime command that provisions calibration. Adding such a transport requires a separate review.

## Evidence chain

```text
physical diagnostic evidence
        -> repeated calibration campaign
        -> reviewer-ready package
        -> evidence verification
        -> explicit reviewer approval
        -> approved source profile
        -> full source re-derivation verification
        -> device-state declaration
        -> deterministic CalibrationRecord v1 image
        -> provisioning package verification
        -> controlled maintenance integration only
```

The provisioning package does not itself write a device.

## Provisioning policy

The controlled policy is:

```text
hardware/calibration/calibration_provisioning_policy_v1.json
```

Schema:

```text
forgesense.calibration_provisioning_policy.v1
```

The policy freezes the following requirements:

- sequence numbers start at 1;
- a candidate sequence must be strictly greater than the installed sequence;
- sequence wraparound is not supported;
- `CalibrationRecord v1` remains 48 bytes, little-endian, with CRC32/IEEE;
- storage uses two NVS slots;
- boot recovery selects the highest valid sequence;
- equal-sequence records with different bytes are rejected as ambiguous;
- package-time maintenance-mode confirmation is required;
- package-time physical load-output inhibition confirmation is required;
- those safety preconditions must be checked again at actual write time;
- no remote provisioning command is declared;
- no automatic provisioning is authorized;
- calibration provisioning cannot control actuators or relax hard-safety limits;
- no hardware-backed monotonic counter is claimed.

## Device-state input

Start from:

```text
hardware/calibration/calibration_device_state_template_v1.json
```

Schema:

```text
forgesense.calibration_device_state.v1
```

A completed device-state record includes a device identifier, UTC capture time, installed calibration sequence, optional installed record CRC, maintenance-mode confirmation, physical load-output inhibition confirmation, and the source of that information.

This record is an input declaration. It does not prove that a physical device remains in the same state later. The provisioning package therefore records:

```text
write_time_recheck_required = true
```

A future physical writer must re-check maintenance state, output inhibition, device identity, installed sequence, and retained record before committing a new calibration.

## Deterministic record encoding

`tools/prepare_calibration_provisioning.py` first runs the full source derivation verification from `tools/verify_calibration_source_derivation.py`. The approved profile is therefore not accepted merely because it is present on disk.

The tool then encodes the source-controlled current and temperature coefficients into the existing firmware record layout:

```text
uint32 magic        = 0x46534331  // FSC1
uint16 version      = 1
uint16 size         = 48
uint32 sequence
LinearCalibration temperature    // four int32 fields
LinearCalibration current        // four int32 fields
uint32 crc32_ieee
```

The first 44 bytes are protected with the same CRC32/IEEE algorithm used by the C++ firmware implementation. The generated record is retained in both binary and hexadecimal form.

## Generate a provisioning package

After a source-change package has passed full derivation verification and a fresh device-state declaration has been captured:

```bash
python tools/prepare_calibration_provisioning.py \
  build/calibration-source-change-001 \
  --bundle build/calibration-campaign-001 \
  --change-package-dir build/calibration-change-001 \
  --approval evidence/calibration-approval-001.json \
  --source-root evidence \
  --campaign-manifest evidence/campaign-001.json \
  --repo-root . \
  --source-change-policy hardware/calibration/calibration_source_change_policy_v1.json \
  --device-state evidence/calibration-device-state-001.json \
  --provisioning-policy hardware/calibration/calibration_provisioning_policy_v1.json \
  --sequence 5 \
  --out-dir build/calibration-provisioning-001
```

The output is:

```text
calibration-provisioning-001/
  provisioning.json
  calibration-record.bin
  calibration-record.hex
  artifact-index.json
```

`provisioning.json` binds the exact device-state bytes, approved-profile bytes, source-change summary, campaign provenance, reviewer approval, requested sequence, record SHA-256, and record CRC.

`artifact-index.json` hashes all generated artifacts and carries a canonical SHA-256 root.

## Independent verification

Run:

```bash
python tools/verify_calibration_provisioning.py \
  build/calibration-provisioning-001 \
  --source-change-dir build/calibration-source-change-001 \
  --bundle build/calibration-campaign-001 \
  --change-package-dir build/calibration-change-001 \
  --approval evidence/calibration-approval-001.json \
  --source-root evidence \
  --campaign-manifest evidence/campaign-001.json \
  --repo-root . \
  --source-change-policy hardware/calibration/calibration_source_change_policy_v1.json \
  --device-state evidence/calibration-device-state-001.json \
  --provisioning-policy hardware/calibration/calibration_provisioning_policy_v1.json
```

The verifier:

- recomputes the artifact-index root;
- re-hashes every generated artifact;
- reruns full source derivation verification;
- revalidates the device-state and provisioning policy;
- enforces strictly increasing sequence numbers;
- re-encodes the 48-byte record from the approved source profile;
- compares the re-encoded bytes with `calibration-record.bin`;
- checks the hexadecimal copy;
- checks CRC32 and record SHA-256 metadata;
- checks that package provenance matches the approved profile;
- preserves the no-actuator/no-hard-limit authority boundary.

The verifier reports `device_write_performed = false`.

## Firmware dual-slot store

The reusable record-selection contract is implemented in:

```text
firmware/components/forgesense_sensing/
  forgesense_calibration_provisioning.cpp
  include/forgesense_calibration_provisioning.h
```

The ESP32 NVS adapter is:

```text
firmware/esp32/main/calibration_store_nvs.cpp
firmware/esp32/main/calibration_store_nvs.hpp
```

The NVS namespace is `fs_cal` and the record slots are `slot0` and `slot1`.

### Boot recovery

At startup, the store reads both slots and the stored sequence floor. Each present slot must decode as a valid `CalibrationRecord` with valid CRC and coefficient structure.

The store fails closed when:

- a present slot is corrupt;
- both slots contain the same sequence but different bytes;
- no valid record exists while the stored floor indicates that a record should exist;
- the newest valid record sequence is lower than the stored floor.

If a newer valid slot exists because power failed after the slot commit but before metadata commit, the store selects that highest valid sequence and repairs the active-slot/floor metadata.

### Staged commit

A candidate record must have a non-zero sequence strictly greater than the recovered floor.

The write order is:

```text
1. encode candidate CalibrationRecord
2. choose inactive slot
3. write inactive slot
4. NVS commit
5. read the slot back
6. require byte-for-byte equality
7. decode and require expected sequence
8. write active-slot metadata and new sequence floor
9. NVS commit
10. update in-memory active record
```

The active slot is not overwritten first. This preserves the previous committed record across a failure during staging.

## Anti-rollback boundary

The sequence floor prevents accidental or ordinary software rollback while the NVS state remains intact. Boot recovery also prevents a lower-sequence slot from replacing a newer retained calibration.

This is not a hardware-backed anti-rollback mechanism. An attacker or maintenance action capable of restoring an older complete flash/NVS snapshot may also restore the stored sequence floor. ForgeSense therefore does not claim protection against raw storage snapshot rollback in this implementation.

A stronger future design may bind calibration sequence state to secure hardware, authenticated maintenance credentials, or another monotonic trust anchor. Such a change must use standard cryptographic mechanisms and receive a separate security review.

## Runtime authority boundary

This implementation deliberately does not add a runtime entrypoint that calls `stage_and_commit()` from UART, telemetry, dashboard, or normal application traffic. `app_main.cpp` remains unchanged by this work.

The NVS store compiles into the ESP32 build so its storage contract is available for a future controlled maintenance integration, but ordinary runtime traffic cannot reach it through a newly added command.

Calibration storage does not alter FPGA hard limits, analog protection thresholds, eFuse settings, E-stop behavior, or protected-output authority.

## Verification gate

Run:

```bash
make calibration-provisioning-check
```

The gate includes Python tests for deterministic record encoding, sequence rollback rejection, safe-state declarations, package re-verification, binary tamper rejection, and exact device-state binding. It also compiles and runs a host C++ test for slot selection, corrupt-record rejection, rollback detection, and equal-sequence ambiguity.

Synthetic tests are software verification only. No physical device was provisioned and no physical calibration result is claimed by this implementation.
