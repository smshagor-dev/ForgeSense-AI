# ESP32-S3 Firmware Release Security

## Purpose

This document defines the repository-side production security workflow for the ForgeSense ESP32-S3 production image. It does not enable irreversible device security automatically and does not claim that any physical device currently has Secure Boot or flash encryption enabled.

Policy source:

```text
firmware/security/esp32_s3_release_security_profile_v1.json
```

## Release security contract

Before a **production security** claim, a retained final `sdkconfig` must satisfy the policy checker. The profile requires ESP32-S3 Secure Boot v2 plus flash encryption in release mode, and rejects explicitly insecure/JTAG allowances listed by the policy.

Validate a real build configuration with:

```bash
python tools/check_esp32_release_security.py --sdkconfig path/to/final/sdkconfig
```

The default development `firmware/esp32/sdkconfig.defaults` intentionally does not burn or enable irreversible security state.

## Signing-key boundary

ForgeSense repository tooling does not require a production private Secure Boot key.

Allowed repository inputs are public verification/fingerprint material and already-produced build artifacts. Private signing keys must remain under the operator's external key-management procedure.

For external/remote signing, the final ESP-IDF workflow must follow the selected ESP-IDF version's Secure Boot v2 documentation. The repository policy records the required outcome rather than embedding a private-key path.

## Build provenance

After a target build is produced, retain a provenance manifest:

```bash
python tools/build_firmware_provenance.py \
  --repository-commit <40-hex-commit> \
  --idf-version <exact-version> \
  --sdkconfig build/sdkconfig \
  --application build/forgesense.bin \
  --bootloader build/bootloader/bootloader.bin \
  --partition-table build/partition_table/partition-table.bin \
  --signing-public-key public-key.pem \
  --out evidence/firmware-build-provenance.json
```

The manifest records SHA-256 and size for the final sdkconfig, application, bootloader and partition table plus the repository commit, ESP-IDF version and optional public-key fingerprint.

It is **build provenance**, not installed-image attestation.

## Irreversible device actions

The repository does not automate:

- Secure Boot eFuse enablement;
- flash-encryption eFuse enablement;
- JTAG/debug fuse disablement;
- production key generation;
- private-key storage;
- security-state changes on a connected device.

Those actions require explicit operator review because incorrect eFuse/security configuration can make a device difficult or impossible to recover.

## Physical release evidence

A production-security claim additionally requires retained device evidence showing the expected Secure Boot, flash-encryption and debug/download-mode state on the target hardware. The build manifest alone is insufficient.

These firmware-security controls are independent of the FPGA hard-safety path and do not authorize calibration writes or hard-limit changes.
