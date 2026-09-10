# ForgeSense AI Roadmap

This roadmap is ordered by engineering dependency rather than calendar dates.
Items move forward only when their exit criteria are met.

## Foundation baseline

- [x] Repository identity and vision
- [x] Contribution and conduct policy
- [x] Security policy
- [x] Development license
- [x] Documentation map
- [x] Safety boundary
- [x] IP/publication discipline
- [x] Issue and pull-request templates
- [x] Foundation CI

Exit criteria: repository can accept implementation work without changing its
core engineering rules or directory strategy.

## System contract

- [ ] Freeze the first machine/test-load profile
- [ ] Define sensor channels and engineering units
- [ ] Define safe/unsafe states and hard limits
- [ ] Define FPGA/MCU responsibility matrix
- [ ] Define reset, startup, degraded, shutdown, and recovery behavior
- [ ] Select UART or SPI reference transport
- [ ] Define versioned frame format, integrity, sequence, and timeout rules
- [ ] Define telemetry schema

Exit criteria: two independent implementations can interoperate from written
contracts without guessing behavior.

## Executable digital twin

- [ ] Machine-state simulator
- [ ] Temperature model
- [ ] Vibration model
- [ ] Current/load model
- [ ] Sensor noise, dropout, drift, saturation, and stuck-value models
- [ ] Fault injection library
- [ ] Deterministic scenario seeds
- [ ] Golden trace format

Exit criteria: repeatable normal and fault scenarios generate versioned reference
traces suitable for RTL, firmware, and ML tests.

## FPGA control core

- [ ] Clock/reset infrastructure
- [ ] Input synchronizers
- [ ] Sensor acquisition interfaces
- [ ] Deterministic filtering primitives
- [ ] Safety finite-state machine
- [ ] Hard-limit monitors
- [ ] Watchdog and communication timeout
- [ ] Stale/invalid intelligence rejection
- [ ] Output interlock
- [ ] Fault latch and controlled recovery
- [ ] Self-checking RTL testbenches
- [ ] Synthesis and timing baseline for reference FPGA

Exit criteria: all declared safety invariants pass automated normal, boundary,
fault, reset, timeout, and recovery tests.

## Edge firmware core

- [ ] ESP32-S3 project baseline
- [ ] Transport driver
- [ ] Frame parser/serializer
- [ ] Sequence and integrity validation
- [ ] Feature extraction boundary
- [ ] ML inference interface
- [ ] Local telemetry service
- [ ] Configuration validation
- [ ] Event log
- [ ] Watchdog and degraded-mode behavior

Exit criteria: firmware interoperates with the simulator and cannot command the
FPGA outside the documented bounded interface.

## ML baseline

- [ ] Dataset schema and provenance manifest
- [ ] Synthetic baseline dataset
- [ ] Preprocessing pipeline
- [ ] Feature baseline
- [ ] Classical anomaly baseline
- [ ] Compact neural baseline where justified
- [ ] Time-aware train/validation/test split policy
- [ ] False-alarm and missed-fault analysis
- [ ] Quantization/export pipeline
- [ ] ESP32-S3 memory and latency budget
- [ ] Model card for every candidate release

Exit criteria: selected model beats a documented non-ML baseline where relevant,
meets memory/latency constraints, and has defined rejection thresholds.

## End-to-end virtual system

- [ ] Simulator -> acquisition -> control -> inference -> bounded decision loop
- [ ] Communication loss tests
- [ ] Corrupted/stale frame tests
- [ ] Sensor drift/dropout tests
- [ ] False-positive ML tests
- [ ] False-negative ML tests
- [ ] Reset during fault tests
- [ ] Reproducible system test report

Exit criteria: all critical scenarios produce deterministic safe outcomes even
when the intelligent layer is wrong, absent, stale, or corrupted.

## Reference hardware validation

- [ ] Finalize FPGA development board
- [ ] Finalize ESP32-S3 board
- [ ] Validate 3.3 V logic compatibility
- [ ] Add low-voltage temperature sensing
- [ ] Add current sensing
- [ ] Add vibration sensing
- [ ] Add emergency input
- [ ] Add isolated/protected output path
- [ ] Hardware-in-loop scenarios
- [ ] Measure latency, current draw, noise, and thermal behavior

Exit criteria: physical measurements match the documented envelopes and virtual
tests reproduce on the reference hardware within defined tolerances.

## Custom electronics

- [ ] Electrical requirements review
- [ ] Power tree and protection
- [ ] Analog front end
- [ ] FPGA and MCU integration
- [ ] Debug/programming access
- [ ] Safe output drivers
- [ ] Schematic review checklist
- [ ] PCB layout rules
- [ ] DRC/ERC clean design
- [ ] BOM with sourcing alternatives
- [ ] Manufacturing outputs
- [ ] Bring-up procedure

Exit criteria: custom board passes power, interface, protection, and functional
bring-up without relying on undocumented modifications.

## Product-quality validation

- [ ] Long-duration soak testing
- [ ] Brownout and power-cycle testing
- [ ] Communication abuse testing
- [ ] Dataset-shift experiments
- [ ] Calibration drift experiments
- [ ] Fault coverage report
- [ ] Performance and resource report
- [ ] Threat-model review
- [ ] Hazard-analysis review
- [ ] Documentation completeness review

Exit criteria: limitations are measured and documented; no unsupported safety or
novelty claim is required for the system to be useful.

## Future research directions

Potential research extensions include multi-sensor confidence estimation,
uncertainty-aware maintenance decisions, adaptive sampling, model-drift detection,
formal checking of control invariants, secure update paths, fleet-level learning,
and hardware acceleration of selected feature-extraction or inference operations.

Research directions are hypotheses, not promises or novelty claims.
