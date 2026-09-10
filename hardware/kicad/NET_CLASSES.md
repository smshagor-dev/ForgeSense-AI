# Preliminary PCB Net Classes

These are routing intentions, not manufacturing rules. Final widths require copper weight, temperature-rise target and PCB-fabricator stackup.

| Class | Nets | Intent |
| --- | --- | --- |
| MOTOR_POWER | VIN_PROTECTED, MOTOR_12V, motor return path | Short/wide, current-capacity calculation required |
| KELVIN_SENSE | CS_SHUNT_P, CS_SHUNT_N | Differential Kelvin routing directly from shunt pads; no motor current in sense branches |
| ANALOG | CS_AMP_OUT, ADC analog inputs/reference | Keep away from switch-node/gate edges; controlled return path |
| SAFETY | ANALOG_HARD_TRIP, ESTOP_SENSE, ESTOP_GATE_OK | Defined bias at reset/unplugged state; avoid shared noisy routing |
| DIGITAL_FAST | ADC/ACC SPI | Short source-referenced routes; optional 22–47 ohm source damping footprints |
| DIGITAL | UART, I2C, status/service | 3.3 V logic unless explicitly translated |
| POWER_LOGIC | +5V_SYS, +3V3_SYS | Local bulk plus IC decoupling |

The Tang Nano 9K schematic shows 3.3 V and 1.8 V I/O banks; carrier routing must not assume every exposed FPGA pin is 3.3 V tolerant.
