# Implementation plan — Adaptive eBPF Telemetry with an Explicit Overhead Budget

**Version:** 1.0  
**Date:** 30 October 2026  
**Execution model:** autonomous implementation agent, evidence-backed phase gates  
**Current state:** plan only; no implementation, pilot results, or validated novelty claim  
**Primary output:** a reproducible empirical systems study, its software/data artifact, and a paper-style report

## 1. Project contract

Build and evaluate a stock-Linux eBPF telemetry pipeline with low, medium and high collection modes. Compare leaving detailed probes attached and sampling inside them against attaching/removing detailed probes as the controller changes mode. Use identical event definitions, sentinel, workload schedules, detector and collector wherever the mechanism permits. Measure application overhead, short-incident detection, detail capture, loss and switching delay together.

The research question is:

> At a declared application-performance budget, how does the mechanism used to reduce eBPF collection change short-incident visibility and the observed overhead–capture frontier as event rate and workload intensity change?

The contribution sought is a reproducible empirical finding or operating boundary. Do not claim a novel sampling mechanism, first adaptive eBPF controller, first overhead budget, first hook-cost floor, or first loss/overhead trade-off. Those have substantial prior art. A negative or null result is a valid project outcome. Publication and empirical novelty remain conditional on evidence.

### 1.1 Source precedence

1. This user-approved task: create a complete implementation and research-evaluation plan.
2. `eBPF_OS_Assignment_4_Resource-Aware_eBPF_Observability.docx` — mandatory coursework requirements.
3. `novelty_review_v4.md` — current research boundary; supersedes contradictory preliminary novelty claims.
4. `novelty_review_v3.md`, the initial literature review, and `adaptive_ebpf_research.zip` — historical context and leads.
5. Official kernel/libbpf documentation and the actual target kernel's feature probes — implementation facts.

Copy these source documents into `context/` when establishing the repository, with hashes and retrieval dates. Preserve originals. Do not depend on chat history as an undocumented specification.

### 1.2 Explicit exclusions

No ML/RL, custom scheduler, kernel patches, GPU, distributed tracing platform, production deployment, dashboard, remote payload collection, or guaranteed overhead bound is required. Do not reproduce every related system. Do not build an eBPF overwrite flight recorder; the baseline BPF ring buffer is a transport. Do not add system features unless needed to answer the stated question.

### 1.3 Research hypotheses

| ID | Falsifiable hypothesis | Primary test |
|---|---|---|
| H1 | Adaptive collection achieves a better application-impact/detail-capture trade-off than at least one fixed configuration. | Adaptive versus fixed-low/medium/high; also show the full fixed sampling curve, not only fixed-high. |
| H2 | In-probe sampling and changing attachment state yield different cost–capture frontiers in some tested conditions. | Same detector, sampling probabilities, payload and workloads; compare measured impact and episode capture with CIs. |
| H3 | A cost proxy calibrated in one regime has measurable prediction error after workload/event-rate changes. | Frozen calibration versus independently measured treatment effects in held-out phases. |
| H4 | Hysteresis and dwell reduce switching, potentially increasing detail-ready delay. | Required separate ablations removing each feature. |

H2 does not assert a winner or universal effect. H3 is not a new discovery merely because a proxy is imperfect. Report where differences are below experimental resolution. Successful coursework implementation does not imply a publishable contribution.

## 2. Autonomous execution rules

The implementing agent owns the full sequence below. Start with Phase 0; do not jump to paper figures before data validation.

- Work in a version-controlled repository. Preserve existing files and inspect local instructions first. Use branches or isolated worktrees if required by that repository.
- Maintain `PROGRESS.md`, `state/progress.json`, `DECISIONS.md`, `ISSUES.md`, and `NEXT.md`. Give every step below a stable ID and one of `todo`, `doing`, `blocked`, `done`, `skipped-with-reason`.
- Each completed step records commit, commands/checks, output paths, evidence hash, date and limitations. Mark a phase done only when its gate passes.
- Resume by reading those files and verifying the referenced artifacts. An interrupted process or old success message is not proof of completion.
- Execute independent code tasks in parallel only if the execution environment/user permits delegation. Never run competing performance experiments concurrently on the same host. One host lock covers calibration, measurements and background generators.
- Keep user-facing progress updates concise and report findings, failures and the next gate. Long experiment batches must provide live progress without blocking communication.
- Technical dependencies unavailable locally: implement and verify unprivileged components first; produce exact reproducible host commands and diagnostics. Do not fabricate successful eBPF attachment or benchmark runs. Explicitly mark kernel-dependent phases blocked until a capable authorized host exists.
- Ordinary implementation choices covered here require no additional clarification. Record deviations. Pause only for a missing fact/access that truly blocks dependent work, destructive changes, or explicit external approval requirements.
- Do not install onto an existing public/demo server or modify its boot/kernel/security policies without authorization. No paid VM creation, messages to others, public publication, or deployment is implied by this plan.
- Every experiment attempt is immutable. New attempts get new IDs. Never overwrite failed raw results or silently repair a completed run. A bug fix affecting measurement creates a new protocol/code version and reruns affected conditions.
- Simulation/unit-test outputs live under `data/synthetic/` with `synthetic=true`. They never appear as real kernel or application evidence.

### 2.1 Completion record

`state/progress.json` contains `schema_version`, `protocol_version`, `source_commit`, `updated_at`, `current_phase`, and a `steps` mapping. Each step has `status`, `depends_on`, `artifacts`, `checks`, `blocker`, `started_at`, `finished_at`. `NEXT.md` gives one exact next command plus expected output. `DECISIONS.md` records choice, alternatives, evidence and effect on comparability. A command failure must be visible in `ISSUES.md` until resolved or accepted as a limitation.

## 3. Repository and implementation architecture

Use C for BPF, workload generators and the collector/controller; Python for orchestration, schemas, statistical analysis and plotting. This avoids Python scheduling/GC differences in the timing-sensitive collector. Use libbpf with CO-RE where appropriate, generated skeletons, Clang/LLVM and bpftool. Use standard tracepoints initially; do not silently change hook types between compared policies.

| Path | Responsibility |
|---|---|
| `context/` | Assignment and research sources, source manifest. |
| `research/` | Citation matrix, hypotheses, claim ledger and access limitations. |
| `src/bpf/sentinel.bpf.c` | Scheduler sentinel; identical across instrumented policies. |
| `src/bpf/detail.bpf.c` | Paired raw-syscall detail tracing with entry sampling. |
| `src/common/` | Versioned event structs, config and IPC schemas. |
| `src/agent/` | Loader, link lifecycle, ring consumer, detector and controller. |
| `src/workloads/` | CPU and cached-I/O benchmarks, futex incident generator and CPU-contention helper. |
| `runner/` | Host discovery, manifests, trials, randomization, cleanup, resume. |
| `analysis/` | Accounting, metrics, CI calculations, figures and paper tables. |
| `configs/` | Base, calibration, pilots, confirmatory and robustness YAML files. |
| `schemas/` | JSON Schemas for manifests, trials, counters, incidents and results. |
| `tests/` | Meaningful unit/integration/privileged correctness tests. |
| `data/{synthetic,calibration,pilot,confirmatory,robustness}/` | Strictly separated data populations. |
| `results/<protocol-version>/` | Derived tables and figures; raw inputs referenced by hash. |
| `paper/` | Manuscript, bibliography, claim-to-evidence table and limitations. |
| `artifact/` | Reproduction instructions, environment locks, manifests and release bundle. |

Expose these stable commands through a `Makefile` and a Python CLI `python -m runner`:

`doctor`, `build`, `test --unprivileged`, `test --privileged`, `calibrate`, `pilot`, `freeze`, `estimate-matrix`, `run`, `validate`, `analyze`, `report`, `status`, `cleanup`, `package`. Support `--config`, `--output`, `--dry-run`, `--resume` and `--seed` where meaningful. No default command should start an expensive full experiment campaign.

The privileged agent is a child process for each trial. It creates and owns only that trial's BPF objects/links. Do not pin maps/links by default; closing owned FDs must remove instrumentation after crash. Runner starts target workers, creates target membership, loads the agent, performs readiness barriers, starts the timed epoch, stops workers, drains outputs and captures cleanup evidence.

