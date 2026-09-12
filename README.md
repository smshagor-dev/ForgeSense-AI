# ForgeSense AI

**Deterministic FPGA safety + edge AI predictive maintenance + evidence-controlled calibration for low-voltage industrial research.**

ForgeSense AI is a hardware/software co-design platform for sensing, predictive maintenance, bounded automation, and safety-oriented experimentation. The system combines a deterministic FPGA safety domain, an ESP32-S3 edge-compute domain, selected industrial sensing devices, protected low-voltage output hardware, a local monitoring stack, and a review-controlled calibration/provisioning workflow.

The central design rule is simple:

> **ML may inform operation, but it never owns the hard safety path.**

The FPGA remains the final digital authority for hard limits, watchdog behavior, emergency response, interlocks, state transitions, and protected-load enable. The ESP32-S3 performs edge inference and monitoring but cannot relax FPGA hard limits or bypass independent hardware protection.

> **Current status:** active pre-hardware engineering implementation. The repository contains the frozen `HW-BL-004` low-voltage reference baseline, selected sensing devices, Tang Nano 9K physical mapping, synthesizable VHDL acquisition/safety logic, ESP32-S3 runtime and dedicated maintenance firmware, deterministic simulation, calibration evidence tooling, signed maintenance authorization, monotonic recovery, per-device audit history, and dual-signed maintenance-authority transition support. Real Gowin synthesis/P&R evidence, ESP-IDF target-build evidence, physical calibration evidence, real key-rotation evidence, and machine-level certification are still pending.

The project does **not** claim industrial certification, metrology certification, production predictive-maintenance accuracy, hardware-backed anti-rollback, installed-image attestation, or unverified novelty.

---

## 1. System objective

ForgeSense AI is designed around a complete low-voltage industrial sensing and control chain:

```text
machine/load
   |
   +--> TMP117 temperature
   +--> ADXL355 vibration
   +--> 15 mOhm shunt + INA181A1 + ADS131M02 current
   |
   v
Tang Nano 9K FPGA
   |
   +--> deterministic acquisition
   +--> sensor validity/freshness
   +--> hard-limit monitor
   +--> watchdogs
   +--> emergency/interlock logic
   +--> final load-enable authority
   |
   +<---------------- ForgeSense Link ---------------->+
   |                                                   |
   v                                                   v
protected output                               ESP32-S3 edge runtime
                                                   |
                                                   +--> feature window
                                                   +--> local anomaly inference
                                                   +--> event records
                                                   +--> read-only telemetry
                                                   +--> dashboard feed
```

A separate maintenance image is used for controlled calibration writes. Production runtime, transparent commissioning, calibration diagnostics, and maintenance provisioning remain separated by explicit authority boundaries.

---

## 2. Selected reference hardware

The current component-backed baseline is `HW-BL-004`.

| Function | Selected reference |
| --- | --- |
| FPGA | Sipeed Tang Nano 9K, GW1NR-LV9QN88PC6/I5 |
| FPGA clock | 27 MHz onboard oscillator |
| Edge processor | ESP32-S3-DevKitC-1 |
| Temperature | TMP117AIDRVR |
| Vibration | ADXL355BEZ |
| Precision ADC | ADS131M02IPWR |
| ADC master clock | SiT8924 8.192 MHz |
| Current shunt | 15 mOhm Kelvin shunt |
| Current amplifier | INA181A1, gain 20 V/V |
| Analog backup trip | TLV3201AIDBVR |
| Input TVS | SMBJ15A |
| Input eFuse | TPS259470LRPWR |
| 5 V regulator | TPS54202DDCR |
| Quiet 3.3 V regulator | TPS7A2033PDBVR |
| Gate driver | UCC27511ADBVR |
| Output MOSFET | CSD18540Q5B |
| Flyback diode | STPS5L60U |
| Passive fuse | 5 A |

Reference power path:

