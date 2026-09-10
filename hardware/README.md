# ForgeSense Hardware Workspace

Hardware work is evidence-driven. Profiles under `hardware/profiles` define electrical and interface contracts; they do not substitute for measured validation.

Current baselines:

- `hardware_baseline_v1.json` — concrete pre-hardware component/reference selection;
- `interconnect_v1.json` — logical FPGA/ESP32/safety interconnect and pin-freeze state;
- `sensor_contract_v1.json` — normalized channel units, plausibility limits, and freshness;
- `sensor_phy_reference_v1.json` — acquisition/ADC/accelerometer/calibration boundary;
- `reference_circuit_v1.json` — low-voltage output/current-sense analytical values;
- `esp32s3_devkit_reference.json` — development ESP32-S3 transport profile.

`bom/preliminary_bom_v1.csv` is the current engineering BOM baseline. `kicad/` defines the schematic hierarchy and net-class intent before graphical capture. Behavioral SPICE references remain under `circuits/`.

No unverified FPGA external pin assignment, regulator/MOSFET/comparator selection, or measured electrical claim should be presented as final hardware evidence.
