# Calibration Recovery and Maintenance Authority Rotation

## Purpose

ForgeSense calibration recovery is not a sequence rollback. If an earlier approved calibration profile must be restored, the earlier coefficients are re-encoded into a new `CalibrationRecord v1` using the next higher sequence number. The signed maintenance path then treats that recovery record exactly like any other authorized calibration write.

The recovery workflow exists to preserve three independent properties:

- an earlier coefficient set must still come from a fully approved and re-verifiable calibration source profile;
- the device calibration sequence must continue increasing monotonically;
- the recovery write must retain the same physical-gate and signed-maintenance authorization requirements as a normal calibration write.

The workflow does not claim hardware-backed anti-rollback. Restoring a complete older flash/NVS image can still restore both records and the software-maintained sequence floor unless a separate hardware monotonic mechanism is introduced.

## Exact active-record evidence

The maintenance firmware provides a read-only active-record query:

```text
0x05 QUERY_ACTIVE_RECORD
0x85 ACTIVE_RECORD_RESPONSE
```

A successful response is:

```text
status                  u8
has active record       u8
CalibrationRecord v1    48 bytes
```

When no active record exists, `has active record` is zero and the 48 record bytes are zero.

The status command records the exact active record in `forgesense.calibration_device_state.v1` as:

```text
active_record_sha256
active_record_hex
installed_sequence
installed_record_crc32
```

The recovery builder and verifier require all four values to agree with the same 48-byte record.

This readback is evidence of the record returned by the dedicated maintenance image. It is not a metrological measurement and it does not establish calibration accuracy.

## Recovery sequence semantics

Recovery requires:

```text
candidate sequence = installed sequence + 1
```

The sequence is never decremented.

Example:

```text
active record sequence:    12
approved profile to restore: coefficients previously used at sequence 7
recovery record sequence:  13
```

The coefficients may match an older approved profile, but the serialized record is new because its sequence and CRC are new.

The recovery builder rejects:

- missing exact active-record evidence;
- invalid active-record SHA-256;
- sequence/CRC disagreement between device state and exact record bytes;
- sequence exhaustion at the non-wrapping upper boundary;
- a target profile whose current/temperature coefficient bytes are identical to the currently active coefficient bytes;
- a recovery reason shorter than the minimum reviewable description;
- any source profile that fails the existing source-derivation/provisioning chain.

A same-coefficient recovery is treated as a no-op and is not allowed to consume a sequence number.

## Recovery package

Prepare a fresh device-state capture first:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py status \
  --port <SERIAL_PORT> \
  --report-out evidence/calibration-device-state-current.json
```

Then build the recovery package from the earlier approved source-change evidence:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/prepare_calibration_recovery.py \
  build/earlier-approved-source-change \
  --bundle build/earlier-calibration-campaign \
  --change-package-dir build/earlier-change-package \
  --approval evidence/earlier-approval.json \
  --source-root evidence \
  --campaign-manifest evidence/earlier-campaign.json \
  --repo-root . \
  --source-change-policy hardware/calibration/calibration_source_change_policy_v1.json \
  --device-state evidence/calibration-device-state-current.json \
  --provisioning-policy hardware/calibration/calibration_provisioning_policy_v1.json \
  --reason "Restore the previously approved profile after observed calibration regression" \
  --out-dir build/calibration-recovery-001
```

The output remains a normal provisioning artifact set:

```text
provisioning.json
calibration-record.bin
calibration-record.hex
artifact-index.json
```

`provisioning.json` additionally contains:

```text
intent.schema = forgesense.calibration_recovery_intent.v1
intent.mode = restore_approved_profile_with_new_sequence
```

The intent binds:

- exact active record sequence, CRC32, and SHA-256;
- target approved campaign and approval IDs;
- exact approved-profile SHA-256;
- exact candidate-record SHA-256;
- installed and candidate sequence;
- explicit `decrement_permitted = false`;
- explicit `increment_exactly_one = true`;
- signed-maintenance authorization requirement;
- no automatic recovery, no actuator authority, and no hard-safety relaxation.

Because `provisioning.json` is part of the provisioning artifact index, changing the recovery intent changes the artifact root that is later included in the signed maintenance authorization payload.

## Independent recovery verification

