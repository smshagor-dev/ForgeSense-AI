# System Architecture

## Authority model

ForgeSense AI separates **measurement**, **intelligence**, **presentation**, and
**safety authority**.

```text
Sensors
  |
  v
Input conditioning / acquisition
  |
  v
FPGA deterministic domain ---------------------> Safe output driver
  |                                                   |
  | bounded telemetry / intelligence contract        v
  v                                               Test load
ESP32-S3 edge intelligence
  |
  +--> local telemetry API
  +--> event storage
  +--> dashboard data
```

The FPGA remains capable of reaching a safe output state without receiving a
valid ML result.

## FPGA responsibilities

- reset and startup sequencing;
- asynchronous-input synchronization;
- deterministic sample capture where applicable;
- hard-limit monitoring;
- safety state machine;
- communication watchdog;
- protocol validity/freshness gate for control-relevant intelligence;
- output interlock;
- fault latching and controlled recovery;
- compact event/status publication.

## ESP32-S3 responsibilities

- protocol transport endpoint;
- feature extraction not required for hard safety;
- ML inference;
- health/anomaly estimate;
- local logging and telemetry;
- configuration services within documented bounds;
- optional network connectivity.

## ML authority

An ML result is a typed, bounded observation such as:

```text
model_id
model_version
sample_window_id
sequence
anomaly_score
health_class
confidence_or_uncertainty
validity_flags
```

It is not an unrestricted actuator command.

The FPGA maps accepted intelligent observations to a limited set of documented
state transitions. A hard fault always has priority.

## Dashboard authority

The dashboard may request configuration or operational actions only through
validated firmware interfaces. It must never become the sole path for a safety
function and must not directly drive FPGA output pins.

## Failure behavior

The architecture must define behavior for:

- sensor disconnected;
- sensor saturated;
- sensor stuck;
- MCU absent;
- MCU reset loop;
- corrupted frame;
- frame replay or duplication;
- stale inference;
- unsupported model or protocol version;
- dashboard/network unavailable;
- FPGA reset;
- load power interruption.

Each condition receives a deterministic test scenario before hardware release.

## Planned repository boundaries

```text
fpga/       deterministic control and RTL verification
firmware/   ESP32-S3 runtime and communications
ml/         training/evaluation/export only
protocol/   language-neutral interface contract
simulator/  machine/sensor/fault reference behavior
hardware/   schematics/PCB/electrical evidence
dashboard/  presentation and bounded configuration
tests/      end-to-end acceptance scenarios
```

No directory is allowed to redefine another subsystem's contract silently.
