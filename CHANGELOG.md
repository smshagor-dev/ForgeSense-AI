# Changelog

All notable repository-level changes are recorded here.

## Unreleased

### Added

- Executable deterministic machine and sensor simulator.
- Synthetic normal, bearing degradation, overcurrent, cooling-loss, and sensor-dropout scenarios.
- Compact versioned anomaly-detection baseline and model artifact export.
- Deterministic feature-window runtime for edge inference.
- ForgeSense Link Protocol v1 with CRC-16/CCITT-FALSE, sequence freshness, and ML compatibility checks.
- Python reference codec and resynchronizing stream decoder.
- Cross-language protocol golden frame.
- Host-testable C++ firmware frame parser, fixed-memory stream decoder, and freshness gate.
- Synthesizable VHDL hard-limit monitor, watchdog, CRC function, raw-byte link receiver, intelligence freshness gate, safety state machine, and integrated ForgeSense core.
- Self-checking VHDL safety-state and link-receiver testbenches.
- Cycle-level closed-loop safety oracle matching the FPGA authority model.
- End-to-end virtual bearing-degradation and closed-loop control demos.
- Implementation CI for Python, C++ and GHDL checks.
- Transport/control integration documentation.

### Fixed

- Prevented startup transients from being treated as control-relevant ML critical events in the virtual integration demo.
- Locked the C++ ML payload length to the protocol's 14-byte normative payload using a shared golden frame test.
- Prevented pre-operational ML warm-up from expiring the FPGA intelligence watchdog.
- Ensured invalid, stale, incompatible, CRC-corrupt, and replayed observations cannot kick the operational watchdog.

## 2026-09-10

### Added

- Initial project foundation.
- Engineering documentation, safety model, security policy, contribution workflow, roadmap, and controlled development license.
