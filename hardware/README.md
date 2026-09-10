# ForgeSense Hardware Workspace

Hardware work is evidence-driven. Profiles under `hardware/profiles` define electrical and interface contracts; they do not substitute for measured validation or certification.

Current baselines:

- `hardware_baseline_v1.json` — component-backed schematic reference (`HW-BL-002`);
- `reference_circuit_v1.json` — current transfer, protection, power, gate-drive, and trip calculations;
- `interconnect_v1.json` — FPGA/ESP32/safety interconnect and pin-freeze state;
- `sensor_contract_v1.json` — normalized channel units, plausibility limits, and freshness;
- `sensor_phy_reference_v1.json` — acquisition/ADC/accelerometer/calibration boundary;
- `esp32s3_devkit_reference.json` — development ESP32-S3 transport profile.

`bom/preliminary_bom_v1.csv` is the engineering BOM baseline.

`kicad/schematic_contract_v1.json` is the machine-readable schematic-capture contract. `kicad/POWER_AND_SAFETY_SHEET_V1.md`, `SCHEMATIC_HIERARCHY.md`, and `NET_CLASSES.md` define the capture structure, critical nets, layout intent, and unresolved decisions before graphical KiCad capture.

Behavioral SPICE references remain under `circuits/`.

Run `make hardware-check` after any electrical/BOM/profile change.

Selected components remain engineering references until physical validation. No unverified Tang Nano external pin assignment, measured transient claim, EMC claim, thermal claim, or functional-safety claim should be presented as final evidence.
