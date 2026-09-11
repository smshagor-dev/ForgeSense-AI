# Calibration Audit Ledger

## Purpose

ForgeSense calibration writes are physically gated, evidence-derived, and cryptographically authorized. The calibration audit ledger adds a separate host-side continuity control so a later maintenance write cannot silently ignore an earlier committed calibration record, an earlier recovery, or an unexpected maintenance-authority key change.

The ledger is a per-device append-structured SHA-256 hash chain. It records the sequence and exact `CalibrationRecord v1` SHA-256 expected after each committed write, the pinned maintenance-authority public-key fingerprint, retained physical evidence hashes, recovery events, and reboot-verification events.

It is deliberately described as **tamper-evident**, not immutable and not a digital signature. A party with unrestricted write access to all host evidence could reconstruct a different chain. Stronger guarantees require independently protected or externally signed archival storage.

## Policy

The machine-readable policy is:

```text
hardware/calibration/calibration_audit_ledger_policy_v1.json
```

Current policy requires:

- initialization only when the device reports calibration sequence `0`;
- no active calibration record at initialization;
- a ready pinned maintenance authority public key;
- no silent adoption of a device with nonzero calibration history;
- contiguous eight-digit entry files;
- SHA-256 previous-entry chaining;
- ledger metadata bound by the genesis entry;
- the current head derived from the final valid entry rather than a mutable head file;
- exact live device identity, calibration sequence, active-record SHA-256, and authority fingerprint checks before each maintenance operation;
- no unexpected authority-key rotation;
- recovery commits at exactly the next sequence;
- no calibration sequence decrement;
- no automatic ledger event insertion.

The ledger has no actuator authority and cannot relax hard safety limits.

## Directory format

A ledger has one immutable-by-convention metadata file and numbered append entries:

```text
calibration-audit/<device>/
  ledger.json
  00000000.json
  00000001.json
  00000002.json
  ...
```

`ledger.json` contains the device binding, policy identifier, creation time, source device-state hash, evidence boundary, and audit-only authority declaration.

`00000000.json` is the genesis entry. Every later entry contains:

- `index`;
- `event_type`;
- `device_id`;
- `previous_entry_sha256`;
- `state_before`;
- `state_after`;
- retained evidence hashes;
- audit-only authority fields;
- `entry_sha256`, computed from canonical JSON excluding the `entry_sha256` field itself.

The verifier derives the current head from the last valid entry. There is no mutable `head` pointer that can be advanced independently from the chain.

## Event types

Supported events are:

```text
genesis
write_commit
recovery_commit
reboot_verified
```

`write_commit` must increase the calibration sequence and bind the committed record SHA-256.

`recovery_commit` must increase the sequence by exactly one. Restoring older approved coefficients never decrements the calibration sequence.

`reboot_verified` is non-mutating. Its before/after sequence, exact-record expectation, and authority fingerprint remain identical.

## Initialize a ledger

First flash/configure the dedicated signed maintenance image, assert the required physical maintenance/load-inhibit gates, and capture the read-only device state:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py status \
  --port <SERIAL_PORT> \
  --report-out evidence/device-state.json
```

The first ledger can only be initialized when that device state reports sequence `0` with no active record:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py init \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --device-state evidence/device-state.json
```

A device already at a nonzero sequence is rejected. The tool does not invent missing history and does not provide an `--adopt-existing-history` bypass.

## Verify the ledger

Verify the complete chain:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py verify \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff
```

To compare the ledger head against a newly captured read-only device-state file:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py verify \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --device-state evidence/device-state-current.json
```

The comparison requires exact device ID, sequence, active-record SHA-256, and maintenance-authority public-key SHA-256 continuity.

## Mandatory write preflight

Physical APPLY now requires:

```text
--audit-ledger <ledger directory>
```

and defaults to:

```text
--audit-policy hardware/calibration/calibration_audit_ledger_policy_v1.json
```

Before the serial port opens, the host verifies the complete ledger structure and provisioning/device binding. After opening the device but before signed PREPARE, it reads:

