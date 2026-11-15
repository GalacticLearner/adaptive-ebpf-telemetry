# Adaptive eBPF Telemetry with an Explicit Overhead Budget

The complete IEEE conference manuscript is maintained in [`latex_report/main.tex`](../latex_report/main.tex). This file records the current evidence summary to accompany the implementation and sealed results.

## Research question

At a declared application-performance budget, how do in-probe sampling and changing detailed tracepoint attachment state affect short-incident visibility and the overhead--capture trade-off?

## Implemented system

The Linux system combines a low-cost `sched_switch` sentinel with raw syscall entry/exit detail collection. The C/libbpf agent filters target tasks and allowlisted syscalls, applies sampling thresholds, maintains selected-call state across entry/exit, consumes a bounded ring buffer, and records separate loss counters. The detector/control path supports LOW/MEDIUM/HIGH modes, GATE and SWITCH mechanisms, dwell and hysteretic recovery, and a declared 5% application-throughput-loss budget. Python orchestrates immutable trials and paired analysis.

## Linux evidence

The recorded host is Ubuntu 26.04 LTS x86-64, kernel `7.0.0-31-generic`. The privileged known-count smoke passed: the high-detail case selected, completed, emitted, consumed, and wrote 2,000 records, with no ring or sink drops; low and sentinel-only checks also passed.

The saved pilot (`data/pilot/bounded-q01-4blocks-20261114-001/`) consists of four paired blocks for each of CPU and I/O workloads, comparing NONE with fixed 1% sampling (FIX_Q01). It contains 16 valid attempts; each carries the external-CPU noise warning. Paired throughput-loss estimates were 1.85% for CPU (95% interval −0.63% to 5.60%) and 11.21% for I/O (10.85% to 11.46%). Common-cutoff incident capture was 1.17% (1.02% to 1.35%) and 1.00% (0.88% to 1.16%), respectively. On-time detector alert recall was zero in both. The runner marks the 5% budget outcome inconclusive because the sample is below its eight-block threshold.

These are actual pilot observations, not synthetic fixtures. Because the pilot contains no ADAPT_GATE or ADAPT_SWITCH runs and all blocks are noise-flagged, it does not establish an adaptive advantage or confirmatory budget compliance. The numerical source is `results/pilot/bounded-q01-4blocks-20261114-001/results.json`; the corresponding claim/evidence map is `paper/claim_evidence.csv`.

## Related work and contribution boundary

SMCO and QVM establish prior work on overhead-managed monitoring; Magnani et al. study adaptive eBPF network telemetry; Naas et al. analyze eBPF tracing component overhead; Hindsight studies retroactive distributed tracing. This project makes no first-system or first-budget claim. Its report presents the Linux implementation and evidence-bounded syscall/scheduler pilot.
