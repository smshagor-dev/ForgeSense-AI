# Calibration Recovery and Maintenance Authority Rotation

## Purpose

ForgeSense calibration recovery is not a sequence rollback. If an earlier approved calibration profile must be restored, those approved coefficients are encoded into a new `CalibrationRecord v1` using the next higher sequence. The signed maintenance path treats that record as a new authorized write.

Recovery preserves four properties:

- the restored coefficient set comes from a fully approved and re-verifiable source profile;
- calibration sequence remains monotonic;
- physical gates and signed maintenance authorization remain mandatory;
- live device state and signer fingerprint continue the per-device audit ledger before PREPARE.

The workflow does not claim hardware-backed anti-rollback.

## Exact active-record evidence

The maintenance image exposes the read-only active-record query:

```text
0x05 QUERY_ACTIVE_RECORD
0x85 ACTIVE_RECORD_RESPONSE
```

The status capture retains:

```text
active_record_sha256
active_record_hex
installed_sequence
installed_record_crc32
```

Recovery build, independent verification, live preflight, post-write verification, reboot verification, and audit append all bind the exact active record rather than relying only on sequence metadata.

## Audit-ledger continuity

Every recovery requires an initialized per-device calibration audit ledger. The ledger itself may only be initialized on a fresh sequence-zero device before the first calibration write.

Before recovery PREPARE, the host verifies:

```text
live device ID                 == audit ledger device
live installed sequence        == audit ledger sequence
live active-record SHA-256     == audit ledger record
live authority fingerprint     == audit ledger authority
```

The recovery package separately binds the same current active record as `from_active_record`.

See [`CALIBRATION_AUDIT_LEDGER.md`](CALIBRATION_AUDIT_LEDGER.md).

## Recovery sequence semantics

Recovery requires:

```text
candidate sequence = installed sequence + 1
```

The sequence is never decremented.

Example:

```text
active sequence:                12
earlier approved coefficients:  previously used configuration
new recovery sequence:          13
```

The builder rejects missing exact record evidence, sequence/CRC disagreement, sequence exhaustion, no-op coefficient restoration, insufficient recovery rationale, invalid source derivation, or a provisioning policy that does not require signed authorization and monotonic recovery.

## Build the recovery package

First capture current device state:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py status \
  --port <SERIAL_PORT> \
  --report-out evidence/calibration-device-state-current.json
```

Then prepare the recovery package from the earlier approved source-change evidence:

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

The normal provisioning artifact set is retained, with a recovery intent in `provisioning.json`:

```text
intent.schema = forgesense.calibration_recovery_intent.v1
intent.mode = restore_approved_profile_with_new_sequence
```

The intent binds the exact current record, target approved profile, candidate record, exact next sequence, no-decrement semantics, signed authorization requirement, and no-automatic-recovery/no-safety-relaxation authority.

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

The verifier re-runs normal provisioning/source derivation and independently checks recovery intent, exact active record, next-sequence semantics, approved-profile hashes, and no-op rejection.

## Signing and applying recovery

Recovery uses the normal externally signed maintenance authorization. The signed bytes bind the device eFuse MAC, expected installed sequence, provisioning artifact-index root, and exact candidate record.

Physical APPLY also requires the per-device audit ledger:

```text
--audit-ledger evidence/calibration-audit/esp32s3-aabbccddeeff
--audit-policy hardware/calibration/calibration_audit_ledger_policy_v1.json
```

Before serial access, source/provisioning/recovery/ledger/signature verification must pass. After serial access but before PREPARE, live device identity, sequence, exact record SHA, and signer fingerprint must match the ledger and recovery source state.

After COMMIT the host reads the exact active record again and requires SHA-256, sequence, and CRC to match the committed record. The retained report is saved before it is appended as a `recovery_commit` audit event.

## Reboot verification

After a manual reboot or power cycle, `verify-reboot` requires the audit ledger and rechecks the exact active record. The reboot report is appended as a non-mutating `reboot_verified` event.

A changed boot nonce shows that a new maintenance-image boot was observed; it does not prove full power removal.

## Maintenance authority key rotation

The maintenance public key remains pinned in the dedicated maintenance image. Runtime, remote, and calibration-protocol key update commands remain unsupported.

A reviewed key change now uses the explicit dual-signed transition workflow documented in [`MAINTENANCE_AUTHORITY_TRANSITION.md`](MAINTENANCE_AUTHORITY_TRANSITION.md).

The high-level flow is:

```text
current device/audit state verified
-> new P-256 public key selected
-> reviewed sdkconfig pins exact new DER public key
-> maintenance source manifest + rebuilt image hashed
-> deterministic transition payload generated
-> current authority signs payload
-> new authority signs same payload as proof of possession
-> both signatures independently verified
-> rebuilt maintenance image installed through separate firmware-update procedure
-> read-only post-install state shows new fingerprint
-> calibration sequence/record proven unchanged
-> authority_transition event appended to audit ledger
```

The transition tool does not flash firmware and does not access private keys.

After the ledger transition, future maintenance writes require the new signer fingerprint. A key change that does not have valid dual-signature transition evidence remains fail-closed.

## Key rotation security boundary

The key-transition workflow does not add:

- a writable key slot in calibration NVS;
- a runtime or remote key-update opcode;
- dual-key acceptance in maintenance firmware;
- automatic firmware installation;
- automatic key rotation;
- private-key storage on the ESP32-S3;
- hardware-backed key revocation.

The new maintenance image still accepts one pinned public key. Dual signatures authorize the host-side continuity transition around the separately controlled image replacement; they do not cause the device to accept two keys concurrently.

## Safety authority boundary

Recovery and authority transition do not change FPGA hard-current/hard-temperature thresholds, analog comparator/eFuse/fuse/E-stop thresholds, protected-load authority, dashboard/production write authority, or calibration sequence through key transition.

Recovery cannot decrement sequence. Authority transition cannot change the calibration record or sequence.

## Verification gates

Run:

```bash
make calibration-recovery-check
make calibration-audit-ledger-check
make maintenance-authority-transition-check
```

These are software verification artifacts. A real target build, real maintenance-image installation, real key custody operation, physical calibration write, and calibration accuracy result require separate retained evidence.
