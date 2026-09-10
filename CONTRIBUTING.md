# Contributing to ForgeSense AI

ForgeSense AI is under controlled development. Contributions should strengthen
safety, determinism, reproducibility, testability, and maintainability rather than
only make a demo appear more capable.

## Before contributing

Read:

- `README.md`
- `ROADMAP.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/SAFETY_MODEL.md`
- `docs/VERIFICATION.md`
- `docs/IP_AND_PUBLICATION.md`

Do not submit material copied from proprietary datasheets, closed repositories,
restricted standards, or code with incompatible licensing.

## Change expectations

Every non-trivial change should answer five questions:

1. What requirement or defect does this address?
2. What subsystem boundary changes?
3. What new failure behavior is introduced?
4. How is the change tested?
5. What documentation must change with it?

Safety-critical behavior must not be hidden inside ML output, dashboard logic, or
network services. Hard safety invariants belong in deterministic control paths.

## Repository conventions

- Keep FPGA RTL synthesizable unless the file is explicitly a testbench.
- Keep simulation-only constructs outside synthesizable RTL directories.
- Prefer explicit clock-domain boundaries and synchronized asynchronous inputs.
- Version protocol changes and preserve backward-compatibility rules where practical.
- Keep training code separate from exported inference artifacts.
- Record dataset provenance, preprocessing, splits, and evaluation metrics.
- Never commit secrets, credentials, private keys, tokens, or personal datasets.
- Hardware changes must include reasoning for voltage, current, protection, and connector choices.
- Documentation is part of the implementation and should change in the same commit when contracts change.

## Commit style

Use focused commits with a short conventional prefix where useful:

```text
docs: define sensor interface contract
rtl: add watchdog timeout logic
firmware: validate protocol sequence counter
ml: add anomaly baseline evaluation
hardware: add protected current-sense input
ci: verify documentation links
fix: reject stale inference frames
```

## Pull request checklist

A change should be reviewable and include, where applicable:

- requirement or issue reference;
- design rationale;
- test evidence;
- simulation waveform or machine-readable result for RTL changes;
- ML metrics and dataset description for model changes;
- electrical calculations for circuit changes;
- compatibility notes for protocol changes;
- safety impact statement;
- updated documentation.

## Security-sensitive work

Do not open a public issue for a suspected vulnerability. Follow `SECURITY.md`.

## Licensing and intellectual property

By contributing, you confirm that you have the right to submit the contribution
and allow the repository owner to incorporate it into ForgeSense AI under the
repository's current or future licensing model. If that is not acceptable, do
not submit the contribution.
