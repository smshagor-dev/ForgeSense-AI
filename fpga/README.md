# FPGA Deterministic Safety Core

The first synthesizable RTL slice implements:

- hard temperature/vibration/current limits;
- sensor-validity fail-safe handling;
- communication watchdog;
- deterministic safety state machine;
- fault latching and controlled recovery;
- validated-intelligence freshness gate;
- output enable only in permitted states.

`intelligence_gate.vhd` consumes already-decoded protocol fields. A byte-stream
parser is intentionally kept separate so framing bugs cannot silently alter the
safety-state-machine contract.

Numeric hard limits are provisional simulation defaults and must be replaced by
measured electrical/mechanical requirements before physical output control.
