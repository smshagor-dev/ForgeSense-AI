# Verification and Validation Strategy

ForgeSense AI treats test evidence as part of the product, not a final cleanup task.

## Test layers

### Static checks

- formatting and repository policy;
- RTL lint/synthesis warnings where supported;
- firmware compiler warnings;
- Python type/lint checks;
- dependency review.

### Unit tests

- RTL primitives and state logic;
- protocol parser/serializer;
- feature extraction;
- model preprocessing/postprocessing;
- configuration validation;
- simulator components.

### Scenario tests

A versioned scenario drives all relevant subsystems with the same event sequence.
Examples:

- healthy startup and run;
- rising temperature;
- vibration anomaly;
- over-current hard fault;
- sensor stuck value;
- sensor dropout;
- MCU timeout;
- stale ML message;
- corrupted frame;
- reset during fault;
- attempted recovery before conditions are safe.

### End-to-end virtual validation

The simulator should produce golden traces that can be consumed by RTL and
software tests. Expected outcomes include exact safety state and output-enable
behavior, not only dashboard messages.

### Hardware-in-loop validation

Once boards exist, repeat representative golden scenarios with measured timing,
voltage/current, sensor data, and output behavior.

## Acceptance evidence

A subsystem should not be declared ready based only on a screenshot. Evidence may
include:

- automated test results;
- assertion logs;
- reproducible commands;
- synthesis/timing reports;
- measured electrical values;
- dataset/model reports;
- scenario traces;
- documented limitations.

## Regression rule

Every discovered defect with a deterministic reproduction should gain a regression
test before or with the fix whenever technically practical.

## Release gate

A tagged release should identify:

- exact source revision;
- supported hardware revision;
- protocol version;
- model/data versions where applicable;
- tests executed;
- known limitations;
- safety status and intended use.