- current device status;
- pinned maintenance-authority fingerprint;
- exact active `CalibrationRecord v1` bytes.

The live values must match the ledger head. Any sequence gap, record SHA mismatch, device mismatch, or unexpected signer fingerprint change stops the operation before PREPARE.

This is an additional boundary. It does not replace provisioning/source derivation verification, detached signature verification, device-side signature verification, physical maintenance enable, or physical load-output inhibit.

## Append after a successful write

After COMMIT and post-write verification, the physical tool first writes the physical evidence JSON to the requested `--report-out` path. Only then is that evidence hash appended to the ledger.

The appended event binds:

- the prior sequence and prior record SHA from the existing ledger head;
- the new sequence;
- the committed record SHA-256;
- the provisioning artifact-index root;
- the maintenance authorization payload SHA-256;
- the detached signature SHA-256;
- the maintenance authority public-key SHA-256;
- the retained physical evidence file SHA-256.

For a recovery package the entry type is `recovery_commit` and the next-sequence rule is rechecked.

## Reboot verification

The existing `verify-reboot` operation also requires the audit ledger. Live exact-record and signer continuity are checked before the reboot evidence is accepted.

After the reboot verification report is retained, a `reboot_verified` event is appended. This event does not change the ledger's calibration sequence or record SHA.

## Host interruption after device COMMIT

A host filesystem failure can occur after the physical device has successfully committed a calibration but before the ledger entry is appended. Host-side files cannot make a device NVS transaction and a separate computer filesystem transaction globally atomic.

ForgeSense therefore follows this ordering:

```text
device signed PREPARE/COMMIT
-> device post-write verification
-> retain physical evidence JSON
-> append audit-ledger entry
```

If the final append fails, the physical evidence JSON remains available. The command fails and the ledger remains behind the live device. Future physical writes then fail the live ledger preflight until the retained evidence is explicitly reconciled.

Use:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py append-write \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --evidence evidence/calibration-physical-provisioning-001.json
```

For retained reboot evidence:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py append-reboot \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --evidence evidence/calibration-physical-provisioning-reboot-001.json
```

These commands validate continuity; they do not offer arbitrary entry creation or history rewriting.

## Failure behavior

The verifier fails closed on:

- malformed or unsupported policy;
- missing genesis;
- non-contiguous entry numbers;
- unknown files in the ledger directory;
- symlinked/non-regular entries;
- entry hash mismatch;
- previous-entry hash mismatch;
- metadata/genesis binding mismatch;
- device mismatch;
- state-before/state-after discontinuity;
- sequence decrement;
- recovery sequence jump;
- missing committed record SHA;
- unexpected maintenance-authority fingerprint change;
- live device sequence mismatch;
- live exact active-record SHA mismatch;
- replayed/duplicate physical evidence that no longer continues the current head.

A partially created append is not silently deleted by the ledger code. It remains visible and causes verification to fail until explicitly investigated.

## Authority-key rotation interaction

The current maintenance-authority policy requires key rotation through source review and a rebuilt maintenance image; there is no runtime key-update command.

The audit ledger intentionally treats a changed pinned public-key fingerprint as an unexpected discontinuity and blocks writes. This implementation does **not** create a key-rotation ledger event or silently accept a replacement key. A future reviewed rotation-transition workflow must provide its own explicit evidence before continuity across keys can be accepted.

## Verification gate

Run:

```bash
make calibration-audit-ledger-check
```

The gate covers:

- fresh-device genesis;
- nonzero-history rejection;
- write/recovery/reboot continuity;
- entry and metadata tamper detection;
- duplicate/replayed evidence rejection;
- exact active-record drift rejection;
- signer fingerprint drift rejection;
- exact-next-sequence recovery enforcement;
- source-level physical-tool ordering and production-authority separation.

These are software verification artifacts. They do not prove a physical write occurred, do not establish calibration accuracy, do not create immutable archival storage, and do not provide hardware-backed anti-rollback.
