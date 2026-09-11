# Signed Maintenance-Only Physical Calibration Provisioning

## Purpose

ForgeSense keeps physical calibration writes separate from the production ESP32 runtime, dashboard/telemetry path, FPGA deterministic safety authority, and transparent commissioning bridge.

The dedicated firmware target is:

```text
firmware/esp32_calibration_maintenance/
```

It installs only an already reviewed, approved, source-derived, independently verified, externally authorized `CalibrationRecord v1`.

A physical write requires all of the following:

1. verified calibration evidence/source derivation;
2. verified provisioning package;
3. externally produced ECDSA P-256/SHA-256 authorization signature;
4. firmware-pinned public key matching that signer;
5. exact target ESP32-S3 eFuse MAC identity;
6. expected installed calibration sequence;
7. exact provisioning artifact-index root;
8. exact 48-byte calibration record;
9. valid per-device calibration audit-ledger continuity;
10. exact live active-record SHA-256 matching the audit head when active;
11. live pinned-authority fingerprint matching the audit head;
12. physical maintenance-enable asserted;
13. independent physical load-output inhibit asserted;
14. fresh per-boot and PREPARE-to-COMMIT challenges.

The private signing key is not embedded in firmware, is not requested by ForgeSense tooling, and must not be committed to the repository.

The audit ledger is tamper-evident host evidence, not immutable storage or a digital signature.

No physical provisioning, calibration-accuracy, metrology, certification, or hardware-backed anti-rollback claim is made merely because this code exists.

## Trust flow

```text
read-only device state + exact active record + signer fingerprint
        -> fresh-device audit-ledger genesis, if not already initialized
        -> verified source/provisioning package
        -> deterministic authorization payload
        -> external private-key signature
        -> OpenSSL signature/public-key verification
        -> signed authorization package
        -> full provisioning/recovery verification
        -> audit-ledger structural verification before serial open
        -> open dedicated maintenance transport
        -> live device identity/sequence/exact-record/signer audit preflight
        -> physical maintenance gate asserted
        -> physical load-output inhibit asserted
        -> signed PREPARE verified by device mbedTLS
        -> fresh commit challenge
        -> gates + authority readiness checked again
        -> COMMIT inactive NVS slot
        -> exact storage readback
        -> immediate sequence/CRC verification
        -> retain physical evidence JSON
        -> append physical evidence hash to audit ledger
        -> manual reboot/power cycle
        -> exact retained-state verification
        -> append reboot-verification evidence to audit ledger
```

## Dedicated firmware separation

The maintenance image is intentionally separate from:

```text
firmware/esp32/                 # production runtime
firmware/esp32_commissioning/   # transparent USB <-> FPGA bridge
```

The production runtime and transparent bridge do not contain the signed maintenance PREPARE path or pinned maintenance-authority verification logic.

The maintenance image does not send FPGA control commands and does not expose dashboard or HTTP write routes.

## Default-disabled physical gates

Two independent GPIO inputs are required:

- physical maintenance-enable input;
- physical load-output-inhibit sense input.

Both GPIO settings default to `-1`, so provisioning is unavailable until board-specific wiring is frozen and reviewed.

```text
CONFIG_FORGESENSE_MAINTENANCE_ENABLE_GPIO=-1
CONFIG_FORGESENSE_LOAD_INHIBIT_SENSE_GPIO=-1
```

No GPIO number is guessed by the repository. External hardware must provide defined asserted/deasserted levels.

Gate loss during maintenance clears the pending record/challenge. Reasserting a gate therefore requires a new PREPARE.

## Pinned maintenance authority public key

The maintenance image also defaults to no signing authority:

```text
CONFIG_FORGESENSE_MAINTENANCE_AUTHORITY_PUBKEY_DER_HEX=""
```

An empty value means signed authorization is unavailable and calibration writes are rejected.

For an enabled maintenance build, this setting contains hexadecimal DER SubjectPublicKeyInfo bytes for the reviewed P-256 public key.

The signed authorization packaging tool emits:

```text
authority-public-key.der.hex
```

The device computes SHA-256 over the pinned DER public key and exposes the fingerprint through the read-only authorization-status query. The host requires that fingerprint to match both the verified authorization signer and the audit-ledger authority continuity.

The firmware does not parse or store a private key.

## Device identity and read-only state capture

The device identity is the ESP32-S3 default eFuse MAC represented as:

```text
esp32s3:<12 lowercase hexadecimal MAC digits>
```

Capture read-only state:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py status \
  --port <SERIAL_PORT> \
  --report-out evidence/calibration-device-state-001.json
