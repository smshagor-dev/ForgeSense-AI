# Signed Maintenance-Only Physical Calibration Provisioning

## Purpose

ForgeSense keeps physical calibration writes separate from the production ESP32 runtime, the dashboard/telemetry path, the FPGA deterministic safety authority, and the transparent commissioning bridge.

The dedicated firmware target is:

```text
firmware/esp32_calibration_maintenance/
```

It is intended only for controlled installation of an already reviewed, approved, source-derived, and independently verified `CalibrationRecord v1`.

A physical write now requires all of the following:

1. a verified calibration evidence/provisioning chain;
2. an externally produced ECDSA P-256/SHA-256 authorization signature;
3. a firmware-pinned public key matching that signer;
4. the exact target ESP32-S3 eFuse MAC identity;
5. the expected installed calibration sequence;
6. the exact provisioning artifact-index root;
7. the exact 48-byte calibration record;
8. physical maintenance-enable asserted;
9. independent physical load-output inhibit asserted;
10. a fresh per-boot challenge and a fresh PREPARE-to-COMMIT challenge.

The private signing key is not embedded in firmware, is not requested by ForgeSense tooling, and must not be committed to this repository.

No physical provisioning, calibration-accuracy, metrology, certification, or hardware-backed anti-rollback claim is made merely because this code exists.

## Trust flow

```text
read-only device state + signer fingerprint
        -> verified provisioning package
        -> deterministic authorization payload
        -> external private-key signature
        -> OpenSSL signature/public-key verification
        -> signed authorization package
        -> full provisioning verification again
        -> signature verification again before serial open
        -> device identity + pinned-key fingerprint check
        -> physical maintenance gate asserted
        -> physical load-output inhibit asserted
        -> signed PREPARE verified by device mbedTLS
        -> fresh commit challenge
        -> gates + authority readiness checked again
        -> COMMIT inactive NVS slot
        -> exact storage readback
        -> immediate sequence/CRC verification
        -> retained physical evidence
        -> manual reboot/power cycle
        -> retained sequence/CRC recovery verification
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

Both GPIO settings default to `-1`, which makes provisioning unavailable until board-specific wiring is frozen and reviewed.

```text
CONFIG_FORGESENSE_MAINTENANCE_ENABLE_GPIO=-1
CONFIG_FORGESENSE_LOAD_INHIBIT_SENSE_GPIO=-1
```

No GPIO number is guessed by the repository.

The firmware configures the selected pins as inputs without enabling internal pulls. External hardware must provide defined asserted/deasserted levels.

Gate loss during maintenance clears the pending record/challenge. Reasserting a gate therefore requires a new PREPARE.

## Pinned maintenance authority public key

The maintenance image has a third default-disabled prerequisite:

```text
CONFIG_FORGESENSE_MAINTENANCE_AUTHORITY_PUBKEY_DER_HEX=""
```

An empty value means signed authorization is unavailable and calibration writes are rejected.

For an enabled maintenance build, this setting must contain the hexadecimal DER SubjectPublicKeyInfo bytes for the approved 256-bit EC public key used to verify ECDSA P-256/SHA-256 signatures.

The signed authorization packaging tool emits:

```text
authority-public-key.der.hex
```

That file contains public material only and can be used as the reviewed Kconfig value.

The device computes SHA-256 over the pinned DER public key and exposes the fingerprint through the read-only authorization-status query. The host requires that fingerprint to exactly match the public key that verified the detached signature.

The firmware does not parse or store a private key.

## Device identity and read-only status capture

The device identity is the ESP32-S3 default eFuse MAC represented as:

```text
esp32s3:<12 lowercase hexadecimal MAC digits>
```

Before building a provisioning package, use the read-only status command:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/run_physical_calibration_provisioning.py status \
  --port <SERIAL_PORT> \
  --report-out evidence/calibration-device-state-001.json
```

The command reads both normal maintenance status and signer status. It performs no PREPARE and no COMMIT.

The retained `forgesense.calibration_device_state.v1` record includes:

- eFuse-derived device identity;
- installed calibration sequence and CRC;
- maintenance-enable observation;
- load-inhibit observation;
- maintenance-authority readiness;
- pinned public-key SHA-256 fingerprint;
- boot/session status.

The physical gates are still rechecked during PREPARE and COMMIT.

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

The larger bounded payload allows a detached DER ECDSA signature to accompany the exact record and provenance binding. The parser remains fixed-memory and CRC-framed.

### Opcodes

```text
0x01 QUERY_STATUS
0x02 PREPARE_RECORD
0x03 COMMIT_RECORD
0x04 QUERY_AUTHORIZATION
0x81 STATUS_RESPONSE
0x82 PREPARE_RESPONSE
0x83 COMMIT_RESPONSE
0x84 AUTHORIZATION_RESPONSE
```

`QUERY_STATUS` remains compatible with the existing 27-byte status payload. `QUERY_AUTHORIZATION` returns whether the pinned public key parsed successfully and its SHA-256 fingerprint.

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

The candidate sequence is already contained inside the exact 48-byte calibration record.

This binds a signature to one device identity, one expected installed floor, one reviewed provisioning artifact root, and one exact record.

The signature format is:

```text
ECDSA P-256 over SHA-256, ASN.1 DER encoded signature
```

## Prepare the external signing request

The authorization request generator first runs the full provisioning verifier. It does not access a private key.

Example structure:

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

Signing occurs outside ForgeSense tooling with the approved private key under the operator's key-management procedure.

Example OpenSSL command structure:

```bash
openssl dgst -sha256 \
  -sign /secure/non-repository/path/maintenance-authority-private.pem \
  -out authorization-signature.der \
  build/calibration-maintenance-auth-request-001/authorization-payload.bin
```

