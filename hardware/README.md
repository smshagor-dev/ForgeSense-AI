# ForgeSense Hardware Workspace

Hardware work is evidence-driven. Profiles under `hardware/profiles` define pre-hardware interfaces and constraints; they do not substitute for a schematic, measured transfer function, PCB layout, or validation report.

Current reference profiles:

- `sensor_contract_v1.json` — normalized channel units, plausibility limits, and freshness;
- `sensor_phy_reference_v1.json` — vendor-neutral acquisition/ADC/accelerometer/calibration boundary;
- `reference_circuit_v1.json` — low-voltage power/output/current-sense reference values and analytical constraints;
- `esp32s3_devkit_reference.json` — development ESP32-S3 transport profile.

Behavioral circuit references are under `hardware/circuits/`. They are intended for SPICE/topology verification before component selection; they are not certification evidence.

Future schematic, BOM, PCB, manufacturing, and measured calibration files should be added only with explicit revision identifiers and evidence.