```text
12 V input
  -> 5 A fuse
  -> SMBJ15A TVS
  -> TPS259470L eFuse
  -> VIN_12V_PROTECTED
       |
       +--> motor/output branch
       |
       +--> TPS54202 -> +5V_LOGIC
                         |
                         +--> Tang Nano 9K
                         +--> ESP32-S3
                         +--> UCC27511A
                         |
                         +--> TPS7A2033 -> +3V3_QUIET
                                             |
                                             +--> INA181A1
                                             +--> ADS131M02
                                             +--> TLV3201
                                             +--> ADXL355
                                             +--> TMP117
```

---

## 3. Deterministic safety authority

The safety chain is intentionally layered.

```text
sensor transport validity
      |
      v
sensor freshness + plausibility
      |
      v
FPGA hard-limit monitor
      |
      +--> analog hard-trip input
      +--> emergency input
      +--> intelligence watchdog
      +--> link watchdog
      |
      v
deterministic safety state machine
      |
      v
FPGA_LOAD_ENABLE
      |
      v
UCC27511A gate driver
      |
      +<-- independent fail-high E-stop inhibit
      |
      v
CSD18540Q5B protected output
```

Safety invariants include:

- emergency and hard-critical conditions outrank ML;
- sensor invalidity fails closed;
- only accepted fresh/compatible ML traffic resets the intelligence watchdog;
- replayed, duplicate, stale, incompatible, or corrupt ML messages do not keep the system operational;
- ML warning/critical state is latched until replaced by a newer accepted observation;
- a critical first operational ML observation cannot transiently energize the load;
- Wi-Fi, dashboard, telemetry, storage, or cloud availability is never the sole safety path;
- maintenance/calibration tooling cannot relax FPGA hard limits;
- the analog comparator, eFuse, passive fuse, and fail-high E-stop remain independent of edge inference.

Reference intervention ordering:

```text
~3.47 A independent analog hard trip
< ~4.04 A eFuse current limit
< 5 A passive fuse
```

---

# 4. Core engineering formulas

This section collects the main equations implemented or checked by the repository. The values are engineering reference values for the current low-voltage baseline, not certified machine limits.

## 4.1 Current shunt and amplifier

Reference values:

```text
Rshunt = 0.015 ohm
INA181 gain G = 20 V/V
Iref = 3.2 A
```

Shunt voltage:

```text
Vshunt = I * Rshunt
       = 3.2 * 0.015
       = 0.048 V
```

Amplifier output:

```text
Vout = G * Vshunt
     = 20 * 0.048
     = 0.960 V
```

Shunt power:

```text
Pshunt = I^2 * Rshunt
       = 3.2^2 * 0.015
       = 0.1536 W
```

ADS131M02 gain-1 positive nominal full-scale utilization:

```text
utilization = Vout / 1.2 V
            = 0.960 / 1.2
            = 0.80
            = 80%
```

General current analog transfer:

```text
Vout = I * Rshunt * G
I = Vout / (Rshunt * G)
```

For the current baseline:

```text
I = Vout / 0.300
```

where `I` is in amperes when `Vout` is in volts.

## 4.2 ADS131M02 raw code to current

The selected FPGA reference uses exact integer scaling:

```text
current_mA = trunc(raw_signed24 * 1000 / 2097152)
```

Equivalent full-scale interpretation:

```text
2^23 raw counts ~= 4000 mA
```

The source constants are:

```text
ADS131M02_CURRENT_MA_NUMERATOR   = 1000
ADS131M02_CURRENT_MA_DENOMINATOR = 2097152
```

Later approved calibration replaces the nominal gain/offset with the reviewed `CalibrationRecord` coefficients; hard safety limits remain separate.

## 4.3 Independent analog overcurrent trip

Comparator reference divider:

```text
Vsupply = 3.3 V
Rtop = 23.2 kohm
Rbottom = 10.7 kohm
```

Divider voltage:

```text
Vtrip_ref = Vsupply * Rbottom / (Rtop + Rbottom)
          = 3.3 * 10.7 / (23.2 + 10.7)
          ~= 1.042 V
```

