# Repository Software Qualification

## Purpose

ForgeSense separates repository-executable qualification from physical qualification. The repository qualification demonstrates deterministic software/RTL contracts and fail-closed behavior. It does not substitute for real hardware soak, brownout, EMC, thermal, latency, or reliability evidence.

## Executable qualification

`simulator/forgesense_sim/qualification.py` produces `forgesense.software_qualification.v1` and covers:

- the seven-scenario deterministic validation matrix;
- normal-envelope stability across multiple deterministic sensor-noise seeds;
- replayed intelligence-frame abuse and watchdog shutdown;
- reset/startup load-disable behavior;
- required-sensor dropout fail-closed behavior;
- a dataset-shift/stuck-current case proving the deterministic current hard limit remains independent of ML.

Run:

```bash
make software-qualification-check
```

The target runs the qualification regression together with the complete sensor-impairment tests. It is suitable for CI because the qualification is deterministic and does not depend on physical devices or external services.

## Sensor impairment model

The digital twin now supports per-channel:

- Gaussian noise override;
- static bias;
- linear drift versus simulated time;
- minimum/maximum saturation;
- stuck-value faults;
- dropout/invalidity.

Legacy dropout flags and the historical default sensor-noise levels remain compatible with the existing scenario matrix.

## Evidence boundary

A passing repository qualification means only that the declared deterministic reference behavior is internally consistent. The following remain separate physical evidence tasks:

- real-duration soak testing;
- brownout waveform testing;
- repeated power-cycle testing;
- physical UART/SPI/I2C abuse;
- target ESP32-S3 memory and latency measurement;
- FPGA timing closure on the selected toolchain;
- real sensor drift/calibration experiments;
- EMI/surge/noise immunity;
- thermal measurements;
- real-machine false alarms, missed faults, and detection lead time.
