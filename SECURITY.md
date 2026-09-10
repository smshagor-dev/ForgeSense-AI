# Security Policy

ForgeSense AI combines control logic, embedded firmware, ML inference, telemetry,
and physical outputs. Security failures can therefore become safety failures.

## Reporting a vulnerability

Do not disclose a suspected vulnerability in a public issue, discussion, commit
message, screenshot, or shared dataset.

For now, report privately to the repository owner through a private GitHub channel
available to authorized collaborators. If a public security contact is introduced,
this document will be updated before public release.

Include:

- affected component and revision;
- reproduction steps;
- expected and observed behavior;
- security and physical-safety impact;
- whether credentials, keys, firmware images, datasets, or model artifacts are exposed;
- a minimal proof of concept when safe to provide.

## Security boundaries

The design must assume that the following can fail or become hostile:

- ESP32-S3 firmware;
- ML model output;
- telemetry clients;
- dashboard clients;
- network connectivity;
- sensor values;
- FPGA/MCU communication frames;
- stored configuration;
- update packages;
- external debug interfaces.

No single non-deterministic or network-connected component should be able to
silently defeat a hard FPGA safety invariant.

## Minimum controls

The implementation should progressively enforce:

- explicit input validation;
- protocol versioning;
- message integrity checks;
- freshness or sequence checks;
- bounded values and timeouts;
- fail-safe behavior on communication loss;
- least-privilege interfaces;
- authenticated configuration changes where networking is involved;
- signed production firmware/update artifacts when supported;
- disabled or restricted debug interfaces for deployment builds;
- reproducible builds and dependency review;
- no secrets in source control.

## Dependency and supply-chain rules

Pin dependencies where practical. Review transitive dependencies before adopting
new frameworks. CI should use minimal permissions. Third-party GitHub Actions must
be pinned to immutable commit SHAs unless an explicit security review documents
another decision.

## Safety notice

This repository is not a certified safety product. Do not use experimental builds
to protect people, control hazardous machinery, or switch mains voltage directly.
Existing certified protection systems must remain independent during development.