## 4. Experimental hosts and environment

### 4.1 Required primary host

Prefer an otherwise idle x86-64 bare-metal Linux host with at least four physical cores, 8 GB RAM, initially at least 100 GB free disk and enough capacity for the full estimated campaign/archive plus 20% headroom, cgroup v2, readable kernel BTF, and permission to load tracing BPF. Target Ubuntu 24.04 LTS with a supported Linux 6.8-or-newer kernel; use the *actual* kernel build, not this version string as proof of support. Pin the exact tested kernel/toolchain/libbpf revisions after feature discovery. Do not automatically replace a machine's kernel.

Required checks: BPF syscall and tracing support; working `sched:sched_switch` and `raw_syscalls:sys_enter/sys_exit`; ring-buffer map; required map/helper support; libbpf load, attach, receive and detach smoke test; cgroup/affinity permissions. Privileged tracing can require root or an appropriate capability set subject to kernel policy. Detect lockdown, permissions and container restrictions rather than recommending disabling protections.

A Linux VM is a functional fallback. Record hypervisor, vCPU topology, steal time and contention. WSL is a development target only if its actual kernel passes the same checks; do not infer that a working shell implies BPF support. Conclusions from one VM remain explicitly limited. CPU time/fine-grained overhead claims require a suitable host.

### 4.2 Placement

Discover physical-core and SMT topology. Choose four distinct physical cores where possible: `C0` runner/system coordination; `C1,C2` target workload and injected competing load; `C3` independent measurement/logging helper. **Primary shared-observer placement:** agent/collector/controller shares `{C1,C2}` with the application. **Isolation robustness placement:** agent on `C3`, with that core reserved in *all* conditions including no telemetry; explicitly report the extra reserved core.

Do not change scheduling priority between treatments. Disable neither SMT nor turbo silently. Prefer a stable documented governor if permitted; record the original setting and restore any changes. Record topology, governor, frequency/thermal telemetry, CPU pressure, background processes, time source, NTP state, swap and memory pressure. Avoid changing page-cache state in the primary cached-I/O experiment. Background processes not owned by the trial must not be killed.

Primary host gets the full core study. A second independent host/kernel runs a specified replication subset before cross-machine claims. If unavailable, finish the single-host artifact and report the limitation without inventing replication.

### 4.3 Fixed execution settings

- Base control period `P=100 ms`; sensitivity `25, 100, 500 ms`.
- Sentinel bin width `b=5 ms`, 2,048 rotating bins (10.24 seconds of history); bin-close safety lag `2b=10 ms`.
- Default detailed ring buffer `8 MiB`; stress capacities `256 KiB` and `32 MiB`. Verify allocation on target; actual bytes logged.
- Detail inflight map: bounded hash, 8,192 entries; target thread map: 128 entries. Do not use LRU eviction for inflight correlation.
- Trial: 30 s warmup, 240 s measured epoch, up to 5 s final output drain, 15 s cooldown minimum. Readiness/start/stop actual timestamps mandatory.
- Store all source/runtime times in monotonic nanoseconds (`CLOCK_MONOTONIC` aligned with `bpf_ktime_get_ns`); wall time is metadata only. Verify clock correspondence experimentally. Do not substitute `MONOTONIC_RAW` in one component.
- Collector uses epoll/ring-buffer readiness, timerfd for ticks, signalfd or equivalent structured shutdown. No busy-poll loop in the primary configuration. Keep sink behavior identical across policies.
- Benchmark no BPF runtime statistics in primary runs. Dedicated attribution runs may enable `BPF_ENABLE_STATS`; these are intrusive measurements and must not be pooled with primary runs.

## 5. Workloads, incidents and independent truth

### 5.1 Two mandatory application families

**W-CPU:** two stable benchmark worker threads, one on C1 and one on C2, continuously perform a fixed deterministic integer/hash operation over a private buffer. One work unit has a fixed input size and repeat count, and produces a checksum so optimization cannot remove work. Work-unit size is selected once in calibration for a unit duration in the approximate 20–100 microsecond range, then frozen. Count completed units in thread-local counters and publish aggregate increments to shared memory every 100 ms; do not log every unit or call a tracing API. No timing adaptation inside a measured run.

**W-IO:** two stable workers repeatedly issue direct `syscall(SYS_pread64, ...)` calls for 4 KiB reads from pre-created, prefaulted files on tmpfs, with deterministic per-worker offset sequences in a 64 MiB working set. One successful 4 KiB read plus its frozen deterministic compute batch is one unit. Calibration may select a batch solely to keep the primary eligible-entry rate and raw output within the declared storage guard (§11 P5.1); save the batch, checksum and achieved rate, and never pace based on tracing mode. Track attempted, successful, short and failed reads. Primary tests deliberately study the cached/VFS/syscall path, not physical storage. File generation/first touch is outside the measured epoch. Do not use O_DIRECT on tmpfs. A real-file/device workload is an explicitly separate optional extension.

Both families run at maximum offered local work: an always-busy benchmark, not a lightly loaded service whose throughput is fixed by its client. That makes completed work per second a meaningful application-throughput metric. No request-latency or external offered-load claims follow from these batch-style workloads. Work-unit duration may be sampled sparsely into a preallocated local histogram at the same fixed rate in *all* conditions; validate measurement cost before use. External-service p99 is out of scope unless Phase 9 adds a separately specified server experiment.

All worker/helper TIDs are created and registered before warmup through a barrier. Target membership includes the application and incident helper TIDs; no churn during a main trial. Keep membership and filters identical across comparable treatments. Record logical thread roles independent of recycled PID values. Unexpected thread exit/replacement invalidates a performance trial.

### 5.2 Primary incident: controlled scheduling/syscall burst

Pre-create two helper threads pinned to C1. During an incident they perform a timeout-bounded `FUTEX_WAIT_PRIVATE`/`FUTEX_WAKE_PRIVATE` ping-pong on a shared word. Outside incidents they park. Every explicit futex invocation is counted locally by role and episode. Use at most 1 ms wait timeout and a stop flag so incidents can finish and cleanup cannot deadlock. Aggregate counters and actual first-call/last-return times are written once after each episode, without a per-event log in primary runs. Capture checksum/handshake correctness and interrupted/error returns.

Nominal durations `D={10,25,50,100,250,500,1000} ms`. These are requested durations, not assumed achieved durations. The episode lasts from the first helper's start barrier to both helpers' last active-call return; report actual duration, overshoot and per-helper call totals. An incident is a labeled injection, not proof of a user-visible fault. Report its effect on benchmark throughput separately. Zero-call or malformed episodes are generation failures, not missed detections.

**Independent truth:** episode ID, nominal and actual start/end, logical helper roles/TIDs, explicit syscall attempt totals, run/seed and intensity. The controller cannot read this file, schedule, stop flag, workload completion counters or phase labels. It sees only the sensors specified below. For detail-capture denominators, use explicit allowlisted helper invocations bracketed by the actual episode window; correctness tests establish that counts correspond to kernel entries. Primary performance runs use totals, not exhaustive ground-truth tracing. Boundary ambiguous calls must be counted/flagged rather than silently assigned.

### 5.3 Secondary incident and benign drift

**CPU contention:** an additional pre-created helper on C1 performs deterministic arithmetic for 25,100,500,1000 ms, with actual timestamps. It may lower rather than raise switch rate, and can be invisible to the chosen event set. This is a required held-out failure/generalization test; do not retune the detector on its confirmatory results. There may be zero diagnostic syscalls; use N/A rather than a fabricated capture denominator.

**Benign workload drift:** at the start of the second half of the measured epoch (120 s), change the application to a prespecified alternate workload intensity: W-CPU doubles per-unit compute repeats; W-IO changes reads from 4 KiB to 16 KiB while retaining the same byte working set. Compare within each phase to a matched no-telemetry phase; work-unit throughput before and after is not directly interchangeable. This is an expected benign change: report any resulting alerts as benign-change false alarms, separately from quiet-period false alarms. Policy does not get the drift label. The trigger reference is frozen within a trial; do not accidentally train away the drift during final testing.

### 5.4 Episode schedules

