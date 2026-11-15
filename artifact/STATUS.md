# Project and evidence status

Status reconciled against the Linux artifacts on 2026-11-15.

## Completed and recorded

- Implemented the CO-RE eBPF sentinel/detail programs, C/libbpf agent and workload generators, Python runner/analysis pipeline, configurations, schemas, and Linux setup/reproduction tooling.
- Built and exercised on Ubuntu 26.04 LTS x86-64, kernel `7.0.0-31-generic`; target tool versions are retained under `state/bootstrap/`.
- Passed the privileged Linux known-count smoke on 2026-11-14. The HIGH case delivered all 2,000 expected records, and LOW/SENT checks passed.
- Recorded immutable calibration attempts and 16 valid paired pilot attempts: four blocks each for CPU and I/O, comparing NONE with FIX_Q01.
- Reproduced the pilot analysis, created an IEEEtran report and a detailed reproduction guide, and maintained the result-to-claim boundary.

## Pilot result scope

The four-block pilot estimates throughput loss at 1.85% for CPU work (95% interval −0.63% to 5.60%) and 11.21% for I/O (10.85% to 11.46%). Common-cutoff capture is 1.17% and 1.00%, respectively; on-time alert recall is zero in both. All 16 attempts carry the external-CPU noise warning. The sample is below the runner's eight-block decision threshold, so the declared 5% budget outcome remains inconclusive. The pilot contains no ADAPT_GATE or ADAPT_SWITCH comparison.

## Remaining research scope

The 56-cell/672-trial primary matrix is a protocol estimate, not the completed sample. Full fixed-frontier/adaptive comparisons, clean-host sensitivity, drift/background conditions, robustness and independent-host studies are not part of this pilot. Complete calibration and freeze before claiming confirmatory compliance, adaptive benefit, or cross-host generalization.

See `research/claims.md`, `paper/claim_evidence.csv`, and the compiled IEEE report for the exact evidence and boundaries.