Run:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/verify_calibration_recovery.py \
  build/calibration-recovery-001 \
  --source-change-dir build/earlier-approved-source-change \
  --bundle build/earlier-calibration-campaign \
  --change-package-dir build/earlier-change-package \
  --approval evidence/earlier-approval.json \
  --source-root evidence \
  --campaign-manifest evidence/earlier-campaign.json \
  --repo-root . \
  --source-change-policy hardware/calibration/calibration_source_change_policy_v1.json \
  --device-state evidence/calibration-device-state-current.json \
  --provisioning-policy hardware/calibration/calibration_provisioning_policy_v1.json
```

The verifier first re-runs the normal provisioning verifier, including source derivation and hard-safety non-regression. It then independently checks the recovery intent, exact active record, next-sequence rule, target approved-profile hashes, and non-no-op coefficient change.

## Signing a recovery

Recovery does not receive a separate bypass signature type. Use the existing maintenance authorization request tool with the recovery provisioning directory.

The request tool detects `forgesense.calibration_recovery_intent.v1` and requires the independent recovery verifier to pass before it emits `authorization-payload.bin`.

The signed bytes still bind:

```text
maintenance authorization domain
+ device eFuse MAC
+ expected installed sequence
+ provisioning artifact-index root
+ exact candidate CalibrationRecord v1
```

The provisioning artifact root transitively binds the recovery intent and target profile provenance.

A recovery therefore requires the same external P-256 signature and the same pinned public key as a normal calibration write.

## Physical recovery write

Use the existing `apply` command with the recovery provisioning directory and its signed authorization package.

Before opening the serial port, the host requires:

- strict signed provisioning policy;
- full provisioning verification;
- full recovery verification;
- detached signature verification.

After opening the device, the host additionally reads the exact active record again. If its SHA-256, sequence, or CRC has changed since the recovery package was created, the write stops before PREPARE.

After COMMIT, the host reads the exact active record again and requires its SHA-256 to match the committed recovery record.

Retained evidence records both the prior active record and the new recovery record and states:

```text
monotonic_sequence_preserved = true
sequence_decrement_performed = false
```

## Maintenance authority key rotation

The maintenance signing public key is deliberately not writable through the calibration maintenance protocol.

The machine-readable policy is:

```text
hardware/calibration/maintenance_authority_policy_v1.json
```

Current rotation rules are:

- signature algorithm remains ECDSA P-256/SHA-256 with DER ECDSA signatures;
- the private key is external to the repository, device, and ForgeSense signing-request/package tools;
- the maintenance firmware contains only the reviewed public key;
- the public-key SHA-256 fingerprint is readable for pre-write matching;
- there is no runtime or remote key-update opcode;
- there is no dual-key overlap mode;
- a key change requires source review and a newly built maintenance image;
- revoking the previous key therefore requires installing a maintenance image pinned to the new public key;
- a normal calibration write can never rotate the authority key.

This deliberately avoids creating a second writable trust store inside calibration NVS.

## Key rotation procedure

A reviewed rotation should follow this boundary:

```text
new external private/public key pair created under the owner's key-management process
-> public key DER/fingerprint reviewed
-> Kconfig public-key pin changed in maintenance-image source/build configuration
-> source review
-> new maintenance image built and verified
-> image installed through the separately controlled firmware-update procedure
-> QUERY_AUTHORIZATION confirms the new fingerprint
-> old signing key is no longer accepted by the new maintenance image
```

ForgeSense does not currently implement a dual-signature transition or hardware-backed key revocation counter. Those would require a separate security design and validation effort.

## Safety authority boundary

Recovery and authority rotation do not:

- change FPGA hard-current or hard-temperature thresholds;
- change analog comparator/eFuse/fuse/E-stop thresholds;
- authorize protected-load energization;
- send FPGA control commands;
- add dashboard or production-runtime calibration writes;
- decrease the calibration sequence;
- automatically select or restore a profile;
- automatically rotate a key;
- store a private signing key on the ESP32-S3;
- claim hardware-backed anti-rollback.

## Verification gate

Run:

```bash
make calibration-recovery-check
```

The gate covers exact active-record query framing, next-sequence recovery packaging, no-op rejection, active-record tamper detection, recovery runtime binding, signed policy enforcement, and the source-review-only maintenance-authority rotation boundary.

These are software verification artifacts only. A real target build, real key rotation, physical maintenance wiring, real calibration write, and physical accuracy result each require separate retained evidence.