Each 240 s measured epoch has fourteen incident slots with anchor times `15+15j` seconds for `j=0..13`. Add seeded uniform jitter in `[-2,+2]` seconds. Assign each duration once among slots 0..6 and once among slots 7..13 using independent seeded shuffles. Thus each duration appears in each workload phase. Do not overlap incidents. If the OS delays an episode so it would overlap the next, log it as a generation failure and invalidate the run for timing analysis; do not quietly compress it. Save intended schedule before the run, actual schedule afterward. Entire logical schedules and workload input seeds are paired across policies; scheduling itself and kernel PRNG draws are not assumed identical.

Background levels: primary low = no additional helper outside incident periods; high = an owned non-target arithmetic helper consumes a pre-calibrated 50% duty cycle on C2, with fixed period 10 ms. Its PID/TID is excluded from event membership but it can affect application scheduling. Record achieved CPU time; it is part of workload context, not observer cost. Main drift/no-drift conditions remain distinct.

## 6. Telemetry semantics and accounting

### 6.1 Always-on sentinel

Attach a separate BPF tracepoint program at `sched:sched_switch` for every instrumented policy. Count a switch once if either previous or next TID belongs to the frozen target set. No stack walks, task payloads, or dynamic strings. Store counts in a per-CPU rotating array keyed by `floor(monotonic_ns/b) mod 2048`; each value contains generation/epoch and count. Also maintain cumulative per-CPU totals.

The controller reads only *completed* bins ending at least 10 ms before the tick, checks the generation and never destructively resets an active bin. Remember last processed absolute bin to avoid double consumption. A read delayed past retention or with a generation **newer** than requested, or an unreadable bin, becomes a `sentinel_gap`, not zero activity. For a timely, fully closed bin whose stored generation is **older** than requested, infer zero: no event visited that slot in this generation. Initialize empty generations consistently at startup. This distinction prevents idle intervals from becoming artificial sensor gaps. Validate concurrent read/write and wraparound on the target. Per-CPU bin memory is proportional to possible CPUs; record actual allocation. This sentinel is intentionally on a different event family from syscall details: removing syscall probes cannot be claimed to remove scheduler-sentinel cost.

A 100 ms total alone can hide a 10 ms burst; the detector receives the completed 5 ms bin sequence and can raise an alert on any bin. Detection is still delayed by polling, safety lag and scheduling. A burst can finish before alert or detail activation. Preserve and show that outcome.

### 6.2 Detailed event stream

Use standard `raw_syscalls:sys_enter` and `raw_syscalls:sys_exit` tracepoints, target-TID filter, and a fixed allowlist generated for the host architecture: `pread64`, `futex`, `sched_yield`, `clock_nanosleep`. Record syscall numeric/name mapping and ABI; unsupported architectures fail discovery instead of using x86 IDs. Main performance/event comparisons use exactly the same allowlist. No syscall argument payloads, buffers, paths, credentials or stacks are collected.

At each eligible entry: increment eligible-entry counter; draw one sampling decision with probability q; for selected calls insert `{entry_ns, syscall_id, generation, entry_cpu, sequence}` into the inflight map keyed by TID. Hash insertion failure is counted. At exit: first apply the fixed allowlist/membership rules, then look up/delete any selected inflight entry regardless of the *current* mode; validate matching syscall identity; increment completion; reserve/output exactly one fixed-size record. Sample at entry, never independently at exit. Maintain counters for rejected sampling, insert failure, overwritten/restarted entries, exit-without-selected-entry (expected for unsampled calls), truly malformed pair, pending and forced-abandoned entries, reserve failure and emitted records. Do not equate unmatched exits with dropped selected events.

Publish sampling threshold and generation as one aligned 64-bit configuration word (low 32 bits unsigned threshold, high 32 bits generation), with atomic user-space publication through a supported mapped libbpf global/config path and one consistent BPF read. Threshold 0 means none, UINT32_MAX is an explicit sample-all branch, and intermediate q uses the exact documented integer threshold. Verify generated code/load atomicity on the chosen architecture; otherwise use a supported map-based snapshot publication scheme and measure its cost equally in both policies. Do not assume a multi-field map update is an atomic transaction. Record the effective threshold and generation.

Wire format: fixed 64 bytes, explicit schema version/flags, mode-generation, entry/exit monotonic ns, TGID/TID, syscall ID, entry/exit CPU, signed return value, per-thread selected sequence and attachment epoch. Assert offsets/size in C and Python; endianness recorded. The collector obtains run identity from the file envelope. Sequence numbers are for accounting, not deterministic source-event identity across policies.

Use the kernel PRNG or a verified lightweight implementation for sampling. Main workload seeds are replayable; native BPF PRNG draws are not reproducible from those seeds. Do not promise byte-identical telemetry across runs. Validate sampling frequency statistically in dedicated tests and repeat independent trials. Sampling cost is part of measured overhead. Live tracing can itself change the sentinel signal and subsequent policy decisions; matching detector code is not evidence of identical live input. Preserve observed differences and use offline replay only as a diagnostic, not a substitute for live measurements.

### 6.3 Collection modes and mechanisms

| Mode | Sentinel | Detailed entry probability q | Meaning |
|---|---|---:|---|
| LOW | Always active | 0 | Detection from sentinel only; no newly selected detailed syscalls. |
| MEDIUM | Always active | 0.10 | Sample completed syscall pairs. |
| HIGH | Always active | 1.00 | Attempt every eligible pair; delivery can still fail. |

**GATE:** entry/exit detail programs remain attached in all modes. Entry returns without state insertion at q=0. Exit still checks/cleans selected calls that entered earlier; no unsafe “LOW means ignore all exits” optimization. Costs of hooks, TID filtering, config checks and exit lookup remain.

**SWITCH:** detail programs are precompiled, loaded and verified before warmup; LOW has neither attached. Activation attaches exit first, then entry while new selection is disabled, then publishes one versioned config enabling q. Record syscall timings and publish-ack time. If either attachment fails, disable new entries, destroy owned partial links, mark failure, and terminate the performance trial. There is no atomic two-link attachment guarantee.

When entering LOW: disable new entry selection, detach entry, leave exit up to 20 ms to drain inflight entries (check at 1 ms via nonblocking state machine), then detach exit and classify any remaining entries as forced-abandoned at the boundary; clear only after no new handlers can add entries. MEDIUM↔HIGH changes q without detaching. Re-entry while draining queues one latest desired state, without duplicate entry attachment. Report drain cost and boundary censorship. Keep detector ticks and ring consumption active during transitions. Test long/blocking syscalls and signal/restart paths.

For GATE use the same 20 ms analytic cutoff when LOW is requested, but leave programs attached and keep normal inflight completion accounting. A pair from before the LOW boundary that finishes after the cutoff is marked boundary-censored **offline** and excluded from the common-cutoff capture metric, while its real completion and transport counters remain intact. Do not count such a pair as both physically abandoned and completed. Also show the uncensored GATE result; imposing a common cutoff is a fairness sensitivity, not grounds to hide a real capability. SWITCH alone physically abandons remaining entries after removing detail hooks. Any deletion/handler race must reconcile in a stress test; if quiescence cannot be established, the run cannot claim exact accounting.

Track four times separately: desired state, action start, action acknowledged, first usable detail event. An acknowledgment is not proof an incident event was captured. Record current attachment state, sampling probability and generation at every tick.

### 6.4 Ledger and transport

At run end verify selected-entry accounting: every selected entry is pending, completed, insert-failed or explicitly abandoned/replaced under a documented nonoverlapping classification. Analytic boundary-censoring tags overlap these terminal classes and are never added to that balance. After workers park at a stop barrier and owned hooks detach, drain and take stable final snapshots before freezing the ledger; preserve late completions and retries rather than treating an initial nonquiescent counter read as final. Completed export attempts equal successful emissions plus reserve failures. Emissions equal collector-consumed records plus known undrained records at final cutoff, subject to versioned reconciliation. Any unexplained discrepancy invalidates fidelity metrics. q=0 has no selected-entry denominator.

