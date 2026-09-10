# ForgeSense AI Documentation

This directory is the engineering source of truth for system behavior that cannot
be understood safely from source code alone.

## Start here

1. [`VISION.md`](VISION.md) — problem, goals, non-goals, and differentiation.
2. [`SYSTEM_REQUIREMENTS.md`](SYSTEM_REQUIREMENTS.md) — measurable first-system requirements.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — subsystem boundaries and data/control paths.
4. [`SAFETY_MODEL.md`](SAFETY_MODEL.md) — hard invariants, unsafe assumptions, and fail-safe rules.
5. [`HARDWARE_DESIGN.md`](HARDWARE_DESIGN.md) — electronics and PCB design discipline.
6. [`FPGA_VHDL.md`](FPGA_VHDL.md) — RTL structure and verification rules.
7. [`AI_ML.md`](AI_ML.md) — data, training, evaluation, export, and inference constraints.
8. [`FIRMWARE.md`](FIRMWARE.md) — ESP32-S3 responsibilities and trust boundary.
9. [`VERIFICATION.md`](VERIFICATION.md) — test strategy and evidence requirements.
10. [`IP_AND_PUBLICATION.md`](IP_AND_PUBLICATION.md) — novelty, prior art, disclosure, and licensing discipline.

The project roadmap lives at [`../ROADMAP.md`](../ROADMAP.md).

## Documentation rule

A source-code change that changes an interface, requirement, safety invariant,
protocol field, electrical assumption, model contract, or test acceptance rule is
incomplete until the relevant documentation changes with it.

## Decision records

Material architecture decisions will be recorded under `docs/decisions/` using a
short decision record containing context, options, decision, consequences, and
validation evidence. This prevents important design reasoning from becoming
tribal knowledge.
