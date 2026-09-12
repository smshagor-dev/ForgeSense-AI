# Implementation Status

**Repository implementation: complete for the ForgeSense v1 declared engineering scope.**

This document records source/executable implementation status conservatively. “Complete” here means the repository contains the declared code, RTL, firmware reference, tooling, policies, tests, documentation, and verification wiring. It does not mean physical validation, manufacturing, certification, or target-tool execution evidence is complete.

The machine-readable scope is `engineering/completion_manifest_v1.json`; `make engineering-complete-check` verifies that every declared repository deliverable remains present.

## Deterministic digital reference

The repository includes a repeatable low-voltage machine reference with temperature, vibration, current and speed behavior plus bearing degradation, overcurrent, cooling loss, sensor dropout, intelligence-link loss and emergency scenarios.

The sensor model supports deterministic Gaussian noise, static bias, time drift, saturation, stuck-value and dropout impairments. `simulator/forgesense_sim/qualification.py` adds extended virtual soak, replay-abuse, reset/startup, sensor fail-closed and dataset-shift hard-limit checks.

The seven-scenario validation matrix and qualification suite are virtual engineering evidence only.

## FPGA deterministic domain

Implemented VHDL includes:

- 27 MHz Tang Nano 9K physical composition and frozen J5 application mapping;
- UART 8N1 RX/TX and shared transmit arbitration;
- versioned sensor/status transmission and ML observation receive path;
- CRC/version/type/length/model/schema/freshness/replay checks;
- retained accepted intelligence state and watchdog;
- TMP117 I2C controller with identity and ACK/NACK handling;
- ADXL355 mode-0 SPI identity/configuration/readback and XYZ acquisition;
- ADS131M02 CPOL=0/CPHA=1 register/frame acquisition with output CRC;
- deterministic fixed-point temperature/current/accelerometer conversion;
- sensor validity/freshness supervision and vibration RMS;
- hard warning/critical monitoring;
- startup/run/warning/shutdown/fault/recovery safety state machine;
- asynchronous hard-trip/E-stop/recovery synchronization;
- final protected-load enable authority.

Self-checking RTL/testbench sources exist for safety, protocol, UART/SPI/I2C primitives, sensor math/frontends, selected sensor behavioral models, startup-critical behavior and physical integration. Gowin TCL, CST and SDC sources target `GW1NR-LV9QN88PC6/I5`.

A retained successful GHDL run and Gowin synthesis/place-route/timing report remain external tool-execution evidence gates.

## ESP32-S3 edge domain

`firmware/esp32` provides the production reference application with FPGA transport, fixed-memory parsing, inference, link-loss behavior, event persistence and read-only host telemetry.

Portable C++20 components cover protocol, stream parsing, inference, events, telemetry, sensing, calibration and PHY behavior and are wired into host compilation tests.

The local API/dashboard is read-only and never owns machine-state authority or actuator routes.

Separate firmware targets exist for transparent commissioning and calibration maintenance; production firmware does not expose calibration PREPARE/COMMIT operations.

## ML release engineering

The selected v1 model is the auditable diagonal-Gaussian anomaly baseline. The repository now contains:

- deterministic reference fitting and C++ export;
- 8-sample feature runtime;
- model/feature schema versioning;
- `ml/contracts/dataset_manifest_v1.json` dataset/provenance contract;
- deterministic synthetic reference dataset generator;
- scenario/time-aware split policy;
- `ml/reference_model_card_v1.json`;
- virtual evaluation report generator with normal warning/critical incidence, normal terminal-action count and declared fault-scenario outcomes.

A compact neural candidate is deliberately not promoted from synthetic-only evidence. Representative physical data must show a measured grouped/time-aware benefit before additional model complexity is justified.

Target latency, peak memory, false alarms per operating hour, missed-fault rate and real detection lead time remain physical-device/real-data evidence gates.

## Hardware reference source package

The current reference is `HW-BL-004`:

```text
12 V input
→ 5 A fuse
→ SMBJ15A TVS
→ TPS259470L eFuse
→ protected 12 V rail
```

Protection ordering is intentionally layered:

```text
~3.47 A independent TLV3201 analog trip
< ~4.04 A TPS259470L eFuse current-limit reference
< 5 A passive fuse
```