BPF ring-buffer reserve failure is explicit producer-side loss. It is not an overwrite history. The collector writes fixed binary records through a preallocated bounded queue to an identical buffered binary sink. No JSON formatting per event, printing, fsync per record or silent downsampling. If the user-space queue fills, count `sink_drop`; primary configuration is intended to avoid it, stress runs deliberately expose it. Save bytes, throughput and flush timings. Primary logging goes to a preallocated tmpfs staging file with a cap of `min(1 GiB, 20% of host RAM)` per trial, using a full-run worst-case prediction from calibration plus 20% headroom. If the planned rate does not fit, fail the preflight and make a documented calibration/protocol adjustment before freeze; never silently truncate. Overload tests use a separately declared file-backed sink if needed, with matched controls. Hash and losslessly compress outside measurement; verify the archive restores the raw checksum before deleting the redundant uncompressed staging copy. Archives remain immutable. Host memory checks prevent OOM; unavailable archive capacity is a real blocker. Record the map allocation, queue, sink and archive sizes separately.

For diagnostic sampling curves add q in `{0,0.01,0.10,0.50,1}` without changing event semantics; these are extra fixed configurations, not extra core controller modes.

## 7. Detector, controller and budget interpretation

### 7.1 Detector

Compute per-bin robust standardized switch-count deviations against a **frozen training baseline** for each declared workload deployment. Let `x=log1p(bin_count)`, baseline median `m`, scale `s=max(1.4826*MAD,0.10)`, and `z=abs(x-m)/s`. Score for a tick is the maximum z among newly closed valid bins. This two-sided score can detect abnormal decreases as well as increases; it is not a universal detector. Zero counts are legitimate only for validated bins, never for gaps. Baseline training uses separate normal calibration runs; implementation never reads episode times or confirms labels online.

Default high threshold `h=6`; medium threshold `h/2`; recovery threshold `h/4`. In calibration, evaluate `h∈{4,6,8,12}` and choose the smallest achieving at most one alert episode/minute on held-out *normal training validation* data; if none meets that threshold, use 12 and explicitly report the unmet detector target. Use a minimum 10 minutes normal data per workload/background calibration level. Do not tune on final incident recall. Each workload family may have its own baseline, but GATE and SWITCH must use the exact same frozen baseline/threshold. Baseline selection is a deployment setting, not a hidden ground-truth signal.

Tick handling: `score>=h` requests HIGH; otherwise `score>=h/2` requests MEDIUM. Five consecutive complete quiet ticks below `h/4` allow one step down at the default P=100 ms. In period sensitivity runs use `ceil(500 ms/P)` quiet ticks, so the recovery requirement remains 500 ms. Values in between hold state and reset the quiet counter. Dwell default 250 ms between any successful mode changes; requests wait until dwell expires. Budget-driven reduction overrides dwell and is logged. Alert state is independent: begin an alert episode when `score>=h`, close after five quiet ticks, and assign alerts to incidents only offline. Starting the controller in LOW for all adaptive treatments ensures comparable initial state. A sentinel gap causes `sensor_uncertain`, prohibits new positive evidence of recovery, and requests LOW for cost containment; report the gap and recovery delay.

### 7.2 Primary application budget

Primary budget `B=5%` relative **completed-work throughput loss** against matched no-telemetry runs for the *same workload phase, background and schedule*:

`L=1 - Q_policy/Q_NONE`, where `Q` counts successful work units per measured second.

Estimate effects from repeated randomized blocks, using a paired log-ratio analysis as specified below. The confirmatory aggregate effect is the geometric mean of block-paired throughput ratios, converted to loss (§9.3); report arithmetic ratio-of-means as a secondary sensitivity and do not conflate them. Each phase's throughput has its own reference; do not compare different unit sizes. Throughput is saturating local benchmark throughput, not offered request throughput. Keep negative overhead estimates rather than clipping them in tables. Report whole-epoch and phase-level effects; no instantaneous overhead “ground truth” exists.

Classify final **measured phase-level compliance** from a one-sided 95% upper confidence limit: `compliant` if UCL<=B, `violating` if the corresponding lower limit>B, otherwise `inconclusive`. These are effect-estimation statements, not a proof of a live per-window guarantee. Also show point estimates and two-sided 95% CIs. Sensitivity budgets `2%,5%,10%` are preregistered separate controller configurations.

### 7.3 Online cost supervisor

The controller cannot know true relative throughput loss on a changing workload. Do not feed no-telemetry references, truth labels or future phase information into it. Use an explicitly limited **offline-calibrated context/action table** as a deployable prediction baseline, shared in structure by both mechanisms:

1. Calibration collects each mode/action at stable and shifted training regimes, including total observer costs, actual application impact and sentinel score/count distribution. Build three sentinel-rate bands from pooled training tertiles; also record utilization bands `<50%,50–80%,>80%` for the designated application CPU mask from per-CPU `/proc/stat` counters at 100 ms. These are context proxies, not independent truth.
2. For each mechanism × mode × context cell, store measured throughput-loss estimate plus its one-sided 95% UCL from independent calibration replicates. Empty/underpowered cells use the mechanism/mode's worst available training UCL. Do not extrapolate an unobserved cell to zero cost.
3. At a tick, select the detector-requested mode or the highest lower mode with predicted UCL<=B. If none qualifies, choose LOW and log `budget_infeasible_prediction`. LOW still has sentinel and controller cost and is not a zero-overhead guarantee. Record requested/allowed/applied modes and predicted cost every tick.
4. Calibration of attach/detach actions additionally records transition CPU/time. Charge a conservative transition-cost entry over a declared 1 s prediction horizon; sparse context uses the training worst case. If application-cost conversion is not statistically identifiable, retain the action cost as a separate metric and flag `transition_cost_unresolved`; do not fabricate a throughput percentage.
5. Context data is causal and past-only. CPU-utilization readings and cost-table accesses are identical across adaptive mechanisms. Table contents can differ because measured action costs differ. Re-evaluate frozen models offline on held-out drift to quantify error; do not retrain them during confirmatory trials.

This is a best-effort budget-targeting policy. It is not a new controller or SMCO reproduction, and does not enforce a hard CPU or application budget. The important evidence is observed compliance/failure, capture and model error. Include the detector-only version without this supervisor as a separate baseline to measure its contribution. If the table is too inaccurate or too coarse, report that as H3's result; do not redesign it on the final dataset.

### 7.4 Fixed/adaptive baseline registry

| Policy ID | Sentinel | Detail lifecycle | q/controller |
|---|---|---|---|
| `NONE` | No | No programs loaded/attached | Benchmark and external measurement only. |
| `SENT` | Yes | No detail probes | Same agent loop, detector and sink envelope, no mode actions. Static SWITCH-LOW. |
| `FIX_LOW_GATE` | Yes | Both detail probes always attached | q=0; fixed LOW. |
| `FIX_MED` | Yes | Both always attached | q=0.10, fixed MEDIUM. |
| `FIX_HIGH` | Yes | Both always attached | q=1, fixed HIGH. |
| `ADAPT_GATE` | Yes | GATE | Common detector + cost supervisor + dwell/hysteresis. |
| `ADAPT_SWITCH` | Yes | SWITCH | Same logic, action-specific calibration costs. |
| `FIX_Q01`, `FIX_Q50` | Yes | Always attached | Extra q=0.01,0.50 frontier points. |
| `TRIGGER_GATE`, `TRIGGER_SWITCH` | Yes | Respective lifecycle | Detector/dwell/hysteresis, no cost supervisor. |

All instrumented fixed policies run the same detector for sentinel alert metrics, but do not act on its requests; their cost supervisor need not execute, and any saved controller cost must be disclosed. Add a fixed-with-shadow-controller attribution check to measure this difference. `NONE` cannot produce BPF detections; never assign it perfect/zero recall as if it were a detector. Sentinel recall will often match between policies; **detail capture**, not reusing the same detector twice, is the main differentiating endpoint.

An always-on fixed MEDIUM/HIGH under SWITCH is the same steady attachment mechanism as GATE. Verify equivalence and use the common fixed baseline; do not double-count identical baselines as independent evidence. Do not claim implementation of Magnani's network system or SMCO from these proxies; direct reproductions are optional, separately costed research work.

## 8. Experimental design and run matrix

### 8.1 Separate populations

