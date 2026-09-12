# Calibration Audit Ledger

## Purpose

ForgeSense keeps a per-device, append-structured calibration audit ledger for maintenance calibration history. The ledger links retained write, recovery, reboot-verification, and explicitly authorized maintenance-authority transition evidence with SHA-256 hashes.

The ledger is tamper-evident host evidence. It is not a digital signature, immutable storage, a transparency log, or hardware-backed monotonic state.

## Initialization boundary

A ledger may be initialized only from a fresh maintenance device state with:

```text
installed calibration sequence = 0
active CalibrationRecord        = absent
maintenance authority           = ready
```

The initializer records the device ID and current maintenance-authority public-key SHA-256 fingerprint in the genesis entry.

A device with an existing nonzero calibration sequence cannot be silently adopted into a new ledger. This prevents missing history from being invented after provisioning has already occurred.

## Chain structure

Each entry is a numbered JSON file:

```text
ledger.json
00000000.json   # genesis
00000001.json
00000002.json
...
```

Every entry contains:

- a contiguous numeric index;
- device ID;
- event type;
- SHA-256 of the previous entry;
- state before the event;
- state after the event;
- evidence hashes;
- an audit-only authority declaration;
- its canonical SHA-256 entry hash.

`ledger.json` is bound by the genesis entry hash. The effective ledger head is derived from the final verified entry; there is no mutable head pointer that can silently move history.

## Calibration state tracked by the ledger

The state carried across entries is:

```text
calibration sequence
exact active CalibrationRecord SHA-256, or null
maintenance authority public-key SHA-256
```

Normal calibration writes and recovery writes may change calibration sequence/record but may not change authority. Reboot verification may not change any state.

A maintenance-authority transition may change only the authority fingerprint and must leave calibration sequence and active record unchanged.

## Event types

### `write_commit`

Records a successful signed calibration write. The new sequence must be greater than the prior sequence and an exact committed record SHA-256 is required.

### `recovery_commit`

Records restoration of an earlier approved coefficient set through a newly encoded record. The resulting sequence must be exactly `previous + 1`; sequence decrement is forbidden.

### `reboot_verified`

Records read-only verification after a new maintenance-image boot. Sequence, record SHA-256, and authority fingerprint remain unchanged.

### `authority_transition`

Records a reviewed maintenance-authority key transition. It is accepted only when a dual-signed transition package has been independently verified and a post-install read-only device-state capture shows:

- same device ID;
- unchanged calibration sequence;
- unchanged active record SHA-256;
- maintenance authority ready;
- new live authority fingerprint equal to the dual-signed new key.

The transition package requires both the old authority signature and new-key proof-of-possession signature over the same payload. See [`MAINTENANCE_AUTHORITY_TRANSITION.md`](MAINTENANCE_AUTHORITY_TRANSITION.md).

## Live preflight before physical writes

Every physical `apply` and `verify-reboot` operation requires the ledger path.

Before opening the serial port, the host verifies the complete ledger structure and hash chain. After opening the dedicated maintenance transport but before PREPARE or reboot acceptance, it reads:

- device ID;
- installed sequence;
- exact active CalibrationRecord SHA-256;
- pinned maintenance-authority public-key SHA-256.

All values must equal the current ledger head. A mismatch fails closed.

An arbitrary changed signer fingerprint is still rejected. The only supported way to advance the ledger to a new authority is the explicit dual-signed `authority_transition` event.

## Exact record evidence

A committed write is appended only when retained physical evidence includes an exact post-write active-record readback whose:

```text
SHA-256
sequence
CRC32/IEEE
```

match the committed provisioning record.

Reboot evidence likewise requires exact active-record SHA-256, sequence, and CRC to match the current committed record.

This prevents the ledger from relying only on status metadata when exact record bytes are available through the maintenance read-only query.

## Host interruption behavior

Device NVS commit and host filesystem append cannot be globally atomic.

The physical workflow therefore uses:

```text
verify audit ledger
-> live preflight
-> signed PREPARE/COMMIT
-> exact post-write readback
-> atomically retain physical evidence JSON
-> append hash-bound ledger entry
```

If device commit succeeds but the final ledger append fails, the retained physical evidence remains. The live device is then ahead of the ledger, so future writes fail preflight until explicit reconciliation is performed.

Legacy evidence that was not produced under the exact recorded ledger head/entry-count preflight cannot be used to invent missing history retroactively.

## Ledger management commands

Initialize a new ledger:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py init \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --device-state evidence/calibration-device-state-initial.json
```

Verify chain and optionally live captured state:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py verify \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --device-state evidence/calibration-device-state-current.json
```

Reconcile a retained committed write after a host interruption:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py append-write \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --evidence evidence/calibration-physical-provisioning-001.json
```

Append retained reboot evidence:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py append-reboot \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --evidence evidence/calibration-physical-provisioning-reboot-001.json
```

Append a verified authority transition after the rebuilt maintenance image has been installed through the separately controlled firmware-update procedure:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py append-authority-transition \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --transition-package build/maintenance-authority-transition \
  --post-device-state evidence/device-state-after-transition.json
```

None of these commands offers arbitrary entry creation or history rewriting.

## Failure behavior

Verification fails closed on malformed policy, missing genesis, non-contiguous entries, unexpected files, symlinked entries, entry-hash mismatch, previous-hash mismatch, metadata/genesis mismatch, device mismatch, state discontinuity, sequence decrement, recovery sequence jump, missing exact record evidence, unauthorized authority change, invalid dual-signature transition evidence, live record drift, live signer drift, stale transition ledger head, or replayed evidence.

A partially created append remains visible and causes verification failure until investigated; the ledger does not silently rewrite or delete history.

## Authority-key transition boundary

Runtime, remote, and calibration-protocol key-update commands remain unsupported. A key change still requires source review and a rebuilt maintenance image.

The explicit authority-transition workflow adds continuity evidence around that separately controlled firmware installation. It does not itself flash firmware or write a key to device storage.

The ledger accepts a new authority only when:

```text
old authority signs exact transition payload
+ new authority signs same payload
+ payload binds current ledger/calibration state and rebuilt image
+ rebuilt image is installed separately
+ read-only post-install state shows new fingerprint
+ calibration state is unchanged
```

Any key change outside that path remains an unexpected discontinuity and blocks maintenance writes.

## Verification gates

Run:

```bash
make calibration-audit-ledger-check
make maintenance-authority-transition-check
```

The gates cover fresh-device genesis, nonzero-history rejection, write/recovery/reboot continuity, exact active-record evidence, entry/metadata tamper detection, duplicate evidence rejection, live device drift rejection, exact-next-sequence recovery, dual-signed authority transitions, unchanged calibration state during key transition, and production-authority separation.

These are software verification artifacts. They do not prove physical calibration accuracy, immutable archival storage, firmware provenance beyond the recorded hashes, secure-boot state, or hardware-backed anti-rollback/key revocation.
