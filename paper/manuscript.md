# Adaptive eBPF Telemetry with an Explicit Overhead Budget

## Question and scope

At a declared application-performance budget, how does in-probe gating versus changing detail attachment state affect short-incident visibility and the overhead–capture frontier?
The deliverable is an empirical systems study. Adaptation, sampling, overhead budgets and loss accounting have prior art; this implementation makes no first-system claim.

## Implementation and methods

The Linux implementation uses C/libbpf CO-RE programs, C workload/collector/controller processes, and Python orchestration and analysis. The target ABI is x86-64 little endian. Real builds derive vmlinux.h from the target kernel BTF and generate skeletons from compiled BPF objects.

A scheduler-switch sentinel counts target involvement once per switch in 2,048 per-CPU rotating 5 ms bins. Completed bins are read with a 10 ms safety lag. Old generations indicate zero in a timely closed bin; newer generations, torn snapshots and retention overruns indicate sensor gaps. The target set is frozen before warmup.

Detailed raw syscall tracepoints select pread64, futex, sched_yield and clock_nanosleep at entry. LOW selects none, MEDIUM selects 0.10, and HIGH selects all eligible entries. Exits complete the original selection even if the sampling mode has changed. Each fixed 64-byte record is wrapped with its collector receipt timestamp in a block-checksummed 72-byte transport stride. Native PRNG draws are not replayable from workload seeds.

GATE leaves both detail hooks attached. SWITCH attaches exit then entry with selection disabled before publishing a naturally aligned 64-bit generation/threshold word. On LOW, SWITCH disables selection, removes entry, drains exits at 1 ms intervals for at most 20 ms, then removes exit and classifies remaining entries. GATE's corresponding late completions remain real completions and receive a separate offline common-cutoff tag. Real atomic publication, detach quiescence and exact-count race behavior require target-kernel verification.

The collector consumes readiness events with epoll, receives control ticks through timerfd and handles shutdown through signalfd. A bounded queue feeds a dedicated binary writer. Queue saturation, ring reservation failure and final undrained records have separate counters. Staging is preallocated in tmpfs with a per-trial cap of min(1 GiB,20% RAM); actual 72-byte stride, frame overhead and 20% headroom are included. Compression and checksum restoration happen after measurement.

The detector uses the maximum robust log1p switch-count deviation among newly closed valid bins. Its median, MAD scale (floor 0.10), threshold and context/action cost UCLs must come from independent normal/calibration data. Adaptive modes begin LOW. Recovery requires 500 ms quiet and dwell is 250 ms unless the relevant ablation changes it. Gaps request LOW and prevent positive recovery evidence. The optional supervisor uses past sentinel rate and application-core utilization; it does not observe truth, schedule labels, future drift or throughput counters.

W-CPU runs two deterministic checksum-producing batch workers. W-IO uses explicit pread64 calls over a prefaulted 64 MiB tmpfs working set per worker. Drift doubles CPU repeats or changes reads from 4 KiB to 16 KiB. Per-read compute batches are fixed before final experiments. The incident engine pre-creates bounded-timeout futex helpers and an unseen CPU-contention helper. Truth includes intended and actual boundaries and per-role invocation totals, without per-event primary logs.

## Protocol and inference

The primary design has seven policies, two application families, two background levels, and drift absent/present: 56 cells, initially 12 randomized paired blocks per scenario (672 trials). Default timing is 30 s warmup,240 s measured,up to 5 s drain and at least 15 s cooldown. A block pairs the entire schedule/input seed across policies. All supplementary comparisons own explicit matched controls; runtime/storage estimates include these extra controls. Independent hosts and stats-on attribution remain separate populations.

Primary application impact is 1-exp(mean(log(Qpolicy/QNONE))) over paired blocks, separately per drift phase. Whole blocks are bootstrapped 10,000 times. Compliance at B=5% uses one-sided 95% limits and is compliant,violating or inconclusive. Negative estimated overhead is retained. Arithmetic ratio-of-means is secondary. Sparse calibration contexts use worst training UCLs; unidentifiable transition cost is flagged rather than converted to fictitious throughput loss.

Cumulative application samples are interpolated at phase boundaries; the maximum bracket interval is retained as measurement resolution. This interpolation's perturbation and error must be quantified in calibration before fine-grained overhead claims. Optional duration histograms describe benchmark work units,not service request latency.

Detection uses chronological one-to-one alert matching within actual incident onset through end+1 s. On-time recall is reported separately. Preexisting alerts are not new detections. Capture is received correct helper pairs divided by independent helper invocations; useful capture thresholds are one and ten pairs completed during the incident. Zero-call CPU incidents have N/A capture. Missing delays remain misses/right-censored,with success fractions beside conditional distributions.

## Results and scientific decision

No empirical result set is available. No kernel attachment, overhead, detection advantage, budget compliance, host generalization or publication-ready novelty has been demonstrated. See the phase gates and exact host handoff in artifact/REPRODUCE.md.

## Threats, skeptical review and limitations

Low trace volume can result from sampling or loss; report both alongside source-call denominators. Adaptive performance must be compared with the full fixed sampling frontier and trigger-only variants. The shared sentinel can change because tracing perturbs scheduling. Identical detector code does not imply identical live inputs. Offline replay is diagnostic only.

Changing attachment does not eliminate the always-on scheduler sentinel. Collector CPU does not include all BPF CPU executed in target context. The shared placement charges observer competition to the workload; isolated placement reserves its extra core even for NONE. A single VM cannot establish bare-metal or cross-host effects. No hard instantaneous overhead guarantee,root-cause diagnosis or distributed tracing result is claimed.

Short-incident duration,overshoot,late starts and helper call totals must be validated on real Linux. Workload and controller source code alone is not evidence of correctness. Missing literature full-text access and the unavailable v4 novelty review limit the prior-art audit. Unfinished supplementary cells limit corresponding conclusions.

## Reproducibility

See artifact/REPRODUCE.md for setup,smoke,calibration,freeze,core subset,full matrix and archived-data analysis. Every attempt is immutable after seal.json; invalid attempts and at most two infrastructure retries are retained. The first valid attempt is analyzed. Kernel reserve failures,slowdown,misses and infeasible predictions are outcomes,not invalidation reasons.

## Closest work and references

SMCO and QVM already study overhead-aware monitoring; Magnani et al. already provide adaptive eBPF network telemetry. Hindsight supplies retroactive distributed tracing,whereas this ring buffer is a transport and retains no pre-incident overwrite history. The nine-source access matrix in research/evidence_access.csv distinguishes full-text review,metadata access and unresolved sources. paper/references.bib preserves verified and pending bibliographic records separately.