- **Calibration:** environment choice, workload size, detector references, cost tables, sink sizing and statistical precision. Synthetic/test data never substitutes for it.
- **Pilot:** end-to-end sanity, approximate run duration, feasibility and power/precision. Changes allowed with logs.
- **Confirmatory:** code/config/model/thresholds/statistics frozen and hashed. No tuning.
- **Robustness/exploratory:** held-out conditions and extra hypotheses; explicitly labeled, separate from confirmatory claims.

Use deterministic seed namespaces: calibration `100000+`, pilot `200000+`, confirmatory `300000+`, robustness `400000+`; derive workload, episode, ordering and bootstrap seeds with a documented stable hash, not Python's process-randomized `hash()`. A block ID pairs one scenario/schedule across policies. Each policy execution is an independent trial within that block. Fresh process/maps per trial; seed controls inputs and schedule, not the kernel schedule/PRNG.

### 8.2 Mandatory primary matrix

Seven policies `NONE,SENT,FIX_LOW_GATE,FIX_MED,FIX_HIGH,ADAPT_GATE,ADAPT_SWITCH` × two workloads × two background levels × drift absent/present = **56 treatment cells**. Each cell has **12 independent block repetitions** = **672 trials**, fourteen incident episodes per trial. Incident type for this matrix is the futex burst. These are 12 complete randomized policy blocks per workload/background/drift scenario, not 12 independent copies of one timeline from a single process.

Allocate each block's seven policy positions using seeded balanced cyclic orders, permuted across blocks; not every block starts with NONE. Run one scenario block per host at a time. Each block is the unit of pairing, not a presumption that cross-treatment kernel schedules are identical. Cooldown/readiness gates apply between treatments. Pair by block and scenario, and preserve order for drift/thermal analysis. Baseline reference missing/invalid means the block cannot contribute its paired application effect until the missing treatment is rerun under the retry policy.

At nominal timing `(30+240+5+15)s`, primary runtime is about **54.1 host-hours**, plus setup, drains, retries and calibration. `estimate-matrix` must calculate counts, expected bytes and runtime before launch. Default autonomous batch size <=6 h, with checkpoints and status after each trial; continue batches without requesting confirmation for already-authorized execution. Guard against insufficient disk/RAM. Do not silently shrink the matrix to fit a timeout.

### 8.3 Required supplementary matrix

Keep each extension matched to its appropriate NONE baseline and shared schedule:

| Study | Fixed scope | Repetitions |
|---|---|---:|
| Fixed q frontier | q=.01,.50, two workloads, high background, drift absent/present; reuse matching main baseline where block pairing exists, otherwise add NONE. | 8 blocks |
| Controller contribution | TRIGGER_GATE/SWITCH versus ADAPT_GATE/SWITCH, two workloads, high background, drift present. | 8 paired blocks per scenario |
| Hysteresis ablation | ADAPT variants with no recovery hysteresis: recover at h/2 on one quiet tick; dwell unchanged. Two workloads, high background, drift present. | 8 blocks |
| Dwell ablation | Dwell=0; hysteresis unchanged; same scenarios. | 8 blocks |
| Signal ablation | Replace 5 ms max detector input with the 100 ms total-switch count and separately calibrated normal baseline; use the same threshold-selection rule. Same scenarios. | 8 blocks |
| Budget targets | B=.02,.10, both adaptive variants plus NONE, two workloads, high background, drift present. | 8 blocks |
| Control period | P=25,500 ms; same variants/scenarios; recovery duration stays 500 ms in wall time, dwell 250 ms. | 8 blocks |
| Buffer overload | 256 KiB and 32 MiB; FIX_HIGH and both adaptive variants plus NONE, W-IO/high background/drift. | 8 blocks |
| Unseen incident class | CPU contention, two workloads/high background/drift; seven core policies. No tuning. | 8 blocks |
| Quiet false alarms | No incidents or drift; SENT and both adaptive variants; two workloads, both backgrounds. Five 20-minute measured trials per cell. | 5 long trials |

For extensions that reuse a main condition, only reuse paired records with identical protocol and block definition. Otherwise run new matched NONE/control treatments; a historical mean is not a paired baseline. Maintain full upper-bound runtime/storage estimate with all missing baselines before scheduling. Extensions are required for a complete paper-oriented artifact; if blocked by compute/access, list exact missing cells and scope claims accordingly. Do not make unsupported claims from an incomplete matrix.

### 8.4 Attribution and generalizability

Component attribution: no programs, loaded-unattached detail, sentinel-only, attached-empty detail pair, filter-only, pairing/aggregation without export, sampled export, full export, shadow controller and full agent. Three to five-minute workload runs with at least eight randomized blocks for both application families at high background. Use the same harness, not microbenchmark nanoseconds extrapolated universally. Separate BPF runtime-stats-on and stats-off groups for attribution only; measure stats overhead.

Second host: replicate seven core policies for both workloads at high background and drift, eight blocks; add one short-incident and one quiet test with identical protocol. Compare host interactions and report both hosts rather than pooling as independent identical machines. If no second host, this is a documented scope limitation. Optional real storage or server workloads require an additional signed-off-in-repo protocol before execution; they cannot silently replace the two core families.

## 9. Measurements, outcomes and statistics

### 9.1 Mandatory raw fields

`manifest.json`: run UUID, population, protocol/config hashes, code/tree hash and dirty status, host/boot ID, kernel/toolchain, CPU/SMT/affinity/governor, clock, privilege/features, build options, workload and schedule seeds, policy, model hash, map/sink bytes, stats setting, start/finish, exit and validity.

`truth.jsonl`: intended/actual episode boundaries, duration, helper roles and syscall totals; drift and background actual boundaries; readiness and termination events. `ticks.csv`: absolute monotonic ns, bin range, count/score, gap/staleness, requested/allowed/applied modes, transition state, q, prediction and context, alert state, counters and controller CPU. `transitions.jsonl`: action and acknowledgment times, attachment link/program IDs, generation and censoring. `detail.bin`: versioned record envelope and raw records. `counters.json`: final accounting with deltas and invariant status. `app.csv`: per-worker successful/failed unit counts and phase, sampled unit-duration histogram. `resources.csv`: observer and target CPU time, RSS, cgroup memory where supported, host utilization/steal/pressure and optional frequency/thermal samples. `stdout.log`, `stderr.log`, `commands.jsonl`, and `validity.json` are retained.

Sample external process/resource counters at 1 s by default identically in all treatments; the agent's own tick cost is separate. BPF CPU executed in workload context is not fully represented by collector process CPU; use causal application impact as primary and separate stats-on attribution. Do not call user-space observer CPU “total eBPF overhead.” Measure and report the all-treatment external harness cost with an additional no-sampler calibration.

### 9.2 Endpoint definitions

- **Detection recall:** fraction of valid injected incidents matched to an alert beginning from actual onset through actual end+1 s. Also report **on-time recall** restricted to before actual end; these are different.
- **Matching:** chronological one-to-one assignment of alert episodes to the earliest as-yet-unmatched overlapping incident window. A still-open preexisting alert is not a new detection of a later incident. Report such incidents separately as `already_alerting`; primary on-time recall counts them only if a prespecified *ongoing-visibility* secondary metric is used. Keep the primary definition fixed.
- **Precision:** matched alert episodes/all alert episodes over the eligible observation period; unmatched alerts are false positives unless in the predefined warmup/excluded guard region. Precision is N/A with no alerts. Quiet and benign-drift false alarm rates reported separately.
- **Detail capture:** complete emitted/consumed syscall pairs from injected helper TIDs whose entry is within a valid primary incident, divided by truth eligible helper calls. Report raw capture including intentional q, and delivery conditional on selection separately. Values must not exceed one absent an explicit error. For zero source calls report N/A.
- **Useful incident capture:** at least one correct completed pair during the incident; second endpoint requires at least ten correct pairs. These are operational definitions, not a claim of root-cause diagnosis quality. Do not tune these thresholds after seeing results.
- **Delay:** onset→alert; alert→detail-ready acknowledgment; onset→first captured incident pair; time until actual record receipt. Negative/inapplicable values are flagged. Missed incidents remain failures/right-censored in plots, not dropped from delay means. Show success fractions beside conditional latency distributions.
- **Loss:** independent counts for intentional sampling, failed state insertion, boundary censorship, kernel reserve failure, sink overflow and undrained end-of-run records. Distinguish entry/exit correlation failure from transport loss.
- **Stability:** completed mode changes/min, time fraction per mode, desired/applied disagreement duration, dwell deferrals, budget overrides and transition failures.
- **Resources:** throughput loss with CI, completed units/phase, user/system CPU, allocated BPF memory, collector RSS and buffers. Any sampled p95/p99 refers to **benchmark work-unit duration**, not service request latency; include sample count and method.
- **Model error:** compare phase-aggregated online predictions with phase-level measured effect and CI. Do not report exact per-tick false compliance unless a separate valid counterfactual estimator exists. Save unidentifiable states, sparse-table fallbacks, infeasible predictions and missing context.

