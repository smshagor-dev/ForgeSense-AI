# Calibration Recovery and Maintenance Authority Rotation

## Purpose

ForgeSense calibration recovery is not a sequence rollback. If an earlier approved calibration profile must be restored, the earlier coefficients are re-encoded into a new `CalibrationRecord v1` using the next higher sequence number. The signed maintenance path then treats that recovery record exactly like any other authorized calibration write.

The recovery workflow preserves four independent properties:

- an earlier coefficient set must still come from a fully approved and re-verifiable calibration source profile;
- the device calibration sequence must continue increasing monotonically;
- the recovery write must retain the same physical-gate and signed-maintenance authorization requirements as a normal calibration write;
- the live device state and signer fingerprint must continue the per-device calibration audit ledger before PREPARE is allowed.

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

## Audit-ledger continuity

Every physical recovery write also requires an already initialized per-device calibration audit ledger.

The ledger is initialized only at sequence zero before the first calibration write. It cannot be initialized later around an existing nonzero device state to invent missing history.

Before a recovery write, the host verifies the complete ledger chain. After opening the dedicated maintenance transport but before PREPARE, it reads the live:

- device identity;
- installed sequence;
- exact active-record SHA-256;
- pinned maintenance-authority public-key SHA-256.

All four must match the current ledger head. The recovery package separately binds the same active record as its `from_active_record` state.

The physical command therefore checks both:

```text
live device -> audit-ledger continuity
live device -> recovery package source-state continuity
```

A mismatch in either path stops before signed PREPARE.

See [`CALIBRATION_AUDIT_LEDGER.md`](CALIBRATION_AUDIT_LEDGER.md).

## Recovery sequence semantics

Recovery requires:

```text
candidate sequence = installed sequence + 1
```

The sequence is never decremented.

Example:

```text
active record sequence:      12
approved profile to restore: coefficients previously used at sequence 7
recovery record sequence:    13
```

The coefficients may match an older approved profile, but the serialized record is new because its sequence and CRC are new.

The recovery builder rejects:

- missing exact active-record evidence;
- invalid active-record SHA-256;
- sequence/CRC disagreement between device state and exact record bytes;
- sequence exhaustion at the non-wrapping upper boundary;
- a target profile whose current/temperature coefficient bytes are identical to the active coefficient bytes;
- a recovery reason shorter than the minimum reviewable description;
- any source profile that fails the existing source-derivation/provisioning chain;
- a provisioning policy that does not require signed authorization and monotonic recovery.

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

Because `provisioning.json` is part of the provisioning artifact index, changing the recovery intent changes the artifact root later included in the signed maintenance authorization payload.

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

The verifier re-runs the normal provisioning verifier, including source derivation and hard-safety non-regression, then independently checks recovery intent, exact active record, next-sequence rule, target approved-profile hashes, and non-no-op coefficient change.

## Signing a recovery

Recovery does not receive a bypass signature type. Use the existing maintenance authorization request tool with the recovery provisioning directory.

The request tool detects `forgesense.calibration_recovery_intent.v1` and requires independent recovery verification before it emits `authorization-payload.bin`.

The signed bytes bind:

```text
maintenance authorization domain
+ device eFuse MAC
+ expected installed sequence
+ provisioning artifact-index root
+ exact candidate CalibrationRecord v1
```

The provisioning artifact root transitively binds the recovery intent and target profile provenance.

A recovery therefore requires the same external P-256 signature and pinned public key as a normal calibration write.

## Physical recovery write

Use the existing `apply` command with the recovery provisioning directory, signed authorization package, and per-device audit ledger.

Required audit arguments are:

```text
--audit-ledger evidence/calibration-audit/esp32s3-aabbccddeeff
--audit-policy hardware/calibration/calibration_audit_ledger_policy_v1.json
```

Before opening the serial port, the host requires:

- strict signed provisioning policy;
- full provisioning verification;
- full recovery verification;
- audit-ledger structural/hash-chain verification;
- detached signature verification.

