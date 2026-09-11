# Calibration Bundle Verification and Change Packaging

## Purpose

ForgeSense calibration campaign output is retained engineering evidence. Before a reviewer uses that evidence to consider a source-controlled calibration change, the bundle must be checked for tampering, cross-artifact consistency, source provenance, and authority boundaries.

`tools/verify_calibration_bundle.py` verifies the campaign bundle. `tools/prepare_calibration_change_package.py` creates a reviewer-ready change package only after the campaign bundle and its original source provenance both verify successfully.

Neither utility applies calibration, writes runtime coefficients, enables an actuator, or relaxes deterministic hard-safety limits.

## Two verification levels

The verifier supports two levels.

Bundle-only verification checks:

- `evidence-index.json` schema and authority;
- recomputation of the root SHA-256 integrity seal;
- every indexed generated artifact SHA-256;
- rejection of unindexed extra generated files;
- campaign/review schema consistency;
- campaign/review `review_ready` consistency;
- campaign review hash linkage;
- per-run capture/proposal file hashes;
- capture/proposal repository commit consistency;
- proposal-to-capture identifier linkage;
- proposal `source_capture_sha256` against canonical capture JSON;
- review-only/no-runtime-write authority invariants.

Source-provenance verification additionally checks the original retained inputs:

- canonical campaign manifest hash;
- raw review-policy file hash;
- raw session-manifest file hashes;
- every diagnostic evidence file SHA-256 referenced by each assembled capture.

This separates portable bundle integrity from full retained-source provenance.

## Verify a bundle only

```bash
python tools/verify_calibration_bundle.py \
  build/calibration-campaign-001
```

A successful result reports:

```text
bundle_integrity_pass = true
semantic_chain_pass = true
source_provenance_pass = false
```

`source_provenance_pass = false` in this mode does not mean the bundle failed. It means the original source tree was not supplied for re-verification.

## Verify original source provenance

Supply the original campaign source root and the exact campaign manifest:

```bash
python tools/verify_calibration_bundle.py \
  build/calibration-campaign-001 \
  --source-root evidence \
  --campaign-manifest evidence/campaign-001.json \
  --report-out build/calibration-campaign-001-verification.json
```

For a fully verified campaign:

```text
bundle_integrity_pass = true
semantic_chain_pass = true
source_provenance_pass = true
```

Changing a retained diagnostic JSON, session manifest, review policy, generated capture, generated proposal, campaign summary, review artifact, or evidence-index root causes verification failure.

## Tamper detection boundary

The SHA-256 evidence index is tamper-evident integrity metadata. It is **not a digital signature** and does not authenticate the identity of a reviewer, developer, laboratory, or organization.

The verifier therefore distinguishes:

- integrity: bytes and cross-links still match the retained evidence chain;
- provenance: supplied original source files match the hashes recorded by the campaign;
- authentication: requires a separately managed signing system.

Do not describe a passing SHA-256 verification as proof of signer identity or certified metrological traceability.

## Reviewer-ready change package

A calibration change package can be prepared only when all of the following are true:

- bundle integrity verifies;
- semantic linkage verifies;
- original source provenance verifies;
- the repeated-run review reports `review_ready = true`;
- current, temperature, and accelerometer repeatability sections pass.

Run:

```bash
python tools/prepare_calibration_change_package.py \
  build/calibration-campaign-001 \
  --source-root evidence \
  --campaign-manifest evidence/campaign-001.json \
  --out-dir build/calibration-change-001
```

The output directory contains:

```text
calibration-change-001/
  change-package.json
  signing-request.json
  signing-payload.txt
```

`change-package.json` uses schema:

```text
forgesense.calibration_change_package.v1
```

It records:

- campaign identifier;
- exact repository commit;
- verified evidence-root SHA-256;
- review SHA-256;
- source-provenance verification state;
- candidate current fit values;
- candidate temperature offset;
- candidate accelerometer bias values;
- engineering uncertainty proxies;
- review checks;
- explicit reviewer/source-control authority requirements.

The package always states:

```text
runtime_write_permitted = false
automatic_runtime_application = false
may_control_actuators = false
may_relax_hard_safety_limits = false
```

The package is engineering review input. It is not a provisioning command.

## External signing interface

`signing-request.json` uses schema:

```text
forgesense.calibration_signing_request.v1
```

The signing request contains a domain-separated UTF-8 payload covering:

- campaign identifier;
- repository commit;
- evidence-root SHA-256;
- review SHA-256;
- change-package SHA-256.

The exact payload is also written to `signing-payload.txt`.

The local utility never reads or stores a signing private key. It records:

```text
external_signature_required = true
digital_signature_present = false
```

An independently managed signing system may sign the exact UTF-8 payload. Signature storage, trust anchors, certificate policy, key rotation, revocation, and cryptographic signature verification remain separate concerns and must not be inferred from the signing request alone.

## Atomic publication

Change-package publication is atomic. Files are built in a staging directory and the final directory is created only after verification and package generation succeed.

An existing output directory is never overwritten.

This prevents an incomplete or failed reviewer package from being mistaken for retained approved evidence.

## Engineering approval boundary

Even after a bundle verifies and the campaign is review-ready:

1. a human reviewer still has to approve the engineering change;
2. the coefficient change must be made separately in source control;
3. deterministic verification must be rerun against that source change;
4. hard-safety limits remain independently governed;
5. no utility in this workflow performs a runtime write.

A future provisioning mechanism must remain separately gated and must never allow evidence tooling to relax hard-safety limits.

## Verification gate

Run:

```bash
make calibration-bundle-verification-check
```

The regression and source-contract gate covers:

- valid bundle-only verification;
- full original-source provenance verification;
- generated-artifact tamper rejection;
- evidence-root tamper rejection;
- original diagnostic tamper rejection;
- `review_ready` requirement for change packaging;
- no-runtime-write authority;
- external-signing request semantics;
- atomic publication and overwrite protection.

Synthetic tests verify evidence-handling behavior only. They are not physical calibration evidence and do not establish certification, traceability, or production metrology performance.
