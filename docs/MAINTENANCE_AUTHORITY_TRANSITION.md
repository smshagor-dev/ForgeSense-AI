# Maintenance Authority Key Transition

## Purpose

ForgeSense maintenance-authority rotation is not a calibration write and is not a runtime key-update command. The maintenance public key remains pinned in the dedicated maintenance image. Changing that trust anchor requires a reviewed maintenance-image rebuild plus explicit transition evidence that preserves calibration-state continuity.

The transition workflow uses two detached signatures over the exact same deterministic payload:

- the current/old maintenance authority signs the transition, proving continuity from the authority already recorded in the device audit ledger;
- the proposed/new maintenance authority signs the same payload, proving possession of the new private key before the new public key is adopted.

ForgeSense transition tooling verifies signatures but does not load either private key.

## Security boundary

The transition workflow does not provide a firmware flashing command. It does not write the maintenance public key over the calibration protocol, production runtime, dashboard, telemetry API, or commissioning bridge.

The machine-readable policies are:

```text
hardware/calibration/maintenance_authority_policy_v1.json
hardware/calibration/maintenance_authority_transition_policy_v1.json
hardware/calibration/calibration_audit_ledger_policy_v1.json
```

The transition tool has evidence-only authority: no actuator control, FPGA command authority, hard-safety threshold authority, automatic key rotation, firmware-write authority, private-key access, or calibration record/sequence mutation.

## Preconditions

Before preparing a transition request:

1. the per-device calibration audit ledger must verify;
2. a fresh read-only maintenance device-state capture must match the ledger device ID, calibration sequence, exact active-record SHA-256, and current authority fingerprint;
3. the old P-256 public key must match the authority fingerprint recorded at the ledger head;
4. the new P-256 public key must be different;
5. the reviewed target `sdkconfig` must pin the exact DER SubjectPublicKeyInfo bytes of the new public key;
6. a rebuilt maintenance-image binary must exist so its SHA-256 can be bound into the transition;
7. the source commit must be a full 40-hex Git commit;
8. `repo_root` must currently have that exact commit checked out at `HEAD`;
9. every maintenance-image source path in the transition manifest must be tracked and clean relative to that commit.

A transition cannot silently adopt a device that already presents an unexpected key fingerprint.

## Maintenance source manifest

The transition request hashes the maintenance-image source boundary, including:

```text
firmware/esp32_calibration_maintenance/CMakeLists.txt
firmware/esp32_calibration_maintenance/sdkconfig.defaults
firmware/esp32_calibration_maintenance/main/CMakeLists.txt
firmware/esp32_calibration_maintenance/main/Kconfig.projbuild
firmware/esp32_calibration_maintenance/main/app_main.cpp
firmware/esp32_calibration_maintenance/main/calibration_store_nvs.cpp
firmware/esp32_calibration_maintenance/main/calibration_store_nvs.hpp
firmware/esp32_calibration_maintenance/main/maintenance_authorization.cpp
firmware/esp32_calibration_maintenance/main/maintenance_authorization.hpp
firmware/esp32_calibration_maintenance/main/maintenance_protocol.cpp
firmware/esp32_calibration_maintenance/main/maintenance_protocol.hpp
```

Before hashing, the tool requires `git rev-parse HEAD` to equal the reviewed source commit, requires every listed path to be tracked, and requires `git status --porcelain` for those paths to be clean. The manifest root canonically binds both the exact source commit and the per-file SHA-256 list.

This is a source-checkout integrity binding. It is not a reproducible-build or installed-firmware attestation claim.

## Deterministic transition payload

Both authorities sign the same payload under this domain:

```text
ForgeSense-Maintenance-Authority-Transition-v1\n
```

The payload binds:

```text
device eFuse MAC
current calibration sequence
whether an active calibration record exists
active CalibrationRecord SHA-256, or zeros when absent
current audit-ledger head SHA-256
old authority public-key SHA-256
new authority public-key SHA-256
reviewed 40-hex source commit
maintenance source-manifest root SHA-256
sdkconfig SHA-256
rebuilt maintenance-image SHA-256
```

The signature format is ECDSA P-256 over SHA-256 with ASN.1 DER signatures.

## Prepare the transition request

Capture current read-only device state with the existing maintenance status command, check out the exact reviewed commit with clean maintenance sources, then run:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/prepare_maintenance_authority_transition.py \
  --ledger evidence/device-audit-ledger \
  --device-state evidence/device-state-before-transition.json \
  --old-public-key old-maintenance-authority-public.pem \
  --new-public-key new-maintenance-authority-public.pem \
  --source-commit <FULL_40_HEX_COMMIT> \
  --repo-root . \
  --sdkconfig build/maintenance-v2/sdkconfig \
  --maintenance-image build/maintenance-v2/forgesense_calibration_maintenance.bin \
  --out-dir build/maintenance-authority-transition-request
