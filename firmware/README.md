# ESP32-S3 Firmware Boundary

The first firmware implementation provides the byte-level protocol parser and
shared data types used by the edge runtime. It is written as platform-neutral
C++ so the contract can be tested on a host compiler before binding it to ESP-IDF.

The next firmware work will add UART/SPI transport, model artifact compatibility
checks, feature-window scheduling, inference publication, local event logging,
and bounded configuration/telemetry services.
