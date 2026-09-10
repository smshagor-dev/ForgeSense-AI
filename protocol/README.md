# FPGA ↔ Edge Intelligence Protocol

`SPEC_V1.md` is the normative byte-level contract. The Python codec is the
executable reference used by tests and simulation. Firmware and RTL implementations
must match its golden vectors rather than inventing local interpretations.

The protocol deliberately carries bounded ML observations rather than arbitrary
actuator commands.