Ideal current threshold:

```text
Itrip = Vtrip_ref / (Rshunt * G)
      = 1.042 / (0.015 * 20)
      ~= 3.47 A
```

This comparator feeds the FPGA hard-fault path directly and is independent of ESP32-S3/ML operation.

## 4.4 TPS259470L UVLO and OVLO

Reference divider:

```text
R1 = 470 kohm
R2 = 36 kohm
R3 = 36 kohm
Vref ~= 1.2 V
Rsum = R1 + R2 + R3 = 542 kohm
```

Ideal UVLO:

```text
Vuvlo = Vref * Rsum / (R2 + R3)
      = 1.2 * 542 / 72
      ~= 9.03 V
```

Ideal OVLO:

```text
Vovlo = Vref * Rsum / R3
      = 1.2 * 542 / 36
      ~= 18.07 V
```

## 4.5 TPS259470L current limit

Configured reference equation:

```text
Ilimit_A ~= 3334 / RILM_ohm
```

With `RILM = 825 ohm`:

```text
Ilimit ~= 3334 / 825
       ~= 4.041 A
```

## 4.6 eFuse overcurrent blanking

Reference values:

```text
Citimer = 12 nF
DeltaV = 1.51 V
Idischarge = 1.8 uA
```

Approximate interval:

```text
tblank = C * DeltaV / I
       = 12e-9 * 1.51 / 1.8e-6
       ~= 0.01007 s
       ~= 10.1 ms
```

## 4.7 eFuse output slew

Repository reference equation:

```text
dV/dt ~= 2000 / Cdvdt_pF  [V/ms]
```

For `Cdvdt = 3300 pF`:

```text
dV/dt ~= 2000 / 3300
      ~= 0.606 V/ms
```

Approximate 12 V rise time:

```text
trise ~= 12 / 0.606
      ~= 19.8 ms
```

## 4.8 TMP117 raw conversion

TMP117 nominal LSB:

```text
1 raw count = 0.0078125 degC
```

The FPGA publishes signed deci-degrees Celsius using deterministic integer rounding:

```text
for raw >= 0:
    deci_C = (raw * 5 + 32) / 64

for raw < 0:
    deci_C = (raw * 5 - 32) / 64
```

Equivalent ideal relation:

```text
deci_C ~= raw * 5 / 64
       ~= raw * 0.078125
```

## 4.9 ADXL355 +/-8 g conversion

The 20-bit left-justified sample is recovered as:

```text
raw20 = signed24 >> 4
```

The current FPGA reference converts to milli-g:

```text
milli_g ~= round(raw20 * 156 / 10000)
        ~= round(raw20 * 0.0156)
```

Positive and negative rounding are handled symmetrically in the VHDL implementation.

## 4.10 Vibration RMS

For a default window of `N = 64` conditioned milli-g samples:

```text
RMS = sqrt((x1^2 + x2^2 + ... + xN^2) / N)
```

The FPGA uses integer square-root logic over the accumulated mean square.

## 4.11 Generic linear calibration

`CalibrationRecord v1` uses the transform:

```text
output = trunc((raw - raw_zero) * gain_numerator / gain_denominator)
       + output_offset
```

For approved current calibration:

```text
raw_zero = 0
gain_numerator / gain_denominator ~= approved slope in mA/count
output_offset ~= approved intercept in mA
```

For temperature offset calibration:

```text
raw_zero = 0
gain_numerator = 1
gain_denominator = 1
output_offset = round(mean_offset_C * 10)
```

## 4.12 Current calibration fit

Physical current characterization fits:

```text
reference_current_mA = slope * adc_raw + intercept
```

Residual for point `i`:

```text
ri = yi - (slope * xi + intercept)
```

RMSE:

```text
RMSE = sqrt((1/N) * sum(ri^2))
```

Maximum absolute residual:

```text
max_abs_residual = max(|ri|)
```

