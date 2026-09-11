# Maintenance-Only Physical Calibration Provisioning

## Purpose

ForgeSense separates physical calibration writes from the production ESP32 runtime and from the transparent commissioning bridge.

The dedicated target under `firmware/esp32_calibration_maintenance/` exists only to support a controlled maintenance procedure after the complete calibration evidence chain has already been reviewed, approved, source-controlled, converted into a deterministic `CalibrationRecord v1`, and independently re-verified.

This target does not add a calibration write command to the production runtime, dashboard, telemetry API, or the existing USB-to-FPGA commissioning bridge.

The implemented workflow is:

```text
read-only device-state capture
        -> approved source profile
        -> verified provisioning package
        -> explicit operator write confirmation
        -> physical maintenance gate asserted
        -> physical load-output inhibit asserted
        -> PREPARE exact 48-byte record
        -> fresh commit challenge
        -> physical gates checked again
        -> COMMIT to inactive NVS slot
        -> byte-for-byte storage readback
        -> immediate device status readback
        -> retained physical provisioning evidence
        -> manual reboot or power cycle
        -> retained sequence/CRC recovery verification
```

No physical provisioning result is claimed merely because this code exists. A physical claim requires retained device evidence produced by the actual maintenance procedure.

## Dedicated firmware target

The maintenance target is:

```text
firmware/esp32_calibration_maintenance/
```

It is intentionally separate from:

```text
firmware/esp32/                 # production runtime
firmware/esp32_commissioning/   # transparent USB <-> FPGA bridge
```

The maintenance image does not forward USB traffic to the FPGA UART. It exposes only the bounded maintenance protocol over USB Serial/JTAG.

### Default-disabled physical gates

Two independent GPIO inputs are required:

- physical maintenance-enable input;
- physical load-output-inhibit sense input.

Their Kconfig defaults are both `-1`, meaning unassigned and therefore write-disabled.

```text
CONFIG_FORGESENSE_MAINTENANCE_ENABLE_GPIO=-1
CONFIG_FORGESENSE_LOAD_INHIBIT_SENSE_GPIO=-1
```

No pin numbers are guessed in the repository. The values must only be assigned after the actual maintenance wiring is frozen and reviewed for the selected board assembly.

The firmware configures these lines as inputs without enabling internal pulls. External hardware must therefore establish defined asserted and deasserted levels.

A calibration record cannot be prepared or committed unless both configured physical signals are asserted. Both signals are checked again immediately before COMMIT.

## Device identity

The maintenance image reports the ESP32-S3 default eFuse MAC as the device identity.

The host representation is:

```text
esp32s3:<12 lowercase hexadecimal MAC digits>
```

Example format only:

```text
esp32s3:aabbccddeeff
```

The provisioning package `device_id` must exactly match the identity returned by the maintenance image. A mismatch blocks the write before PREPARE.

## Read-only status capture

Before generating a provisioning package, install the dedicated maintenance image and use the read-only status command:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py status \
  --port <SERIAL_PORT> \
  --report-out evidence/calibration-device-state-001.json
```

The command issues only `QUERY_STATUS`. It does not send PREPARE or COMMIT.

The retained JSON uses:

```text
forgesense.calibration_device_state.v1
```

It records:

- eFuse-derived device identity;
- UTC capture time;
- installed calibration sequence;
- installed record CRC when an active record exists;
- physical maintenance-enable observation;
- physical load-output-inhibit observation;
- the complete maintenance status readback.

This file can be supplied to `tools/prepare_calibration_provisioning.py` as `--device-state`.

A status capture is still only a point-in-time observation. The physical gates are rechecked by firmware during PREPARE and COMMIT.

## Maintenance protocol

Frames use:

```text
magic       4 bytes  "FSM1"
version     1 byte   1
opcode      1 byte
length      2 bytes  little-endian payload length
payload     0..64 bytes
crc32       4 bytes  little-endian CRC32/IEEE over header + payload
```

The firmware parser is fixed-memory, bounds payloads to 64 bytes, validates CRC before dispatch, and resynchronizes on the protocol magic after malformed data.

### Opcodes

```text
0x01 QUERY_STATUS
0x02 PREPARE_RECORD
0x03 COMMIT_RECORD
0x81 STATUS_RESPONSE
0x82 PREPARE_RESPONSE
0x83 COMMIT_RESPONSE
```

### Status response

A successful status response carries:

```text
status                  u8
ESP32 eFuse MAC         6 bytes
boot nonce              u32 little-endian
maintenance asserted    u8
load inhibit asserted   u8
store ready             u8
has active record       u8
installed sequence      u32 little-endian
installed record CRC    u32 little-endian
pending sequence        u32 little-endian
```

The boot nonce is generated for each maintenance-image boot and is used to bind PREPARE and COMMIT to the current boot session.

## PREPARE

PREPARE never changes NVS.

The request contains:

```text
boot nonce                 u32
expected installed floor   u32
CalibrationRecord v1       48 bytes
```

The device requires:

- both physical gates asserted;
- calibration store recovered and ready;
- matching boot nonce;
- expected installed floor equal to the currently recovered floor;
- valid `CalibrationRecord v1` structure and CRC;
- candidate sequence strictly newer than the installed floor;
- non-wrapping sequence policy.

A successful PREPARE retains the exact record bytes only in RAM and returns:

```text
status            u8
candidate sequence u32
record CRC         u32
commit nonce       u32
```

The commit nonce is freshly generated for the pending record.

## COMMIT

The request contains:

```text
boot nonce                 u32
commit nonce               u32
expected pending sequence  u32
```

Before writing, firmware checks both physical gate inputs again. It also requires the boot nonce, commit nonce, pending sequence, and installed floor to still match the PREPARE state.

The NVS write uses the same dual-slot policy as the verified provisioning design:

```text
1. choose inactive slot
2. encode candidate record
3. write inactive slot
4. NVS commit
5. read inactive slot back
6. require byte-for-byte equality
7. decode and validate the retained record
8. write active-slot and sequence-floor metadata
9. NVS commit
10. update the in-memory active record
```

The maintenance service then loads and re-encodes the active record and requires exact byte equality with the PREPARE blob before returning success.

If a storage/metadata/readback failure occurs, the service marks the calibration store unavailable for the remainder of that boot. Another write cannot be attempted until reboot recovery runs again.

The firmware deliberately does not call `nvs_flash_erase()` as an error-recovery shortcut. Calibration state is evidence-bearing persistent data and initialization failures are fail-closed.

## Host-side trust ordering

The physical APPLY command first calls the existing full provisioning verifier:

```text
verify_calibration_provisioning.verify_provisioning_bundle(...)
```

That verification re-establishes the complete retained source/evidence chain, record derivation, artifact hashes, candidate sequence, and hard-safety non-regression boundary.

Only after that succeeds does the tool accept the explicit operator write confirmation. Only after both checks does it open the serial device.

The exact write confirmation is:

```text
CALIBRATION-WRITE
```

A different value blocks the operation before the serial port is opened.

## Physical APPLY command

Example command structure:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py apply \
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
  --provisioning-policy hardware/calibration/calibration_provisioning_policy_v1.json \
  --port <SERIAL_PORT> \
  --operator "<OPERATOR>" \
  --confirm-write CALIBRATION-WRITE \
  --report-out evidence/calibration-physical-provisioning-001.json
```

