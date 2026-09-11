# ESP32-S3 Commissioning Bridge

This is a separate bench-only ESP-IDF image for the ESP32-S3-DevKitC-1. It is not the production edge runtime.

It forwards bytes transparently between:

- the ESP32-S3 built-in USB Serial/JTAG port presented to the PC; and
- UART1 at 115200 8N1 on GPIO17 TX / GPIO18 RX connected to the Tang Nano 9K harness.

The image deliberately contains no Wi-Fi, ML inference, event storage, dashboard transport, or actuator command logic. Logging and the normal console are disabled so raw commissioning traffic is not mixed with text output.

Build with an ESP-IDF environment:

```bash
idf.py set-target esp32s3
idf.py build
idf.py -p PORT flash
```

Then use the host utility documented in `docs/COMMISSIONING_UTILITY.md`.

The source uses the ESP-IDF UART driver for GPIO17/18 and the USB Serial/JTAG driver for the PC-facing raw byte channel. Successful target compilation and USB/UART bench behavior remain evidence to be retained from the actual tool/board run.