Coefficient quantization is then checked against every retained raw calibration point using the exact integer firmware transform.

## 4.13 Temperature offset characterization

For each temperature point:

```text
offset_i = reference_temperature_i - TMP117_temperature_i
```

Constant offset candidate:

```text
mean_offset = mean(offset_i)
```

Residual after applying the constant offset:

```text
ri = offset_i - mean_offset
```

Residual RMSE:

```text
RMSE_temp = sqrt((1/N) * sum(ri^2))
```

## 4.14 Stationary accelerometer bias

Default stationary reference vector:

```text
expected = [0, 0, +1000] mg
```

Per-axis bias:

```text
bias_axis = mean(measured_axis) - expected_axis
```

Per-axis correction candidate is the negative of the measured bias when supported by a future runtime calibration record. The current `CalibrationRecord v1` does not contain accelerometer correction fields, so accelerometer runtime correction remains deferred.

## 4.15 Feature-window averaging

The edge inference runtime uses an 8-sample default window. For each feature:

```text
feature_mean = (x1 + x2 + ... + x8) / 8
```

A required-sensor invalidity resets the window.

## 4.16 Diagonal-Gaussian anomaly model

For each feature `j`:

```text
z_j = (x_j - mean_j) / scale_j
```

Mean squared normalized distance:

```text
z2_mean = mean(z_j^2)
```

Anomaly score:

```text
score = clamp(1 - exp(-0.5 * z2_mean), 0, 1)
```

Reference classification:

```text
score >= 0.90 -> CRITICAL
score >= 0.72 -> WARNING
otherwise     -> NORMAL
```

Reference confidence helper:

```text
d = min(|score - 0.72|, |score - 0.90|)
confidence = min(0.5 + d, 0.99)
```

This model is an integration baseline only. Real machine data, grouped/time-aware validation, drift testing, false-alarm measurement, and alternative model comparison are required before predictive-maintenance performance claims.

## 4.17 Audit-ledger hash chain

Each audit entry is hashed from canonical JSON without its own hash field:

```text
entry_hash_i = SHA256(canonical_json(entry_i_without_entry_sha256))
```

Each non-genesis entry binds the previous one:

```text
entry_i.previous_entry_sha256 = entry_hash_(i-1)
```

Genesis uses:

```text
previous_entry_sha256 = 64 zero hex characters
```

This creates a tamper-evident append-structured chain. It is **not** immutable storage and is **not** a digital signature by itself.

---

# 5. Sensor acquisition workflow

```text
TMP117 / ADXL355 / ADS131M02
          |
          v
register identity/config verification
          |
          v
bus transaction + transport validation
          |
          +--> TMP117 I2C repeated-start read
          +--> ADXL355 SPI mode-0 DRDY burst
          +--> ADS131M02 CPOL=0/CPHA=1 24-bit frame + CRC
          |
          v
fixed-point conversion
          |
          v
sensor freshness/plausibility supervision
          |
          v
normalized temperature / vibration RMS / current
          |
          v
ForgeSense Link sensor frame
```

Selected-device requirements:

- TMP117 device ID must equal `0x0117` before measurements are accepted;
- ADXL355 `DEVID_AD`, `DEVID_MST`, and `PARTID` must match the selected device and configuration must read back correctly;
- ADS131M02 ID/configuration must be verified and output-frame CRC must pass before conversion data are published;
- transport/configuration faults prevent the affected source from being treated as healthy.

---

# 6. ForgeSense Link workflow

Reference full-duplex UART:

```text
115200 baud
8 data bits
no parity
1 stop bit
```

Primary application messages:

| Direction | Message | Type | Frame size |
| --- | --- | ---: | ---: |
| FPGA -> ESP32-S3 | sensor snapshot | `0x11` | 22 bytes |
| FPGA -> ESP32-S3 | safety status snapshot | `0x30` | 18 bytes |
| ESP32-S3 -> FPGA | ML observation | `0x10` | 28 bytes |
| calibration FPGA -> host | diagnostic capture | `0x32` | 30 bytes |