```

The command performs no PREPARE and no COMMIT.

The retained `forgesense.calibration_device_state.v1` record includes:

- eFuse-derived device identity;
- installed calibration sequence and CRC;
- exact active `CalibrationRecord v1` bytes when present;
- exact active-record SHA-256 when present;
- maintenance-enable observation;
- load-inhibit observation;
- maintenance-authority readiness;
- pinned public-key SHA-256 fingerprint;
- boot/session status.

Physical gates, exact record state, authority fingerprint, and audit continuity are rechecked at write time.

## Initialize the per-device audit ledger

Before the first calibration write on a fresh sequence-zero device:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py init \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --device-state evidence/calibration-device-state-001.json
```

Initialization fails if the device already has a nonzero calibration sequence or active record. There is no silent history-adoption bypass.

See [`CALIBRATION_AUDIT_LEDGER.md`](CALIBRATION_AUDIT_LEDGER.md).

## Maintenance framing

Frames use:

```text
magic       4 bytes  "FSM1"
version     1 byte   1
opcode      1 byte
length      2 bytes  little-endian payload length
payload     0..192 bytes
crc32       4 bytes  little-endian CRC32/IEEE over header + payload
```

The bounded payload allows a DER ECDSA signature to accompany the exact record and provenance binding. The parser remains fixed-memory and CRC-framed.

### Opcodes

```text
0x01 QUERY_STATUS
0x02 PREPARE_RECORD
0x03 COMMIT_RECORD
0x04 QUERY_AUTHORIZATION
0x05 QUERY_ACTIVE_RECORD
0x81 STATUS_RESPONSE
0x82 PREPARE_RESPONSE
0x83 COMMIT_RESPONSE
0x84 AUTHORIZATION_RESPONSE
0x85 ACTIVE_RECORD_RESPONSE
```

`QUERY_ACTIVE_RECORD` is read-only and returns the exact active 48-byte record when present. It is used by recovery and audit-ledger continuity checks.

## Authorization payload

The exact externally signed bytes are deterministic:

```text
ASCII domain:
ForgeSense-Calibration-Maintenance-Authorization-v1\n
then:
ESP32 eFuse MAC                 6 bytes
expected installed sequence    u32 little-endian
provisioning artifact root     32 bytes SHA-256
CalibrationRecord v1           48 bytes
```

The candidate sequence is contained inside the exact 48-byte record.

The signature format is:

```text
ECDSA P-256 over SHA-256, ASN.1 DER encoded signature
```

## Prepare the external signing request

The request generator runs the full provisioning verifier and, for recovery packages, the recovery verifier. It never accesses a private key.

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/prepare_calibration_maintenance_authorization.py \
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
  --out-dir build/calibration-maintenance-auth-request-001
```

Output:

```text
authorization-request.json
authorization-payload.bin
authorization-payload.sha256
```

The request is signing input only. It does not authorize or write a device.

## External signing

Signing occurs outside ForgeSense tooling under the owner's key-management process.

```bash
openssl dgst -sha256 \
  -sign /secure/non-repository/path/maintenance-authority-private.pem \
  -out authorization-signature.der \
  build/calibration-maintenance-auth-request-001/authorization-payload.bin
```

Do not commit the private key, copy it into generated evidence, or embed it in firmware.

## Verify and package the detached signature

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/package_calibration_maintenance_authorization.py \
  build/calibration-maintenance-auth-request-001 \
  --signature authorization-signature.der \
  --public-key maintenance-authority-public.pem \
  --out-dir build/calibration-maintenance-authorization-001
```

The packager requires a P-256/prime256v1 public key and a valid detached ECDSA/SHA-256 signature.

Output:

```text
authorization.json
authorization-signature.der
authority-public-key.der.hex
```

## Signed PREPARE

Unsigned legacy PREPARE requests are rejected.

The signed PREPARE request carries:

```text
boot nonce                     u32
expected installed floor       u32
artifact-index root SHA-256     32 bytes
CalibrationRecord v1           48 bytes
signature length               u16
ECDSA DER signature            1..80 bytes
```

Before staging the record in RAM, the device requires:

- both physical gates asserted;
- NVS calibration store ready;
- pinned public key parsed and ready;
- matching boot nonce;
- exact current installed floor;
- valid CalibrationRecord structure/CRC;
- strictly newer non-wrapping sequence;
- valid ECDSA/SHA-256 signature against the pinned public key.

Only then is a fresh commit nonce generated.

## COMMIT

COMMIT carries:

```text
boot nonce                 u32
commit nonce               u32
expected pending sequence  u32
```

Before storage changes, firmware checks physical gates and authorization readiness again and requires the same boot/pending sequence/install floor established during PREPARE.

The NVS transaction remains:

```text
inactive slot write
-> NVS commit
-> byte-for-byte readback
-> record decode/validation
-> active-slot/floor metadata commit
-> active record reload
-> exact re-encode/readback comparison
```

A storage/readback failure disables further writes for that boot. The firmware does not erase NVS as a recovery shortcut.

