# Claim and evidence boundary

## What the repository demonstrates

- The project was built and exercised on Linux. The saved host inventory records Ubuntu 26.04 LTS x86-64 and kernel `7.0.0-31-generic`.
- The privileged eBPF smoke passed on 2026-11-14. In the full-detail known-count case, 2,000 eligible calls yielded 2,000 selected, completed, emitted, consumed, and written events; ring-reservation and sink drops were zero. LOW and sentinel-only checks also passed.
- The immutable pilot run `data/pilot/bounded-q01-4blocks-20261114-001/` contains 16 valid attempts: four paired blocks for each of CPU and I/O, comparing NONE with fixed 1% sampling (FIX_Q01).
- In this pilot, paired throughput-loss estimates were 1.85% for CPU and 11.21% for I/O. Common-cutoff incident capture was 1.17% and 1.00%, respectively; on-time alert recall was 0% in each workload.
- The runner produced 10,000-draw whole-block bootstrap intervals, while marking the four-block conditions underpowered and the 5% budget classifications inconclusive.
- All 16 pilot attempts carry the external-CPU noise warning. They are valid records but exploratory, not clean-host confirmatory evidence.

## What these observations do not establish

The pilot does not compare ADAPT_GATE or ADAPT_SWITCH with the fixed-policy frontier. It does not establish an adaptive advantage, fixed-policy superiority, 5% budget compliance, detector sensitivity across anomaly durations, or generalization to other hosts. The pilot's capture rate, detector alert recall, throughput loss, and transport loss are separate quantities. No hard instantaneous overhead guarantee or novelty claim is made.

The source/configuration support the planned 56 primary cells and 672 trials at 12 paired blocks. That is a protocol estimate, not the completed experiment count. Calibration, pilot, synthetic, smoke, and confirmatory populations must remain distinct.

## Related-work boundary

Overhead-targeted runtime monitoring (SMCO and QVM), adaptive eBPF network telemetry (Magnani et al.), component-level eBPF tracing overhead (Naas et al.), and retroactive distributed tracing (Hindsight) are prior art. The report positions this implementation as a Linux syscall/scheduler measurement and comparison study; it does not claim the first adaptive eBPF controller, first explicit budget, or first loss-accounting scheme.

The literature bibliography and source-access notes remain in `latex_report/references.bib` and `research/evidence_access.csv`. The missing source-precedence review mentioned in older planning notes is not used to invent a novelty claim.