### 9.3 Analysis protocol

Primary comparisons are ADAPT_GATE versus ADAPT_SWITCH for application throughput loss and incident capture, by workload/background/drift, plus each adaptive versus the fixed frontier. Baselines tied to identical sentinel do not create independent detector novelty.

For throughput use block-paired log ratios `r_i=log(Q_policy_i/Q_NONE_i)` and estimate loss `1-exp(mean(r_i))`. Bootstrap whole blocks with fixed seed and 10,000 draws for two-sided 95% intervals and the one-sided compliance limit. Preserve pairing, phases and policies within a resampled block. Episodes within the same run are correlated: bootstrap/cluster by block for capture and delay comparisons, not by individual event or episode. Report per-duration and per-phase counts, unweighted block-level rates and uncertainty. Long quiet tests use rates per observed hour with an appropriate count-rate interval and disclose clustering/limited duration. Use paired effect estimates as the main evidence; if testing a family of hypotheses, apply Holm correction within each preregistered family and publish both raw and adjusted p-values. Statistical significance alone is not practical usefulness.

Minimum practically interesting pilot criteria: resolve a 2 percentage-point throughput-loss difference and a 10 percentage-point capture difference, with intervals narrow enough to interpret. Twelve main blocks are a default, not guaranteed power. Pilot estimates within-run dependence and block variance; use simulation or conservative interval-width calculations to select the required final block count, **minimum 12 and default cap 30**, and freeze it before final execution. If 30 cannot resolve the target, report lower precision/limited sensitivity; do not stop early when a positive p-value appears. No optional peeking/stopping on effect sign. Changing confirmatory N after freeze requires a visible protocol amendment and separate analysis.

### 9.4 Validity and retry rules

Infrastructure invalidation: workload/helper crash, missing truth, malformed schema, unexpected target membership change, BPF load/attach failure, unreconciled ledger, clock mismatch, host suspension, lost unbounded sentinel history, disk-full, thermal emergency, or deliberate interruption. Predefine host-noise thresholds in the pilot: VM mean steal>2% or unexpected external CPU>5% of measured CPU capacity for>10% of run is a default noise flag; do not delete such data automatically. Preserve flagged results and provide with/without-noise sensitivity. Systematic noisy environments require a protocol change, not endless selective reruns.

Event loss, high application overhead, missed incidents, slow adaptation and predicted infeasibility are **research outcomes**, not invalidity. A legitimate saturated buffer is not a reason to rerun until it stops dropping. Infrastructure failures get at most two automatic retries with new attempt IDs and the same intended schedule; retain all attempts, analyze the first valid one by the preregistered rule, and flag repeated failure as a result/limitation. Rerun entire affected blocks if a common reference is unusable or the protocol differs.

## 10. Publication and artifact outputs

Every figure/table must be generated by one command from immutable validated records and list input hashes. Deliver vector PDF/SVG plus PNG previews:

1. Application-impact versus incident-capture frontier with CIs, mechanism and fixed policies.
2. Capture/on-time recall versus actual incident duration, grouped by control period.
3. Timeline showing truth, sentinel score, desired/applied mode, transition delay, loss and throughput on a preregistered representative block (median block by an explicit rule, not prettiest).
4. Kernel/sink loss and boundary-censoring decomposition.
5. Mode changes and high-mode occupancy with hysteresis/dwell ablations.
6. Measured versus predicted phase-level overhead, including uncertainty and infeasible contexts.
7. Component attribution and host/placement robustness.
8. Full result tables and failure inventory, including null/negative results.

Manuscript sections: question and scope; closest prior work; implementation/mode semantics; measurement and hypotheses; experimental protocol; results; threats/limits; reproducibility; conclusion. At least five directly relevant peer-reviewed sources are required by the assignment. Maintain `paper/claim_evidence.csv` mapping every numerical/comparative sentence to table/figure, run set, uncertainty and scope. Label proposed/inferred/author-reported/measured statements distinctly. Do not describe recorded syscall pairs as full causality or root-cause analysis. Freeze a target venue only after evidence; the artifact/report can be complete even without a publication-worthy effect.

## 11. Phases, steps, gates and progress checklist

All boxes start unchecked. A completed implementation must contain the same step IDs in the progress registry. Phase gates are evidence checks, not an instruction to repeatedly request permission.

### Phase 0 — Establish the research contract and repository

- [ ] **P0.1 — Inventory and preserve context.** Read the assignment and v4 review, retain source copies/hashes, inspect existing repo/instructions; create repository structure and progress/decision files without overwriting existing work.
- [ ] **P0.2 — Write the protocol draft.** Translate §§4–9 into machine-readable `configs/protocol.yaml`, schemas and hypothesis/metric registry. Mark every value as fixed, calibration-derived or exploratory.
- [ ] **P0.3 — Bound novelty claims.** Create `research/claims.md` and an evidence/access matrix for SMCO, QVM, Magnani, eInfer, Snowflakes, Ran, Naas, MooKernel and Hindsight. Recheck directly relevant sources for exact semantics; preserve unresolved access gaps. No endless novelty search may substitute for implementing the selected empirical question, but the manuscript cannot claim stronger novelty than this evidence supports.
- [ ] **P0.4 — Establish reproducibility commands.** Implement CLI argument validation/dry runs, output namespaces and schema versioning; generate manifest of every planned phase/step.

**Gate G0:** all assignment requirements map to a module, test and planned output; the claim ledger distinguishes proposed versus prior/measured; no undocumented mandatory design choice remains. Outputs: `protocol.yaml`, `requirements_traceability.md`, context manifest, progress files. Only planning/docs and scaffolding need exist at this gate.

### Phase 1 — Discover and lock the host/toolchain

- [ ] **P1.1 — Doctor.** Collect kernel/BTF/tracepoint/cgroup/privilege/topology/storage information and a bounded load/attach/receive/detach smoke test. Emit JSON plus readable diagnosis.
- [ ] **P1.2 — Reproducible build.** Lock compiler/libbpf/bpftool/Python dependencies, build flags and generated BPF headers. Record download/source hashes and license obligations. Avoid arbitrary unpinned latest packages.
- [ ] **P1.3 — Host setup and restoration.** Select CPU masks, create only owned cgroups/tmp files and establish host lock, disk/RAM guards, signal cleanup and configuration restoration tests. No orphan BPF links or worker processes after SIGINT or forced agent termination.
- [ ] **P1.4 — Unprivileged fallback.** Verify schemas/controller/analysis with synthetic fixtures. If privileged host is missing, produce an exact host bootstrap/readiness handoff and keep kernel-dependent gates blocked.

**Gate G1:** a host passes real privileged smoke tests or is explicitly unavailable. A simulated pass never satisfies G1. Save `host.json`, `toolchain.lock`, `doctor.log`, smoke-test artifact and cleanup report.

### Phase 2 — Build workloads and truth independently of BPF

- [ ] **P2.1 — Benchmark correctness.** Implement W-CPU checksum/work accounting and W-IO explicit pread workload, barriers, stable TID roles and affinity. Unit-check checksums, offsets, read/error accounting and drift settings.
- [ ] **P2.2 — Incident engine.** Implement bounded futex ping-pong, CPU hog, background helper and absolute monotonic scheduling; validate stop, timeout, late starts and teardown.
- [ ] **P2.3 — Ground truth.** Save intended and actual schedules, helper syscall totals, resource/duration boundaries and optional work-unit histograms. Verify controller access cannot read truth.
- [ ] **P2.4 — No-telemetry harness.** Run >=8 independent uninstrumented pilot trials per family at low/high background; verify complete work, achieved timing and baseline variance. Check actual short-burst durations and report jitter rather than accepting nominal values.
- [ ] **P2.5 — Measurement perturbation.** Compare harness/resource sampling on/off, truth aggregation on/off and optional unit-duration sampling on/off in calibration. Freeze the least intrusive configuration with justified precision.