The APPLY path checks the reported device identity, store readiness, both physical gates, installed sequence, candidate sequence, PREPARE acknowledgement, COMMIT acknowledgement, and immediate post-write sequence/CRC.

The exact `calibration-record.bin` retained in the provisioning package is sent to PREPARE. The host does not regenerate a different record during the physical write.

## Physical provisioning evidence

A successful APPLY report uses:

```text
forgesense.calibration_physical_provisioning.v1
```

It records:

- UTC timestamp;
- operator;
- provisioning artifact-index root;
- exact provisioning JSON hash;
- exact record SHA-256;
- candidate sequence and CRC;
- device identity;
- boot nonce;
- pre-write status;
- PREPARE acknowledgement and commit challenge;
- COMMIT acknowledgement;
- immediate post-write status;
- `commit_verified = true`;
- `reboot_recovery_verified = false` until a later boot is observed;
- the no-actuator/no-hard-limit authority boundary.

This evidence means only that the maintenance protocol observations were retained for the write. It does not establish calibration accuracy, reference traceability, industrial certification, or hardware-backed anti-rollback protection.

## Reboot recovery verification

After a successful APPLY, manually reboot or power-cycle the maintenance device and run:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py verify-reboot \
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
  --provisioning-policy hardware/calibration/calibration_provisioning_policy_v1.json \
  --port <SERIAL_PORT> \
  --evidence evidence/calibration-physical-provisioning-001.json \
  --report-out evidence/calibration-physical-provisioning-001-reboot.json
```

This operation sends only `QUERY_STATUS` after re-verifying the provisioning package on the host.

It requires:

- the same eFuse-derived device identity;
- a different boot nonce;
- recovered calibration store ready;
- an active retained record;
- exactly the committed sequence;
- exactly the committed record CRC;
- no pending record.

Only then is `reboot_recovery_verified` set to `true`.

A changed boot nonce is evidence that a different maintenance-image boot was observed. It is not a cryptographic proof of power removal.

## Anti-rollback boundary

The maintenance writer preserves the strict NVS sequence floor. It cannot intentionally commit an equal or lower sequence.

This is still not a hardware-backed monotonic counter. Restoration of an older complete flash/NVS image may restore both the calibration record and its floor. The maintenance workflow therefore does not claim resistance to an adversary with raw storage snapshot restoration capability.

Any stronger anti-rollback design must use a separate reviewed trust anchor or standard secure-hardware mechanism.

## Authority boundary

This implementation does not:

- expose calibration writes through the production runtime;
- expose calibration writes through dashboard or HTTP APIs;
- modify the transparent commissioning bridge;
- send FPGA control commands;
- energize the protected load;
- alter FPGA current/temperature hard limits;
- alter analog comparator, eFuse, fuse, E-stop, or protected-output thresholds;
- automatically select a calibration profile;
- automatically provision a device;
- erase calibration NVS on recovery failure.

The physical load-inhibit observation is a prerequisite for calibration storage; it is not an actuator command.

## Verification gate

Run:

```bash
make maintenance-provisioning-check
```

The gate includes synthetic Python protocol/workflow tests, a C++ host test for the bounded frame parser and CRC, and a source-level authority checker.

The tests cover fragmentation and CRC corruption, device mismatch, open physical gates, stale installed sequence, rejected PREPARE, commit-challenge mismatch, post-write mismatch, successful evidence generation, required changed boot nonce, and retained sequence/CRC after reboot.

These tests verify software behavior only. They are not evidence that the selected ESP32-S3 target compiled, that physical gates are correctly wired, that a real NVS write occurred, or that a calibrated physical system meets an accuracy target.