Frames use:

```text
A5 5A sync
+ protocol version
+ type
+ explicit payload length
+ monotonic/sequence fields
+ CRC-16/CCITT-FALSE
```

CRC parameters:

```text
polynomial = 0x1021
initial value = 0xFFFF
```

The FPGA accepts ML observations only after CRC, type/version, model/schema compatibility, sequence freshness, and inference-age checks.

---

# 7. Edge inference workflow

```text
validated FPGA sensor snapshot
        |
        v
required sensors valid?
   | no -> clear feature window
   | yes
        v
8-sample feature window
        |
        v
mean temperature / vibration / current
        |
        v
diagonal-Gaussian anomaly score
        |
        v
NORMAL / WARNING / CRITICAL
        |
        v
ForgeSense Link ML observation
        |
        v
FPGA acceptance gate
        |
        v
latched intelligence state
        |
        v
deterministic safety FSM
```

ML cannot directly toggle the protected output. It can only contribute an accepted health state to the deterministic FPGA control logic.

---

# 8. Physical calibration evidence workflow

The preferred calibration path is evidence-first and read-only until explicit source approval.

```text
dedicated load-disabled FPGA calibration image
        |
        v
read-only diagnostic frame 0x32
        |
        v
transparent ESP32 commissioning bridge
        |
        v
diagnostic JSON
        |
        +--> independent reference current measurements
        +--> independent reference temperature measurements
        +--> instrument metadata
        +--> k=2 uncertainty declarations
        |
        v
calibration session manifest
        |
        v
capture assembler
        |
        v
calibration capture
        |
        v
single-run proposal
        |
        v
>= 3 independent campaign runs
        |
        v
repeatability + uncertainty review
        |
        v
verified campaign bundle
```

Minimum session evidence currently requires:

```text
>= 5 independent current reference points
>= 3 independent temperature reference points
>= 20 trusted stationary accelerometer samples
```

Diagnostic captures with CRC/frame failures, sequence gaps, untrusted samples, incomplete samples, or authority tampering are rejected.

---

# 9. Calibration review -> approved source workflow

A review-ready result does not automatically become runtime calibration.

```text
verified repeated-run campaign
        |
        v
reviewer change package
        |
        v
explicit approval manifest
        |
        v
current rational quantization
+ temperature deci-C quantization
+ accelerometer deferral
        |
        v
retained-point regression
        |
        v
hard-safety source hash snapshot
        |
        v
add-only approved calibration profile patch
        |
        v
source-control review
```

Initial engineering screening policy includes:

```text
minimum runs                          = 3
maximum current slope span            = 10000 ppm
maximum current intercept span        = 25 mA
maximum current run RMSE              = 50 mA
maximum temperature offset span       = 0.30 C
maximum temperature residual RMSE     = 0.20 C
maximum accelerometer axis-bias span  = 50 mg
maximum run axis standard deviation   = 25 mg
maximum absolute bias                 = 250 mg
maximum current reference U(k=2)      = 25 mA
maximum temperature reference U(k=2)  = 0.20 C
maximum accelerometer reference U(k=2)= 25 mg
```

These are engineering screening limits, not certified metrology limits.

Approved runtime-mappable channels in `CalibrationRecord v1`:

```text
current      -> supported
temperature  -> supported
accelerometer-> deferred
```

---

# 10. Provisioning workflow

An approved source profile is converted into an exact 48-byte `CalibrationRecord v1` candidate only after the earlier evidence chain passes.

```text
approved source-controlled profile
        |
        v
full source/evidence re-verification
        |
        v
exact CalibrationRecord v1 encoding
        |
        v
CRC32 + deterministic byte serialization
        |
        v
strict sequence check
        |
        v
provisioning package
```

Sequence rule:

```text
candidate_sequence > active_sequence
```

Recovery has a stronger rule:

```text
recovery_sequence = active_sequence + 1
```

Sequence decrement is never used for recovery.

CRC32 validates accidental corruption; it is not an authentication mechanism.

---

# 11. Signed maintenance write workflow

Calibration writes are available only through the dedicated maintenance path.

```text
verified provisioning package
        |
        v
exact device state capture
        |
        v
maintenance physical gate active
+ protected output physically inhibited
        |
        v
external ECDSA P-256/SHA-256 authorization
        |
        v
host verifies detached signature
        |
        v
device verifies same signed authorization
        |
        v
signed PREPARE
        |
        v
fresh commit challenge
        |
        v
COMMIT
        |
        v
exact active-record readback
        |
        v
retained physical evidence
```

The signed authorization binds:

```text
exact ESP32-S3 eFuse MAC
expected installed calibration sequence
provisioning artifact-root SHA-256
exact 48-byte CalibrationRecord v1
```

Private signing keys are not stored in the repository, production tooling, or maintenance firmware.

---

# 12. Monotonic recovery workflow

Recovery means restoring earlier approved coefficients in a **newer** record, not decreasing the sequence.

Example:

```text
current active sequence     = 12
earlier approved coefficients= from historical approved profile
recovery record sequence    = 13
```

Workflow:

```text
current exact active record
        |
        v
verify audit-ledger continuity
        |
        v
select earlier approved source profile
        |
        v
re-verify original evidence/provenance
        |
        v
encode coefficients with active_sequence + 1
        |
        v
reject no-op coefficient restore
        |
        v
normal signed maintenance authorization
        |
        v
write + exact readback + reboot verification
```

The project does not claim hardware-backed anti-rollback. Restoring a complete older firmware/NVS snapshot remains outside the current host-side monotonic evidence model.

---

# 13. Per-device audit workflow

Every physical calibration write is tied to an append-structured per-device audit history.

```text
fresh device at sequence 0
        |
        v
audit genesis
        |
        v
pre-write live continuity check
        |
        +--> device ID
        +--> active sequence
        +--> exact active-record SHA-256
        +--> maintenance authority fingerprint
        |
        v
signed physical write
        |
        v
retained evidence
        |
        v
write_commit / recovery_commit entry
        |
        v
reboot verification
        |
        v
reboot_verified entry
```

A ledger cannot be initialized around an already nonzero calibration history to invent missing provenance.

Tamper, entry deletion, replayed evidence, sequence discontinuity, active-record drift, or unexpected signer drift causes fail-closed verification.

---

# 14. Maintenance authority transition workflow

Changing the maintenance signing trust anchor is **not** a calibration command and is not a remote key update.

The new workflow requires both the current and proposed signing authorities to approve exactly the same deterministic transition payload.

```text
verified current audit ledger
        |
        v
fresh read-only device state
        |
        v
clean reviewed Git checkout
        |
        +--> HEAD == reviewed full 40-hex commit
        +--> fixed maintenance source set tracked
        +--> maintenance source set clean
        |
        v
new public key pinned in target sdkconfig
        |
        v
rebuilt maintenance-image SHA-256
        |
        v
deterministic transition payload
        |
        +--> old authority detached signature
        +--> new authority proof-of-possession signature
        |
        v
dual-signature package verification
        |
        v
separately controlled firmware installation
        |
        v
post-install read-only state capture
        |
        v
same calibration sequence + same active record
+ new authority fingerprint
        |
        v
authority_transition audit entry
```

The signed transition payload binds:

```text
transition policy ID
device eFuse MAC
current calibration sequence
active-record presence + SHA-256
current audit-ledger head SHA-256
old authority public-key SHA-256
new authority public-key SHA-256
reviewed source commit
maintenance source-manifest root SHA-256
target sdkconfig SHA-256
rebuilt maintenance-image SHA-256
```

The transition changes only the maintenance authority fingerprint in the audit state. Calibration sequence and active record must remain byte-for-byte unchanged.

The transition tooling does not flash firmware and does not access private signing keys.