## Host trust ordering

Before opening the serial port for APPLY, the host performs:

```text
strict signed provisioning policy validation
-> full provisioning/source derivation verification
-> recovery verification when present
-> audit-ledger structural/hash-chain verification
-> exact CALIBRATION-WRITE confirmation
-> signed authorization package reconstruction
-> P-256 public-key validation
-> detached signature verification with OpenSSL
-> open serial transport
```

Before PREPARE, the live maintenance device must then match the audit ledger on:

- device identity;
- installed sequence;
- exact active-record SHA-256 when active;
- pinned authority public-key SHA-256.

The normal physical gates/store/authorization/pending-state checks remain mandatory.

## Physical APPLY command

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
  --audit-ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --audit-policy hardware/calibration/calibration_audit_ledger_policy_v1.json \
  --authorization-dir build/calibration-maintenance-authorization-001 \
  --authority-public-key maintenance-authority-public.pem \
  --port <SERIAL_PORT> \
  --operator "<OPERATOR>" \
  --confirm-write CALIBRATION-WRITE \
  --report-out evidence/calibration-physical-provisioning-001.json
```

The exact retained `calibration-record.bin` is sent to the device. The physical tool does not regenerate alternate coefficients during the write.

## Retained physical evidence and audit append

A successful physical report uses:

```text
forgesense.calibration_physical_provisioning.v1
```

It records signed authorization metadata, device observations, sequence/CRC behavior, source verification, recovery status when applicable, and the audit-ledger head/entry count verified before the operation.

The physical evidence JSON is persisted before its hash is appended to the ledger. This ordering is intentional: if the host ledger append fails after a successful device COMMIT, the retained evidence remains available for explicit reconciliation.

The ledger append binds:

- physical evidence file SHA-256;
- provisioning artifact-index root;
- authorization payload SHA-256;
- signature SHA-256;
- signer fingerprint;
- before/after calibration sequence;
- committed record SHA-256.

It does not turn the ledger into signed or immutable storage.

## Reboot recovery verification

After APPLY, manually reboot or power-cycle the maintenance device and run `verify-reboot` with the same verification inputs plus the audit ledger:

```text
--audit-ledger evidence/calibration-audit/esp32s3-aabbccddeeff
```

Before accepting reboot evidence, the host again checks live exact-record and signer continuity against the current ledger head.

The read-only reboot verification requires:

- same eFuse device identity;
- changed boot nonce;
- recovered store ready;
- active retained record;
- exact committed sequence;
- exact committed CRC;
- exact active-record SHA-256 through the audit preflight;
- no pending record.

A `reboot_verified` ledger entry is then appended without changing calibration state.

A changed boot nonce demonstrates a new maintenance-image boot was observed. It is not proof of complete power removal.

## Host interruption and reconciliation

Device NVS commit and host filesystem append cannot be one globally atomic transaction.

If a device write succeeds but the ledger append fails, the command retains `--report-out` evidence and returns failure. Future writes fail audit preflight because the live device is ahead of the ledger.

Explicitly reconcile the retained evidence:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py append-write \
  --ledger evidence/calibration-audit/esp32s3-aabbccddeeff \
  --evidence evidence/calibration-physical-provisioning-001.json
```

Reconciliation only accepts evidence that already contains a matching verified audit-ledger preflight head and entry count. Legacy evidence cannot be used to invent history retroactively.

## Replay and rollback boundary

The authorization signature binds the expected installed sequence. The audit ledger separately binds the host's observed history and requires live state continuity before the next write.

Neither mechanism is hardware-backed anti-rollback. An attacker capable of restoring a complete older flash/NVS snapshot and independently replacing all host evidence remains outside the software-only guarantee.

## Authority boundary

Signed maintenance provisioning and the audit ledger do not:

- control the protected load;
- send FPGA control commands;
- alter FPGA hard-limit logic;
- alter analog comparator/eFuse/fuse/E-stop thresholds;
- expose production/dashboard/HTTP write authority;
- automatically select coefficients;
- automatically provision a device;
- store a private signing key on the ESP32-S3;
- ask ForgeSense tooling to load a private signing key;
- silently accept authority-key rotation;
- claim immutable archival storage;
- claim hardware-backed anti-rollback;
- claim physical calibration accuracy or certification.

## Verification gates

Run:

```bash
make maintenance-provisioning-check
make signed-maintenance-authorization-check
make calibration-recovery-check
make calibration-audit-ledger-check
```

The audit-ledger gate covers fresh-device genesis, write/recovery/reboot continuity, metadata/entry tamper detection, replay rejection, exact active-record drift, signer drift, preflight-bound reconciliation, and production-authority separation.

These are software verification artifacts. Target ESP-IDF compilation and real-device authorization/provisioning remain physical evidence tasks and must not be inferred from host tests alone.