```

Output:

```text
transition-request.json
transition-payload.bin
source-manifest.json
```

The request tool verifies audit/device state, P-256 keys, exact sdkconfig public-key pin, clean Git source checkout, source manifest, and image hash. It does not access a private key.

## External dual signing

Sign the same `transition-payload.bin` outside ForgeSense tooling with both private keys.

Example command structure for the current authority:

```bash
openssl dgst -sha256 \
  -sign /secure/non-repository/path/old-maintenance-private.pem \
  -out old-authority-signature.der \
  build/maintenance-authority-transition-request/transition-payload.bin
```

Repeat with the new private key to produce `new-authority-signature.der`.

Private keys must remain outside the repository, generated evidence directories, firmware image, and ForgeSense tools.

## Package and verify the transition

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/package_maintenance_authority_transition.py \
  build/maintenance-authority-transition-request \
  --old-signature old-authority-signature.der \
  --new-signature new-authority-signature.der \
  --old-public-key old-maintenance-authority-public.pem \
  --new-public-key new-maintenance-authority-public.pem \
  --transition-policy hardware/calibration/maintenance_authority_transition_policy_v1.json \
  --out-dir build/maintenance-authority-transition
```

The packager verifies both signatures against the same payload, requires the request policy ID to equal the active transition policy, and stores only public keys plus detached signatures.

The package contains:

```text
transition.json
transition-request.json
transition-payload.bin
source-manifest.json
old-authority-signature.der
new-authority-signature.der
old-authority-public.pem
new-authority-public.pem
```

A packaged transition can be independently rechecked with:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/verify_maintenance_authority_transition.py \
  build/maintenance-authority-transition \
  --transition-policy hardware/calibration/maintenance_authority_transition_policy_v1.json
```

The standalone verifier reconstructs the signed payload, checks the source-manifest commit/root, verifies both signatures, checks package hashes, and requires the active policy ID.

## Install the rebuilt maintenance image

Firmware installation is deliberately outside this workflow. Use the separately controlled, reviewed firmware-update procedure to install the rebuilt maintenance image whose SHA-256 is bound in the transition request.

ForgeSense transition tooling does not invoke `esptool`, does not write flash, and does not expose a key-update maintenance opcode.

After installation, use the maintenance read-only status path again and retain a new device-state file.

The post-install state must show the same device ID, exactly the same calibration sequence, exactly the same active calibration-record SHA-256 (including `null` when absent), maintenance authority ready, and the new authority public-key fingerprint.

Any calibration-state change fails the transition.

The read-only fingerprint observation confirms that the running maintenance image presents the expected new key. It does not cryptographically attest that the running firmware bytes equal the pre-install image SHA-256; secure-boot/firmware-attestation evidence would require a separate design.

## Append the authority transition to the audit ledger

Only after the post-install read-only state is captured:

```bash
PYTHONPATH=simulator:ml:protocol/python:telemetry:commissioning \
python tools/manage_calibration_audit_ledger.py append-authority-transition \
  --ledger evidence/device-audit-ledger \
  --transition-package build/maintenance-authority-transition \
  --post-device-state evidence/device-state-after-transition.json \
  --transition-policy hardware/calibration/maintenance_authority_transition_policy_v1.json
```

The supported ledger command requires the transition request policy ID to equal the active transition policy and then re-verifies the complete ledger and transition package. It requires:

- package device ID equals ledger device ID;
- signed ledger head equals the current ledger head;
- signed ledger entry count is current;
- signed calibration sequence equals the current ledger sequence;
- signed active-record SHA-256 equals the current ledger record;
- old signer fingerprint equals the ledger authority before the event;
- post-install fingerprint equals the dual-signed new authority;
- post-install calibration sequence and record are unchanged.

The resulting `authority_transition` audit entry changes only the authority fingerprint. Calibration sequence and calibration record remain unchanged.

## Future calibration writes

After the transition entry is appended, normal signed maintenance preflight expects the new authority fingerprint. A calibration package signed by the old key is no longer accepted by host/device signer matching when the device image is pinned to the new key.

The workflow does not claim hardware-backed revocation. Restoring an older complete firmware/flash snapshot can fall outside this host-side evidence model. Hardware-backed secure boot, flash encryption, anti-rollback eFuses, hardware monotonic key epochs, or remote attestation require their own design and validation.

## Verification gate

Run:

```bash
make calibration-audit-ledger-check
make maintenance-authority-transition-check
```

The transition gate covers dual P-256 signature verification, same-payload old/new signing, new-key proof of possession, active-policy matching, exact sdkconfig key pin, reviewed Git HEAD/clean-source binding, source-manifest and maintenance-image hash binding, same-key rejection, signature tamper rejection, unchanged calibration state, post-install new-fingerprint matching, explicit ledger transition continuity, absence of runtime/remote/calibration-protocol key updates, and absence of firmware-writing/private-key authority in transition tools.

These are software verification artifacts only. A real rebuilt image, real firmware installation, real key custody procedure, real device transition, and any secure-boot or firmware-attestation claim require separately retained evidence.
