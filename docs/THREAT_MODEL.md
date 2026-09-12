# Threat Model

## Scope

This threat model covers the ForgeSense v1 reference architecture: Tang Nano 9K FPGA safety/control logic, ESP32-S3 edge firmware, ForgeSense Link, local telemetry/dashboard, calibration evidence, maintenance provisioning, audit ledger, and maintenance-authority transitions.

The central security rule is that compromise of a non-deterministic or network-connected component must not silently defeat the deterministic FPGA hard-safety boundary or the independent analog/E-stop protection layers.

## Assets

- deterministic FPGA safety state and hard limits;
- protected-load enable authority;
- sensor integrity/freshness;
- ESP32-S3 production firmware and configuration;
- calibration evidence and approved `CalibrationRecord v1` values;
- maintenance signing public-key trust anchor;
- external private signing keys;
- per-device audit-ledger continuity;
- firmware build provenance and release artifacts;
- retained physical evidence.

## Trust boundaries

1. **Physical safety boundary** — fuse, TVS, eFuse, comparator trip, normally-closed E-stop, gate driver, MOSFET/output network.
2. **FPGA deterministic boundary** — sensor validity, hard limits, watchdog, freshness/replay checks, state machine, final load-enable decision.
3. **ESP32 edge boundary** — inference, event persistence, telemetry, production runtime.
4. **Maintenance boundary** — physically gated dedicated image, signed PREPARE/COMMIT, dual-slot calibration storage.
5. **Host/evidence boundary** — calibration capture/review, provisioning packages, audit ledger, release artifacts.
6. **External key boundary** — private signing keys remain outside repository, firmware, dashboard, and normal maintenance tooling.

## Threats and controls

| ID | Threat | Primary controls | Residual boundary |
| --- | --- | --- | --- |
| T-01 | Malicious/stale/replayed ML frame | CRC16, version/schema checks, sequence freshness, age checks, FPGA watchdog, retained accepted state | UART physical attacker can cause denial of service; cannot override hard limits |
| T-02 | Compromised ESP32 production firmware | FPGA remains final control authority; no dashboard actuator route; hard limits/E-stop independent | Compromised MCU can suppress intelligence/telemetry and force safe shutdown through timeout |
| T-03 | Sensor spoofing or stuck values | device identity/config readback, transport CRC, freshness, plausibility, hard thresholds, impairment/fault tests | Plausible but false physical signals require independent physical validation/redundancy |
| T-04 | UART corruption/injection | framing, CRC, length/version/type checks, monotonic sequence, watchdog | persistent abuse can deny service |
| T-05 | Calibration package tamper | SHA-256 evidence roots, source re-derivation, explicit approval, signed maintenance authorization | SHA-256 is integrity evidence, not a signature unless explicitly signed |
| T-06 | Unauthorized calibration write | separate maintenance image, two physical gates, exact device binding, P-256 signed authorization, sequence monotonicity, dual-slot readback | raw flash/NVS snapshot restore is outside software-only rollback guarantee |
| T-07 | Private-key compromise | keys never loaded by repository tooling/device; public-key fingerprints retained; dual-signed authority transition | external key-management quality remains an operational responsibility |
| T-08 | Silent authority-key replacement | source-reviewed rebuild, clean Git commit binding, old/new dual signatures, post-install fingerprint readback, audit transition event | installed-image byte attestation is not yet hardware-proven |
| T-09 | Audit-ledger tamper/gap | canonical SHA-256 chain, index continuity, live-device preflight binding, exact record/fingerprint continuity | local filesystem is not immutable storage |
| T-10 | Malicious firmware release | secure-release policy, Secure Boot v2/flash-encryption profile, build-provenance hashes, no private keys in repo | actual eFuse/security state requires retained device evidence |
| T-11 | Debug/JTAG exposure | production security profile forbids insecure/JTAG allowances | physical verification required on released hardware |
| T-12 | Dashboard/API misuse | read-only local API, no actuator routes, FPGA status remains authority | local data disclosure remains an operational access-control concern |
| T-13 | Supply-chain dependency/action compromise | minimal dependencies, pinned GitHub Actions, source review, hash-bound release artifacts | external toolchain/compiler trust remains |
| T-14 | Power/EMI/transient attack | independent hardware protection, fail-high E-stop, watchdog/fail-closed logic | EMC/surge robustness requires physical testing |

## Security invariants

- ML cannot clear a hard FPGA fault.
- No normal production/dashboard route can provision calibration.
- A calibration record cannot be accepted with an equal or lower sequence.
- Recovery reuses earlier coefficients only through a new higher sequence.
- Maintenance PREPARE requires a valid external signature and physical gates.
- A maintenance authority change requires old-authority continuity and new-authority proof of possession over the same payload.
- Repository tooling never needs a private maintenance or secure-boot signing key.
- Security tooling must not automatically burn eFuses or enable irreversible device security state.
- Security controls never relax analog, E-stop, or FPGA hard-safety limits.

## Residual risks requiring physical or operational evidence

Secure Boot/flash-encryption eFuse state, installed-image attestation, debug-port disablement, side-channel resistance, raw-flash rollback resistance, sensor spoofing realism, EMI/surge behavior, and key-storage procedures cannot be established by repository source alone.
