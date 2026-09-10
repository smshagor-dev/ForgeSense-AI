# Hardware and Circuit Design

## Goal

The electronics should turn a validated reference setup into a reproducible,
protected, low-cost implementation without hiding electrical assumptions.

## Planned functional blocks

```text
DC input
  |
  +--> reverse-polarity / transient protection
  +--> regulated rails
          |
          +--> FPGA
          +--> ESP32-S3
          +--> sensors / analog front end

Sensors --> filtering / protection / translation --> FPGA or MCU acquisition
FPGA --> protected output driver --> low-voltage test load
Emergency input -------------------> deterministic safety path
```

## Schematic rules

Every electrical interface must document:

- nominal voltage;
- absolute maximum considered by the design;
- expected current;
- source/sink direction;
- pull-up/pull-down behavior;
- startup behavior;
- protection components;
- connector pinout;
- grounding assumption;
- failure behavior.

## Power rules

- No FPGA or MCU GPIO may receive an unspecified external voltage.
- Regulator headroom, thermal dissipation, and worst-case current must be calculated.
- Each digital IC requires appropriate local decoupling based on vendor guidance.
- Analog sensing and switching return currents should not be routed through sensitive references without analysis.
- Output loads must not draw power through logic pins.

## Output design

A relay or MOSFET module used during early validation is a test interface, not the
final electrical design. The custom board should include a driver chosen from
load voltage/current, switching frequency, isolation needs, transient energy, and
failure mode.

## PCB evidence

Before manufacturing, retain:

- schematic ERC result;
- PCB DRC result;
- reviewed power tree;
- connector table;
- BOM with manufacturer part numbers and sourcing alternatives;
- critical component calculations;
- fabrication files;
- assembly drawing;
- bring-up checklist;
- board revision identifier.

## Low-cost discipline

Cost reduction must not remove basic protection or observability. Prefer commonly
available parts, second-source options, test points, and modular sensor connectors
until measurements justify tighter integration.
