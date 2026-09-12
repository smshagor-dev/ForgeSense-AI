# Security Policy

ForgeSense AI combines control logic, embedded firmware, ML inference, telemetry, calibration, maintenance authorization, and physical outputs. Security failures can therefore become safety failures.

## Reporting a vulnerability

Do not disclose a suspected vulnerability in a public issue, discussion, commit message, screenshot, or shared dataset.

Report privately to the repository owner through a private GitHub channel available to authorized collaborators. If a public security contact is introduced, this document will be updated before public release.

Include:

- affected component and revision;
- reproduction steps;
- expected and observed behavior;
- security and physical-safety impact;
- whether credentials, keys, firmware images, datasets, calibration records, or model artifacts are exposed;
- a minimal proof of concept when safe to provide.

## Security boundaries

The design assumes that the following can fail or become hostile:

- ESP32-S3 production firmware;
- ML model output;
- telemetry/dashboard clients;
- network connectivity;
- sensor values and sensor buses;
- FPGA/MCU communication frames;
- stored configuration and calibration records;
- maintenance provisioning traffic;
- update/build artifacts;
- local audit-ledger storage;
- external debug interfaces.

No single non-deterministic or network-connected component may silently defeat a hard FPGA safety invariant. The complete threat model is documented in [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

## Implemented repository controls

The ForgeSense v1 repository implements or source-controls:

- explicit input validation and bounded fixed-memory parsing;
- protocol version/type/length checks;
- CRC integrity checks;
- sequence, freshness, inference-age and watchdog checks;
- fail-safe communication-loss behavior;
- independent FPGA hard-limit and physical E-stop authority;
- read-only dashboard/telemetry surfaces without actuator routes;
- separate commissioning, diagnostic and maintenance firmware targets;
- explicit calibration evidence, approval and hard-safety non-regression gates;
- P-256/SHA-256 signed maintenance authorization bound to device, sequence, evidence root and exact record;
- monotonic calibration recovery and dual-slot storage/readback;
- per-device tamper-evident SHA-256 audit history;
- dual-signed maintenance-authority transition with clean Git/source/image binding;
- private-key isolation from repository/device tooling;
- a production ESP32-S3 Secure Boot v2 / flash-encryption release policy;
- firmware build-provenance hashing;
- pinned third-party GitHub Actions and minimal CI permissions;
- a machine-checkable repository engineering-completion gate.

These are repository engineering controls. Device-side Secure Boot/flash-encryption/eFuse state, installed-image attestation, debug-port state, hardware-backed rollback resistance, physical tamper resistance, and key custody still require external operational or physical evidence.

## Production firmware release security

The production policy is defined in:

```text
firmware/security/esp32_s3_release_security_profile_v1.json
```

Validate a final retained ESP32-S3 `sdkconfig` with:

```bash
python tools/check_esp32_release_security.py --sdkconfig path/to/sdkconfig
```

See [`docs/FIRMWARE_RELEASE_SECURITY.md`](docs/FIRMWARE_RELEASE_SECURITY.md) for the external-signing, provenance and physical-device evidence workflow.

Repository tools deliberately do **not** generate/store production private keys, automatically burn security eFuses, automatically enable irreversible Secure Boot/flash-encryption state, or claim device security state without readback evidence.

## Dependency and supply-chain rules

Pin dependencies where practical. Review transitive dependencies before adopting new frameworks. CI uses minimal permissions. Third-party GitHub Actions must be pinned to immutable commit SHAs unless an explicit security review documents another decision.

Do not commit private keys, API credentials, device secrets, calibration signing keys, production Secure Boot keys, or other secrets. Public verification keys/fingerprints may be source-controlled when required by a reviewed trust policy.

## Security regression gates

Relevant repository checks include:

```bash
make signed-maintenance-authorization-check
make calibration-recovery-check
make calibration-audit-ledger-check
make maintenance-authority-transition-check
make release-security-check
make engineering-complete-check
```

## Safety notice

This repository is not a certified safety product. Do not use experimental builds to protect people, control hazardous machinery, or switch mains voltage directly. Existing certified protection systems must remain independent during development.