---

# 15. Production, commissioning, diagnostics, and maintenance separation

ForgeSense intentionally uses different execution surfaces for different authority levels.

| Surface | Purpose | May write calibration? | May control protected output? |
| --- | --- | ---: | ---: |
| Production ESP32 runtime | edge inference, events, telemetry | no | no direct authority |
| Dashboard/API | read-only monitoring | no | no |
| Transparent commissioning bridge | raw bench transport | no | no |
| Calibration diagnostic FPGA image | read-only sensor evidence | no | load forced disabled |
| Calibration evidence tools | capture/review/proposal | no | no |
| Source-change tools | approved source profile preparation | no | no |
| Provisioning builder/verifier | record preparation | no device write | no |
| Dedicated maintenance firmware | physically gated signed calibration write | yes, under explicit controls | protected load inhibited |
| Authority-transition tools | trust-anchor evidence preparation/verification | no firmware write | no |

---

# 16. Repository layout

```text
ForgeSense-AI/
├── fpga/                 # VHDL acquisition, protocol, safety, board integration
├── firmware/             # ESP32-S3 production, commissioning, maintenance, C++ components
├── ml/                   # reference model, feature runtime, export tooling
├── simulator/            # deterministic machine/sensor scenarios
├── protocol/             # ForgeSense Link specification/reference codec
├── telemetry/            # host telemetry parsing/service logic
├── dashboard/            # local read-only monitoring UI
├── commissioning/        # bench/maintenance host support
├── tests/                # Python/C++/cross-language regression coverage
├── tools/                # validation, calibration, provisioning, audit utilities
├── hardware/             # profiles, calibration policy, circuits, BOM, schematic contracts
├── docs/                 # detailed engineering source of truth
└── .github/              # repository verification workflows
```

---

# 17. Major verification commands

General:

```bash
make test
make demo
make closed-loop
make validate
make model-export
make firmware-host
make dashboard
```

Hardware and selected-device contracts:

```bash
make hardware-check
make circuit-check
make sensor-device-check
make sensor-behavior-check
make tang-pin-check
make bringup-check
make commissioning-check
```

Calibration evidence chain:

```bash
make calibration-diagnostic-check
make calibration-assembler-check
make calibration-check
make calibration-campaign-check
make calibration-bundle-verification-check
make calibration-source-change-check
```

Provisioning, maintenance, recovery, and trust continuity:

```bash
make calibration-provisioning-check
make maintenance-provisioning-check
make signed-maintenance-authorization-check
make calibration-recovery-check
make calibration-audit-ledger-check
make maintenance-authority-transition-check
```

FPGA build entry points when Gowin tools are available:

```bash
make gowin-build
make smoke-build
make calibration-build
```

A configured CI workflow does not count as executed evidence when a hosted runner is not allocated. Repository documentation distinguishes written tests/checkers from actually executed CI results.

---

# 18. Deterministic simulation evidence

The software reference includes deterministic virtual scenarios for:

```text
normal operation
bearing degradation
overcurrent trend
cooling loss
sensor dropout
intelligence link loss
emergency input
```

These results verify system behavior and interface logic in the virtual reference. They do not prove real-machine fault-detection accuracy.

---

# 19. Physical evidence still required

The repository deliberately keeps the following claims open until evidence exists:

- real Tang Nano 9K Gowin synthesis, place-and-route, timing closure, and utilization;
- real ESP32-S3 target build for every dedicated firmware image;
- oscilloscope/logic-analyzer validation of SPI, I2C, UART, gate-drive, E-stop, and fault timing;
- current-sense gain/offset and shunt thermal characterization;
- TMP117 placement and thermal-lag characterization;
- ADXL355 mounting, axis choice, noise, bandwidth, and vibration characterization;
- ADS131M02 measured noise/linearity/clock/CRC behavior;
- eFuse transient, surge, blanking, and latch behavior under the real source/cabling;
- MOSFET switching loss and thermal behavior;
- flyback/transient behavior with the real inductive load;
- real repeated-run calibration evidence from independent reference instruments;
- real maintenance signing-key custody and key-transition evidence;
- installed maintenance-image attestation;
- hardware-backed secure boot, flash-encryption, revocation, or anti-rollback evidence;
- machine-specific functional-safety analysis and certification.