The measurement chain uses a 15 mOhm Kelvin shunt, INA181A1 gain 20 and ADS131M02. The selected vibration and temperature devices are ADXL355 and TMP117. UCC27511A drives CSD18540Q5B; a normally-closed E-stop directly inhibits the gate driver independently of clocked FPGA logic.

Machine-readable power/sensor/interconnect/schematic/BOM/net-endpoint sources, analytical checkers, bring-up contracts, PCB net classes/layout rules and behavioral SPICE sources are present.

Verified KiCad footprint binding, ERC/DRC/manufacturing outputs and fabricated-board evidence remain external physical/CAD-tool gates.

## Calibration and maintenance chain

The implemented source chain is:

```text
load-disabled read-only diagnostics
→ independently referenced session assembly
→ calibration capture/proposal
→ repeated-run campaign/review
→ evidence/source-provenance verification
→ reviewer-ready change package
→ explicit human approval
→ current/temperature integer quantization
→ hard-safety source non-regression
→ add-only approved calibration source profile
→ exact 48-byte CalibrationRecord v1
→ strict monotonic provisioning sequence
→ externally signed P-256 maintenance authorization
→ physical maintenance-enable + load-inhibit gates
→ signed PREPARE / challenged COMMIT
→ inactive-slot NVS write/readback/metadata commit
→ exact post-write and reboot readback
→ monotonic recovery with a new higher sequence
→ per-device SHA-256 audit ledger
→ dual-signed maintenance-authority transition
```

Accelerometer runtime calibration remains explicitly deferred because `CalibrationRecord v1` has current and temperature fields only. The source workflow records accelerometer evidence without inventing an unsupported runtime mapping.

No calibration workflow can authorize actuator control or hard-safety relaxation.

## Security and release engineering

Repository security implementation includes:

- `docs/THREAT_MODEL.md` covering FPGA/MCU/UART/sensor/calibration/key/audit/release boundaries;
- `docs/HAZARD_ANALYSIS.md` covering low-voltage electrical, sensor, communication, calibration, maintenance and ML hazards;
- signed maintenance authorization and dual-signed authority transition;
- no private maintenance key in repository/device tooling;
- `firmware/security/esp32_s3_release_security_profile_v1.json` defining a production ESP32-S3 Secure Boot v2 / flash-encryption release policy;
- `tools/check_esp32_release_security.py` for validating the security policy and a retained sdkconfig;
- `tools/build_firmware_provenance.py` for SHA-256 build provenance over sdkconfig/application/bootloader/partition artifacts.

Repository tools do not automatically burn eFuses or enable irreversible device security state. Actual Secure Boot, flash-encryption and debug-disable state require device readback evidence.

## Verification integration

Primary repository gates include:

```bash
make test
make validate
make firmware-host
make hardware-check
make commissioning-check
make calibration-check
make calibration-diagnostic-check
make calibration-assembler-check
make calibration-campaign-check
make calibration-bundle-verification-check
make calibration-source-change-check
make calibration-provisioning-check
make maintenance-provisioning-check
make signed-maintenance-authorization-check
make calibration-recovery-check
make calibration-audit-ledger-check
make maintenance-authority-transition-check
make software-qualification-check
make ml-release-check
make release-security-check
make engineering-complete-check
```

GitHub Actions contains Python/host/VHDL/commissioning/calibration workflows. Recent hosted runs have repeatedly failed before runner step allocation (`steps=[]`), so source wiring must not be described as a hosted pass until a runner actually executes it.

## External evidence still required

Repository engineering completion deliberately excludes unsupported physical claims. Remaining external evidence includes:

- retained GHDL and Gowin execution/timing reports;
- ESP-IDF target builds plus measured latency/memory/current;
- physical sensor, bus and J5 wiring validation;
- real calibration campaigns with defensible reference uncertainty;
- shunt/comparator/eFuse/TVS/flyback electrical measurements;
- thermal, surge, EMC, soak, brownout and power-cycle testing;
- verified PCB footprints, ERC/DRC and manufacturing output;
- actual Secure Boot/flash-encryption/eFuse state;
- real-machine predictive-maintenance performance;
- any certification or functional-safety assessment.

See `docs/ENGINEERING_COMPLETION.md` for the formal source-versus-physical completion boundary.
