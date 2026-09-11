# Calibration Campaign Orchestration

## Purpose

A single calibration session is not sufficient evidence for a source-controlled coefficient change. ForgeSense therefore packages repeated physical runs into one calibration campaign and evaluates them together with the existing repeated-run review policy.

`tools/run_calibration_campaign.py` coordinates the evidence pipeline without adding any runtime or actuator authority.

The campaign path is:

```text
run-01 session manifest -> assembled capture -> proposal
run-02 session manifest -> assembled capture -> proposal
run-03 session manifest -> assembled capture -> proposal
                                      |
                                      v
                         repeated-run review policy
                                      |
                                      v
                           calibration review result
                                      |
                                      v
                        atomic campaign evidence bundle
```

The default review policy requires at least three runs.

## Campaign manifest

Start from:

`hardware/calibration/calibration_campaign_template_v1.json`

The campaign manifest uses schema:

```text
forgesense.calibration_campaign_manifest.v1
```

It records:

- campaign identifier;
- exact repository commit;
- optional campaign-level board revisions;
- repeated-run review policy;
- unique run identifiers;
- one unique calibration session manifest for each run.

Relative `review_policy` and `session_manifest` paths are resolved from the campaign manifest's directory. The supplied template assumes the working campaign manifest is copied to the repository `evidence/` directory, so its policy path points back to `../hardware/calibration/` and its run sessions live under `evidence/run-01/`, `evidence/run-02/`, and `evidence/run-03/`.

If campaign-level board revisions are declared, every session must match them exactly. Every session must also use the campaign repository commit.

## Run independence

Every run must reference a different session manifest. Reusing the same session file under multiple run identifiers is rejected, including different relative path spellings that resolve to the same file.

Each session remains responsible for its own independent reference measurements, instrument metadata, uncertainty, diagnostic evidence hashes, current points, temperature points, and stationary accelerometer evidence.

The campaign runner does not generate reference truth and does not turn one physical run into multiple logical runs.

## Review-policy minimum

The runner loads the selected `forgesense.calibration_review_policy.v1` before generating the campaign bundle.

If the policy requires three runs and the campaign contains only two, the campaign is rejected before publication.

For every accepted run the runner:

1. validates campaign/session repository scope;
2. assembles the trusted diagnostic evidence into `forgesense.calibration_capture.v1`;
3. generates `forgesense.calibration_proposal.v1`;
4. preserves the proposal quality verdict;
5. passes all proposals to the existing repeated-run reviewer.

The final review remains `forgesense.calibration_review.v1`.

## Atomic publication

Campaign output is published atomically.

The runner builds all outputs in memory, then writes them to a temporary staging directory. The final output directory is created only after the complete bundle has been generated successfully.

If a session is malformed, diagnostic evidence is rejected, proposal generation fails, or review evaluation raises an error, the final output directory is not published.

An existing output directory is never overwritten.

This avoids a partially generated campaign being mistaken for complete retained evidence.

## Bundle layout

A successful evaluation produces a directory similar to:

```text
campaign-output/
  campaign.json
  review.json
  evidence-index.json
  runs/
    run-01/
      capture.json
      proposal.json
    run-02/
      capture.json
      proposal.json
    run-03/
      capture.json
      proposal.json
```

`campaign.json` uses schema:

```text
forgesense.calibration_campaign.v1
```

It records the run set, generated artifact hashes, review artifact hash, minimum-run requirement, final `review_ready` result, and the authority boundary.

A campaign bundle may still be published when review evaluation completes but `review_ready` is false. In that case the command exits non-zero and the retained bundle documents why the campaign failed the engineering review gate.

## Evidence integrity index

`evidence-index.json` uses schema:

```text
forgesense.calibration_evidence_index.v1
```

It contains SHA-256 entries for:

- canonical campaign manifest content;
- raw review-policy file bytes;
- raw session-manifest file bytes;
- every generated capture;
- every generated proposal;
- the repeated-run review artifact;
- the campaign summary artifact.

The index then computes a root SHA-256 over canonical JSON of the index fields excluding the seal itself.

This is a tamper-evident integrity seal. It is **not a digital signature**, does not establish signer identity, and does not replace an authenticated release-signing system.

The index explicitly records:

```text
integrity_index_only = true
digital_signature_present = false
automatic_runtime_application = false
may_relax_hard_safety_limits = false
```

## Authority boundary

Campaign completion does not apply calibration.

The campaign runner:

- has no serial control path;
- has no actuator-enable path;
- cannot write FPGA coefficients;
- cannot write ESP32 runtime calibration;
- cannot alter analog protection thresholds;
- cannot relax deterministic hard-safety limits.

Even when `review_ready = true`, reviewer approval and a separate source-controlled engineering change remain required.

## Run a campaign

Prepare three or more session manifests and a campaign manifest, then run:

```bash
python tools/run_calibration_campaign.py \
  evidence/campaign-001.json \
  --out-dir build/calibration-campaign-001
```

A review-ready campaign exits with status `0`.

A successfully packaged campaign whose repeated-run review is not ready exits with status `2` while retaining the evidence bundle.

Input or evidence validation failure exits without publishing the final output directory.

## Typical physical workflow

A complete physical campaign is:

```text
1. flash the load-disabled calibration FPGA image
2. capture read-only diagnostics for each operating point
3. record independent current and temperature references
4. build one calibration session manifest
5. repeat the complete session independently at least three times
6. create the campaign manifest
7. run the campaign tool
8. inspect review.json and evidence-index.json
9. retain the complete bundle with the physical bench records
10. make any coefficient change only through separate source review and verification
```

Do not reuse one diagnostic/session evidence set to satisfy the repeated-run count.

## Verification

Run:

```bash
make calibration-campaign-check
```

The gate covers:

- successful three-run orchestration;
- repeated-run review integration;
- policy minimum-run enforcement;
- campaign/session repository-commit consistency;
- duplicate-session rejection;
- atomic publication behavior;
- protection against overwriting retained evidence;
- SHA-256 evidence-index generation;
- explicit absence of a digital signature claim;
- review-only/no-actuator/no-runtime-application authority.

Synthetic regression data verifies orchestration behavior only. It is not physical calibration evidence and does not establish metrological accuracy or traceability.
