# Changelog

All notable repository-level changes are recorded here.

## Unreleased

### Added

- Executable deterministic machine and sensor simulator.
- Synthetic normal, bearing degradation, overcurrent, cooling-loss, and sensor-dropout scenarios.
- Compact versioned anomaly-detection baseline and model artifact export.
- ForgeSense Link Protocol v1 with CRC-16/CCITT-FALSE, sequence freshness, and ML compatibility checks.
- Python reference codec and cross-language golden frame.
- Host-testable C++ firmware protocol parser.
- Synthesizable VHDL hard-limit monitor, watchdog, intelligence freshness gate, safety state machine, and top-level safety core.
- Self-checking VHDL safety-state testbench.
- End-to-end virtual bearing-degradation demo.
- Implementation CI for Python, C++ and GHDL checks.
- Implementation status documentation.

### Fixed

- Prevented startup transients from being treated as control-relevant ML critical events in the virtual integration demo.
- Locked the C++ ML payload length to the protocol's 14-byte normative payload using a shared golden frame test.

## 2026-09-10

### Added

- Initial project foundation.
- Engineering documentation, safety model, security policy, contribution workflow, roadmap, and controlled development license.