---

# 20. Documentation map

Start with [`docs/README.md`](docs/README.md). Key detailed documents include:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/SAFETY_MODEL.md`](docs/SAFETY_MODEL.md)
- [`docs/HARDWARE_BASELINE_V1.md`](docs/HARDWARE_BASELINE_V1.md)
- [`docs/REFERENCE_CIRCUITS.md`](docs/REFERENCE_CIRCUITS.md)
- [`docs/SENSOR_DEVICE_DRIVERS.md`](docs/SENSOR_DEVICE_DRIVERS.md)
- [`docs/TANG_NANO_9K_INTEGRATION.md`](docs/TANG_NANO_9K_INTEGRATION.md)
- [`docs/PHYSICAL_BRINGUP.md`](docs/PHYSICAL_BRINGUP.md)
- [`docs/CALIBRATION_DIAGNOSTIC_STREAM.md`](docs/CALIBRATION_DIAGNOSTIC_STREAM.md)
- [`docs/CALIBRATION_SESSION_ASSEMBLY.md`](docs/CALIBRATION_SESSION_ASSEMBLY.md)
- [`docs/CALIBRATION_CAPTURE.md`](docs/CALIBRATION_CAPTURE.md)
- [`docs/CALIBRATION_REVIEW.md`](docs/CALIBRATION_REVIEW.md)
- [`docs/CALIBRATION_CAMPAIGN.md`](docs/CALIBRATION_CAMPAIGN.md)
- [`docs/CALIBRATION_BUNDLE_VERIFICATION.md`](docs/CALIBRATION_BUNDLE_VERIFICATION.md)
- [`docs/CALIBRATION_SOURCE_CHANGE.md`](docs/CALIBRATION_SOURCE_CHANGE.md)
- [`docs/CALIBRATION_PROVISIONING.md`](docs/CALIBRATION_PROVISIONING.md)
- [`docs/CALIBRATION_MAINTENANCE_PROVISIONING.md`](docs/CALIBRATION_MAINTENANCE_PROVISIONING.md)
- [`docs/CALIBRATION_RECOVERY.md`](docs/CALIBRATION_RECOVERY.md)
- [`docs/CALIBRATION_AUDIT_LEDGER.md`](docs/CALIBRATION_AUDIT_LEDGER.md)
- [`docs/MAINTENANCE_AUTHORITY_TRANSITION.md`](docs/MAINTENANCE_AUTHORITY_TRANSITION.md)
- [`docs/AI_ML.md`](docs/AI_ML.md)
- [`docs/VERIFICATION.md`](docs/VERIFICATION.md)

Machine-readable source-of-truth files live primarily under:

```text
hardware/profiles/
hardware/calibration/
fpga/constraints/
protocol/
```

---

# 21. Contribution, security, and IP

Before proposing changes, read:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- [`SECURITY.md`](SECURITY.md)
- [`LICENSE`](LICENSE)
- [`docs/IP_AND_PUBLICATION.md`](docs/IP_AND_PUBLICATION.md)

Do not disclose suspected vulnerabilities in public issues.

The repository remains under its current development license while architecture, prior art, publication strategy, and potentially protectable work are evaluated.

---

## Author

**Md Shahanur Islam Shagor**  
Project Architect and Lead Developer  
AI / Autonomous Systems / Embedded Systems Research  
GitHub: [@smshagor-dev](https://github.com/smshagor-dev)

---

ForgeSense AI is built as an engineering system first: every intelligent output is bounded, every safety decision has an independent deterministic path, every calibration change is evidence-controlled, and every physical claim must be backed by retained verification evidence.