The private key path above is an example location outside the repository. Do not commit a private key, copy it into generated evidence, or embed it in firmware.

## Verify and package the detached signature

Provide only the detached DER signature and public key to ForgeSense packaging:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/package_calibration_maintenance_authorization.py \
  build/calibration-maintenance-auth-request-001 \
  --signature authorization-signature.der \
  --public-key maintenance-authority-public.pem \
  --out-dir build/calibration-maintenance-authorization-001
```

The packager uses OpenSSL to require a P-256/prime256v1 public key and verify the ECDSA/SHA-256 signature before publishing the package.

Output:

```text
authorization.json
authorization-signature.der
authority-public-key.der.hex
```

The JSON binds:

- device ID;
- expected installed sequence;
- candidate sequence;
- artifact-index root SHA-256;
- calibration record SHA-256;
- signed payload SHA-256;
- detached signature SHA-256;
- authority public-key SHA-256;
- signature algorithm/encoding;
- no-private-key/no-automatic-write authority declarations.

## Signed PREPARE

Unsigned legacy PREPARE requests are rejected by the signed maintenance image.

The signed PREPARE request carries:

```text
boot nonce                     u32
expected installed floor       u32
artifact-index root SHA-256     32 bytes
CalibrationRecord v1           48 bytes
signature length               u16
ECDSA DER signature            1..80 bytes
```

Before accepting the record into pending RAM, the device requires:

- both physical gates asserted;
- NVS calibration store ready;
- pinned public key parsed and ready;
- matching boot nonce;
- exact current installed floor;
- valid CalibrationRecord structure/CRC;
- strictly newer, non-wrapping sequence;
- valid ECDSA/SHA-256 signature against the pinned public key over the deterministic authorization payload.

Only after signature verification succeeds is the record staged in RAM and a fresh commit nonce generated.

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

A storage or readback failure disables further writes for that boot. The firmware does not use `nvs_flash_erase()` as a recovery shortcut.

## Host trust ordering

For physical APPLY, the host performs this ordering before opening the serial port:

```text
full provisioning/source derivation verification
-> exact CALIBRATION-WRITE confirmation
-> signed authorization package reconstruction
-> P-256 public-key validation
-> detached signature verification with OpenSSL
-> only then open serial transport
```

After the device opens, the host requires:

- device identity match;
- physical gates asserted;
- calibration store ready;
- authorization subsystem ready;
- device pinned-key fingerprint equal to the host-verified signer key;
- installed sequence equal to the signed expected floor;
- no pending record.

The device then verifies the signature again during signed PREPARE.

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
  --authorization-dir build/calibration-maintenance-authorization-001 \
  --authority-public-key maintenance-authority-public.pem \
  --port <SERIAL_PORT> \
  --operator "<OPERATOR>" \
  --confirm-write CALIBRATION-WRITE \
  --report-out evidence/calibration-physical-provisioning-001.json
```

The exact `calibration-record.bin` from the verified provisioning bundle is sent to the device. The physical tool does not regenerate alternate coefficients during the write.

## Retained physical evidence

A successful report remains:

```text
forgesense.calibration_physical_provisioning.v1
```

In addition to existing sequence/CRC/device/write observations, it now records:

- signed authorization schema;
- authorization payload SHA-256;
- detached signature SHA-256;
- ECDSA signature format;
- authority public-key SHA-256;
- successful host-side signature verification;
- successful device-side signature acceptance implied by signed PREPARE acknowledgement;
- `signed_authorization_required = true`.

This proves only the software-observed authorization/write chain. It does not prove calibration accuracy or certified metrological traceability.

## Reboot recovery verification

After successful APPLY, manually reboot or power-cycle the maintenance device and run the existing `verify-reboot` command with the same provisioning evidence inputs.

The read-only verification requires:

- same eFuse device identity;
- changed boot nonce;
- recovered store ready;
- active retained record;
- exact committed sequence;
- exact committed record CRC;
- no pending record.

A changed boot nonce demonstrates that a new maintenance-image boot was observed. It is not proof of complete power removal.

## Replay and anti-rollback boundary

The signature binds the expected installed sequence. After a successful commit increases the sequence floor, replaying the same signed authorization against the current NVS state fails the installed-floor checks.

This does not create hardware-backed anti-rollback. An attacker capable of restoring an older complete flash/NVS snapshot may restore both the record and sequence floor. Stronger rollback resistance requires a separately reviewed hardware monotonic trust mechanism.

## Authority boundary

Signed maintenance authorization does not:

- control the protected load;
- send FPGA control commands;
- alter FPGA hard-limit logic;
- alter analog comparator/eFuse/fuse/E-stop thresholds;
- expose production/dashboard/HTTP write authority;
- automatically select coefficients;
- automatically provision a device;
- store a private signing key on the ESP32-S3;
- ask ForgeSense host tooling to load a private signing key;
- claim hardware-backed monotonic anti-rollback;
- claim physical calibration accuracy or certification.

## Verification gates

Run:

```bash
make maintenance-provisioning-check
make signed-maintenance-authorization-check
```

The signed authorization gate includes:

- deterministic payload-binding tests;
- OpenSSL-backed ephemeral P-256 signature verification tests;
- tampered-signature rejection;
- signer-fingerprint mismatch rejection before PREPARE;
- signed PREPARE binding/evidence tests;
- expanded 192-byte fixed-memory maintenance-frame regression;
- source-level checks for mbedTLS public-key verification;
- source-level checks that private-key parsing/signing is absent from firmware and packaging tools;
- checks that production runtime and transparent bridge remain outside the write authority;
- policy checks requiring signed authorization at write time.

These are software verification artifacts. Target ESP-IDF compilation and real-device authorization/provisioning remain physical evidence tasks and must not be inferred from host tests alone.
