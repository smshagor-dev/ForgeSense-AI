# ForgeSense Hardware Workspace

Hardware work is evidence-driven. Profiles under `hardware/profiles` define electrical and interface contracts; they do not substitute for measured validation or certification.

Current baselines:

- `hardware_baseline_v1.json` — component-backed schematic reference (`HW-BL-003`);
- `power_entry_v1.json` — 12 V fuse/TVS/eFuse protection, UVLO/OVLO, current limiting, and slew contract;
- `sensor_support_v1.json` — ADS131M02, ADXL355, and TMP117 supply/clock/bus/decoupling contract;
- `reference_circuit_v1.json` — current transfer, analog trip, power, gate-drive, and motor-output calculations;
- `interconnect_v1.json` — FPGA/ESP32/safety interconnect and pin-freeze state;
- `sensor_contract_v1.json` — normalized channel units, plausibility limits, and freshness;
- `sensor_phy_reference_v1.json` — acquisition/calibration boundary;
- `esp32s3_devkit_reference.json` — ESP32-S3 development transport profile.

`bom/preliminary_bom_v1.csv` is the electrical BOM baseline and contains both selected reference parts and unresolved mechanical items.

KiCad-preparation sources:

- `kicad/schematic_contract_v1.json` — machine-readable sheet/critical-net contract;
- `kicad/POWER_AND_SAFETY_SHEET_V1.md` — capture-level connection and layout rules;
- `kicad/component_packages_v1.csv` — manufacturer MPN/package manifest;
- `kicad/net_endpoints_v1.csv` — endpoint, voltage-domain, safety-class, and freeze-state table;
- `kicad/SCHEMATIC_HIERARCHY.md` — sheet organization;
- `kicad/NET_CLASSES.md` — routing-class intent.

Behavioral SPICE references remain under `circuits/`.

Run `make hardware-check` after any electrical, BOM, package, net, or profile change.

Selected components remain engineering references until physical validation. KiCad footprint identifiers must be bound against the installed library rather than guessed. No unverified Tang Nano external application pin, measured transient/EMC/thermal result, or functional-safety claim should be presented as final evidence.