**Gate G2:** deterministic input/checksum correctness, bounded shutdown, trustworthy truth counters, known timing resolution and measured baseline variability. A high-noise baseline must be resolved or declared before collecting tracing comparisons.

### Phase 3 — Implement and verify eBPF accounting

- [ ] **P3.1 — Sentinel.** Build target-TID filter, completed-bin reader and rolling per-CPU counters; test zero activity, burst position within a polling interval, wraparound, delayed reads, old/new generations and CPU migration.
- [ ] **P3.2 — Paired detail.** Implement allowlist, entry sampling, inflight lifecycle, fixed record ABI and all loss/error counters. q=0 and q=1 are exact branches; intermediate probabilities statistically validated.
- [ ] **P3.3 — Collector and sink.** Implement nonbusy event loop, bounded transport-to-sink queue, binary framing, block checksums, final drain and schema-checked parser. Test intentionally corrupt/truncated files and output backpressure.
- [ ] **P3.4 — Count truth test.** Run a small known-count target that performs exactly N explicit pread/futex calls. With q=1 and no boundary/overload, require exact kernel-entry/selected/completed/received accounting after drain. Nonzero unexplained loss is a failure. Validate syscall return/duration with a separate tiny correctness-only per-call log.
- [ ] **P3.5 — Race and failure tests.** Signals/restarted calls, long waits, map capacity, thread exit, simultaneous workers, ring saturation, sink overflow, timestamp order and generation changes. Every deliberately induced missing record has a classified reason.
- [ ] **P3.6 — Cost instrumentation separation.** Build optional BPF runtime-stat diagnostics but prove it is off in primary manifests. Check orphan program/link inventory before and after tests.

**Gate G3:** event semantics are correct and losses reconcile. Preserve verifier logs and real count-test output. Performance optimization cannot hide malformed events or losses.

### Phase 4 — Implement mode lifecycle and policy

- [ ] **P4.1 — Fixed modes.** Implement NONE/SENT/FIX_LOW_GATE/FIX_MED/FIX_HIGH, verify intended programs attached and q chosen. Confirm fixed MED/HIGH steady path equivalence across mechanism labels.
- [ ] **P4.2 — GATE/SWITCH lifecycle.** Implement activation ordering, versioned configuration publication, disabled-entry grace, draining, forced-abandonment and transition timing. Do not rely on atomic two-link operations. Inject attachment failure and cancellation at every transition state.
- [ ] **P4.3 — Detector.** Implement frozen log-count baseline, robust score, gap semantics and alert-state matching inputs. Test bursts entirely between ticks, quiet/noisy signals and fake missing bins.
- [ ] **P4.4 — Controller.** Implement deterministic requested/allowed/applied state logic, quiet recovery, dwell, budget override, predicted-infeasible state, transition-in-progress and queued request. Replay synthetic ticks through exact expected transitions.
- [ ] **P4.5 — Integration.** Run short real workloads covering LOW→MEDIUM→HIGH→LOW, transitions during a syscall and re-escalation while draining. Verify metadata and reconciled boundary losses.

**Gate G4:** all state transitions have test coverage and raw evidence; same input tick stream yields identical desired states across mechanisms when cost tables are disabled. Attach acknowledgment and first captured event remain distinct.

### Phase 5 — Calibrate without using final tests

- [ ] **P5.1 — Rate and storage calibration.** Select fixed work-unit sizes, normal/high event rates and sink capacity from calibration-only data; bound the primary W-IO detailed eligible-entry rate to 50,000/s aggregate by selecting a fixed deterministic per-read compute batch if necessary, then freeze that batch and disclose it. An event-rate sweep above that bound is a separate overload extension, not a change to the core workload. Project worst-case raw bytes for q=1 plus helper bursts; perform a sustained sink-throughput test.
- [ ] **P5.2 — Detector training.** Collect normal calibration, choose baseline and thresholds by the fixed selection rule, and estimate false-alarm rate on held-out normal calibration. Freeze matching settings for both mechanisms.
- [ ] **P5.3 — Cost tables.** Collect calibration-mode application impacts and context; build means/UCLs/fallbacks for both mechanisms. Include all observer costs and calibrate transitions separately.
- [ ] **P5.4 — Component attribution.** Run initial empty/filter/pair/export measurements to determine whether the testbed has a measurable range of costs. This is replication/calibration evidence, not a paper novelty result.
- [ ] **P5.5 — Precision/power pilot.** Estimate paired block variance and within-run dependence; determine final block count and budget sensitivity using preregistered practical differences. If the chosen budgets are all infeasible due to sentinel cost, retain that result and explicitly amend any additional feasible-budget experiments *before* confirmatory data.
- [ ] **P5.6 — Bounded feasibility decision.** Verify system correctness, storage, runtime and detectable effect range. If simple fixed tracing dominates, proceed with a transparent comparison/negative result rather than engineering a biased success case. If the host cannot resolve effects, mark the research evaluation blocked or limited.

**Gate G5:** versioned calibration artifact, frozen workload/detector/cost model, timing/noise/storage report, justified N and no final-data leakage. Missing cost information produces explicit uncertainty, not optimistic defaults.

### Phase 6 — Freeze and execute the experiment campaign

- [ ] **P6.1 — Preregistration freeze.** Commit/tag code, protocol, models, analysis equations, cell registry, seeds, order plan, retry/exclusion rules and expected result files. `freeze` hashes all dependencies. Changes after this require a protocol amendment.
- [ ] **P6.2 — Matrix validation.** Generate complete treatment/block/attempt records, costs, runtime and storage estimates; ensure every comparison has matched NONE/control records. Dry-run all commands.
- [ ] **P6.3 — Primary campaign.** Execute serially per host with readiness, automated validation, checkpoints and cooling. No manual seed selection or removal of unfavorable results.
- [ ] **P6.4 — Supplementary campaign.** Execute fixed-q frontier, supervisor, hysteresis/dwell/signal/budget/control-period, overload and quiet tests. Save exact reused-versus-new baseline mappings.
- [ ] **P6.5 — Robustness.** Run unseen CPU-contention class, isolated observer and second-host subset where available, with frozen configurations. Mark unavailable extensions explicitly.
- [ ] **P6.6 — Failure audit.** Validate ledger/manifests, distinguish infrastructure failure from genuine loss/slowdown, apply bounded retry rule and export all attempt statuses.

**Gate G6:** all planned cells are valid/completed or individually accounted for as blocked/failed; campaign completeness is reported numerically. Partial data can support only explicitly scoped analyses.

### Phase 7 — Statistical analysis and adversarial checks

- [ ] **P7.1 — Raw validation.** Reject schema/version incompatibilities, impossible counts, clock errors and unjustified many-to-one alert matching. Reconcile raw data before plotting.
- [ ] **P7.2 — Metrics.** Compute all defined outcomes, matching/censoring rules, per-phase comparisons and loss categories. Verify tiny hand-calculated synthetic fixtures against implementations.
- [ ] **P7.3 — Statistical inference.** Generate block-paired CIs/compliance categories, effect sizes, correction families and missing-data tables. CIs at the correct independent unit; no millions-of-events false precision.
- [ ] **P7.4 — Strong-baseline check.** Compare to the fixed frontier, trigger-only, same-memory/sink policies, and shadow-controller cost. Refuse a comparison that attributes different detector inputs or payloads to the collection mechanism.
- [ ] **P7.5 — Robustness and negative cases.** Analyze noisy-run sensitivity, drift phases, actual versus nominal durations, conditional versus unconditional delay, boundary grace and shared versus isolated collector placement.
- [ ] **P7.6 — Scientific decision.** For every hypothesis report supported/not supported/inconclusive with exact scope. Reassess novelty against closest work using actual result, not desired architecture. Do not convert a replication into a first claim.

