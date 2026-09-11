# Tang Nano 9K Bring-Up Wiring Assembly

This assembly guide is for the low-voltage development setup only. It is not a mains-wiring guide and is not certification evidence.

## Logic-only first assembly

Before any motor supply is connected:

```text
ESP32-S3-DevKitC-1                  Tang Nano 9K
-------------------                 -------------
GND ------------------------------> GND
GPIO17 / U1TXD ---- 33R ----------> J5-5 / FPGA25
GPIO18 / U1RXD <--- 33R ----------- J5-6 / FPGA26

Motor supply: DISCONNECTED
Gate-driver power stage: DISCONNECTED or inhibited
Sensor board: optional; leave disconnected for first UART smoke
```

Do not connect the 5 V rails of the two development boards together merely because both boards are USB-powered. The first logic test needs a common ground and the two 3.3 V UART signals only.

## Safety/service harness

```text
Comparator hard-trip output ------> J5-7  / FPGA27
E-stop observation buffer --------> J5-8  / FPGA28
J5-9 / FPGA29 --------------------> gate-driver command input
Service recovery input -----------> J5-10 / FPGA30
```

The physical normally-closed E-stop inhibit must remain wired directly to the gate-driver inhibit path. `ESTOP_SENSE` is an FPGA observation and is not the only means of disabling the output stage.

## TMP117 harness

```text
J5-11 / FPGA33 <------------------> TMP117 SCL
J5-12 / FPGA34 <------------------> TMP117 SDA
GND -------------------------------- sensor GND
3.3 V quiet rail ------------------ sensor V+
```

SCL and SDA require the external pull-ups defined by the hardware baseline. The FPGA pins are open-drain in the physical design.

## ADXL355 harness

```text
J5-13 / FPGA40 -------------------> CS_N
J5-14 / FPGA35 -------------------> SCLK
J5-15 / FPGA41 -------------------> MOSI
J5-16 / FPGA42 <------------------- MISO
J5-17 / FPGA51 <------------------- DRDY
GND ------------------------------- sensor GND
3.3 V quiet rail ------------------ sensor V+/VDDIO
```

## ADS131M02 harness

```text
J5-18 / FPGA53 -------------------> CS_N
J5-19 / FPGA54 -------------------> SCLK
J5-20 / FPGA55 -------------------> DIN
J5-21 / FPGA56 <------------------- DOUT
J5-22 / FPGA57 <------------------- DRDY_N
GND ------------------------------- ADC DGND reference
3.3 V quiet rail ------------------ ADC AVDD/DVDD support network
```

The ADC clock/reference/decoupling and analog input network are defined by the schematic baseline; they are not replaced by this harness description.

## Assembly rules

- Keep the RGB panel disconnected because several selected J5 pins are shared with that connector.
- Do not use TF-card FPGA pins 36-39 or onboard BL702 UART FPGA pins 17/18 for the ForgeSense harness.
- Do not connect 3.3 V peripherals to the external 1.8 V BANK3 pins 79-86.
- Connect ground/reference conductors before signal conductors.
- Verify continuity and absence of power-to-ground shorts before applying power.
- Keep `LOAD_ENABLE` physically inhibited until the logic-only and safety checks have been recorded as passing.