After opening the device but before PREPARE, the host reads the exact active record and signer fingerprint again. If device ID, sequence, record SHA-256, or signer fingerprint differs from the ledger head, the write stops. If the exact active record also differs from the recovery package source binding, the write stops.

After COMMIT, the host reads the exact active record again and requires its SHA-256 to match the committed recovery record.

Retained evidence records both prior and new recovery records and states:

```text
monotonic_sequence_preserved = true
sequence_decrement_performed = false
```

The retained physical report also records the audit-ledger head and entry count verified before the operation. The report is saved before its hash is appended as a `recovery_commit` ledger entry.

## Reboot verification after recovery

A later `verify-reboot` operation again requires the same audit ledger. The live exact record must match the current ledger head before reboot evidence is accepted.

For recovery evidence, the read-only recovery verifier also requires the exact active-record SHA-256 and sequence to equal the committed recovery record.

The retained reboot report is then appended as a non-mutating `reboot_verified` ledger event.

## Maintenance authority key rotation

The maintenance signing public key is deliberately not writable through the calibration maintenance protocol.

The machine-readable policy is:

```text
hardware/calibration/maintenance_authority_policy_v1.json
```

Current rotation rules are:

- signature algorithm remains ECDSA P-256/SHA-256 with DER signatures;
- the private key is external to the repository, device, and ForgeSense request/package tools;
- maintenance firmware contains only the reviewed public key;
- public-key SHA-256 is readable for pre-write matching;
- there is no runtime or remote key-update opcode;
- there is no dual-key overlap mode;
- a key change requires source review and a rebuilt maintenance image;
- a normal calibration write can never rotate the authority key.

This avoids a second writable trust store inside calibration NVS.

## Key rotation and audit-ledger boundary

A reviewed firmware-level key rotation can replace the public key pinned in a rebuilt maintenance image, but the current calibration audit ledger deliberately treats an unexpected signer fingerprint change as a discontinuity.

Therefore, after a maintenance image is installed with a different authority key:

```text
QUERY_AUTHORIZATION can confirm the new fingerprint
but
calibration audit preflight rejects the changed fingerprint
```

No current command silently advances the ledger across that key transition. Calibration writes remain blocked until a separately reviewed key-transition evidence workflow is implemented.

This is intentional fail-closed behavior. It prevents a compromised or accidentally rebuilt maintenance image from silently redefining calibration-write authority.

ForgeSense does not currently implement dual-signature key transition, cross-signing, or hardware-backed key revocation counters.

## Key rotation build procedure

The source/build-side rotation boundary remains:

```text
new external private/public key pair created under the owner's key-management process
-> public key DER/fingerprint reviewed
-> Kconfig public-key pin changed in maintenance-image source/build configuration
-> source review
-> new maintenance image built and verified
-> image installed through the separately controlled firmware-update procedure
-> QUERY_AUTHORIZATION confirms the new fingerprint
-> old signing key is no longer accepted by the new maintenance image
-> calibration writes remain audit-blocked pending explicit key-transition evidence support
```

## Safety authority boundary

Recovery, audit continuity, and authority rotation do not:

- change FPGA hard-current or hard-temperature thresholds;
- change analog comparator/eFuse/fuse/E-stop thresholds;
- authorize protected-load energization;
- send FPGA control commands;
- add dashboard or production-runtime calibration writes;
- decrease the calibration sequence;
- automatically select or restore a profile;
- automatically rotate or adopt a key;
- store a private signing key on the ESP32-S3;
- claim immutable host evidence;
- claim hardware-backed anti-rollback.

## Verification gates

Run:

```bash
make calibration-recovery-check
make calibration-audit-ledger-check
```

The recovery gate covers exact active-record query framing, next-sequence recovery packaging, no-op rejection, active-record tamper detection, runtime binding, signed policy enforcement, and source-review-only maintenance-authority rotation.

The audit gate separately covers fresh-device genesis, chained write/recovery/reboot evidence, replay/tamper detection, exact live record continuity, and signer fingerprint continuity.

These are software verification artifacts only. A real target build, real key rotation, physical maintenance wiring, real calibration write, and physical accuracy result each require separate retained evidence.