**Gate G7:** tables/figures reproducible from validated inputs; every finding includes denominator, uncertainty, conditions and counterexamples; limitations visible.

### Phase 8 — Paper-style report and research claim audit

- [ ] **P8.1 — Write methods first.** Document actual implemented semantics, budgets, host, workloads, conditions, randomization, loss and measurement costs. Update from design to actual behavior where deviations occurred.
- [ ] **P8.2 — Results and evidence mapping.** Generate all required figures/tables and claim ledger. Main text includes fixed-baseline comparisons and null/negative outcomes.
- [ ] **P8.3 — Prior-art audit.** Recheck the exact measured finding against Magnani/eInfer/SMCO/Snowflakes/Ran/Naas; distinguish reproduced mechanisms from any newly observed interaction. Update citations/status/access notes; verify bibliography metadata before submission.
- [ ] **P8.4 — Skeptical review.** Explicitly answer: could low cost be due to drops, could fixed low do as well, did changing event semantics alter detection, is the effect just one machine, did incomplete ground truth or scheduling create it, and did controller cost move off the measured cores?
- [ ] **P8.5 — Scope final contributions.** State the strongest justified result. If there is insufficient novelty, deliver the complete course study and reproducibility artifact; explicitly say what would be needed for a research publication.

**Gate G8:** all numerical claims map to artifacts; no proposal/result confusion, invented citations, hidden exclusions or universal guarantees. Manuscript limitations include remaining literature gaps.

### Phase 9 — Independent replay, cleanup and final handoff

- [ ] **P9.1 — Clean build/replay.** Rebuild in a clean checkout, run unprivileged tests, real privileged count test and one canonical trial per workload; rerun analysis from archived data without manual edits.
- [ ] **P9.2 — Artifact bundle.** Package code or repository commit, environment locks, configs, sources/links, truth/manifests/raw archive inventory, derived results, manuscript and commands. Data too large for one bundle gets explicit checksummed shards; include no personal secrets or unrelated files.
- [ ] **P9.3 — Reproduction guide.** Provide quick smoke (<15 min if host ready), core subset, full campaign and analysis-only paths, expected resource costs, exact privileges and known failure modes. State which results were actually reproduced on which host.
- [ ] **P9.4 — Restore and verify.** Destroy owned links/maps, workers/cgroups/temp files; restore any changed host settings; retain raw archives and evidence. Compare pre/post instrumentation inventory.
- [ ] **P9.5 — Final status.** Complete phase/step matrix, unresolved issues, experiment completeness, paper-readiness decision and exact next actions. Report every skipped gate and why.

**Gate G9:** clean-checkout reproduction evidence, checksummed release and transparent final status. Project done means a correct implementation and scientifically honest study, not a guaranteed positive research claim.

## 12. Configuration contract

The agent must encode and validate at least these groups in `configs/protocol.yaml`; unknown fields are errors and defaults are written into resolved config manifests:

- `protocol`: version, population, source/context hashes, preregistration hash.
- `host`: discovered identity, kernel/toolchain locks, CPU masks, placement, privilege mode, cgroups, restoration manifest and required feature list.
- `workload`: family, workers, unit definition, checksum, IO sizes/files, drift phase/settings, warmup/measure/drain/cooldown, input seeds and resource guards.
- `incidents`: class, durations, anchors/jitter, handshake/timeout, background level, actual-timing tolerance and generation-failure rule.
- `sentinel`: hook, target roles, bin width/count, lag, missing-bin behavior.
- `detail`: hooks, syscall allowlist/ABI, map sizes, packed-config layout, sample probabilities, record version, ring bytes, drain grace, sink/queue size and overflow accounting.
- `detector`: reference/model hash, transform/scale floor, thresholds, period, recovery duration, alert close and missing-sensor behavior.
- `controller`: mechanism, initial mode, dwell, budget target, model table/context bands, supervisor on/off, fallback and transition-cost policy.
- `experiment`: policies/scenarios, blocks, seed namespace, order schedule, quiet tests, retries, invalidation/noise flags, batch size and storage estimate.
- `analysis`: endpoints, alert-matching window, capture threshold, phase rules, bootstrap seed/draws, CI levels, paired unit, multiple-testing family and treatment of missing outcomes.

Add a `resolved_config.json` to every attempt. Numerical values chosen through calibration must be resolved and hashed before freeze; no `TBD` remains in a confirmatory configuration. A missing physical host identifier cannot be filled fictitiously; discovery is a named Phase 1 dependency.

## 13. Requirements traceability and definition of done

| Assignment/research requirement | Implementation | Evidence/acceptance |
|---|---|---|
| Three intensity modes | LOW/MEDIUM/HIGH and q semantics | P4 tests, mode traces, occupancy. |
| Low-cost always-on signal | Scheduler-bin sentinel | Cost attribution and count/gap tests. |
| Trigger, hysteresis and minimum dwell | Frozen detector/controller | Synthetic replay plus real transitions; ablations. |
| Declared overhead target | B=5%, calibrated best-effort supervisor | Independent block-paired measured effects, including violations/inconclusive. |
| Fixed and no-telemetry comparisons | Seven core policies plus q frontier | Complete randomized matrix and matched baseline IDs. |
| Short/long anomalies | 10–1000 ms requested futex episodes | Actual duration/ground-truth totals and capture/latency plots. |
| Multiple loads/workloads and drift | CPU + cached I/O, backgrounds, benign phase change | Per-scenario effects, holdout CPU-contention test. |
| Loss and delay | Kernel/sink/boundary ledger; distinct timestamps | Reconciliation and failure-case tests. |
| CPU/memory/application/stability metrics | Agent/resources/app tables | Evidence-backed result tables; no CPU-attribution shortcut. |
| >=5 repetitions/CIs | >=12 core blocks, >=8 supplementary | Block-level statistical analysis, pilot precision rationale. |
| Reproducible report/artifact | Frozen inputs/code/data + generated figures | Clean replay, claim ledger, source/metadata audit. |
| Honest research claims | Prior-art boundary and failure outcomes | Phase 8 skeptical review; no unsupported novelty guarantee. |

Before final delivery the agent must answer **yes, no or blocked** for: real kernel load verified; known-count pair capture exact; all losses classified; input schedules preserved; controls matched; actual duration measured; controller blind to truth; model frozen; stats overhead excluded from primary; protocol/attempt history immutable; CIs clustered correctly; the planned matrix and valid/failed/missing counts reconcile; all required cells accounted for; figures regenerable; cleanup verified; claims scoped to evidence. “Blocked” must name the missing dependency and completed independent work.

## 14. Technical and research references

Consult the target versions; retrieval date 30 October 2026 for implementation documentation. These links define semantics, not evidence that this unbuilt system works:

- [Linux BPF/libbpf overview](https://docs.kernel.org/bpf/libbpf/libbpf_overview.html) — loading, attaching and CO-RE/skeleton workflow.
- [BPF ring buffer](https://docs.kernel.org/bpf/ringbuf.html) — reservation/output semantics and transport limits.
- [BTF](https://docs.kernel.org/bpf/btf.html) — kernel type metadata.
- [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) — process organization and resource control/accounting.
- [BPF syscall/runtime stats](https://www.kernel.org/doc/html/next/userspace-api/ebpf/syscall.html) — runtime statistics are disabled by default to avoid measurement overhead; resolve against the actual kernel/UAPI.
- [SMCO](https://doi.org/10.1007/s10009-010-0184-4); [QVM author paper](https://files.sri.inf.ethz.ch/website/papers/oopsla08.pdf); [Magnani et al.](https://doi.org/10.1109/ACCESS.2022.3202644); [eInfer](https://doi.org/10.1145/3748355.3748372); [Snowflakes](https://doi.org/10.1145/3748355.3748364); [Ran et al.](https://doi.org/10.1109/ACCESS.2026.3658370); [Naas et al.](https://doi.org/10.1145/3805687.3806254); [MooKernel](https://doi.org/10.1145/3672197.3673431); [Hindsight](https://www.usenix.org/conference/nsdi23/presentation/zhang-lei) — direct prior-art boundaries and comparison motivation. Read access/status limitations in `novelty_review_v4.md`.
