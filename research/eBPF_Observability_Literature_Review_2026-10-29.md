# Literature Review: Resource-Aware Adaptive eBPF Observability

**Search cutoff:** 29 October 2026  
**Assignment:** Adaptive eBPF Telemetry with an Explicit Overhead Budget  
**Status:** Curated first-pass literature review. This is **not** a certified exhaustive systematic review or proof of novelty. Focus is peer-reviewed research, supplemented with clearly labeled emerging evidence.

## Executive finding

Adapting tracing intensity in response to anomalies **is not novel on its own**. Related approaches have already appeared in fully adaptive eBPF network telemetry (Magnani et al., 2022), adaptive sensing using state-aware eBPF hook orchestration (Ran et al., 2026), adaptive kernel-event tracing (LMAT, 2026, which uses LTTng rather than eBPF for trace collection), and selectively detailed production tracing (StriaTrace, OSDI 2026). Other systems separately investigate event loss, probe overhead, and resource scheduling.

**Candidate research problem (must be checked more deeply):** Can an adaptive eBPF observability controller dynamically account for the *actual application-impact cost* of its instrumentation and optimize anomaly detection and short-burst capture subject to a declared, measured overhead budget, explicitly exposing event loss and the system's failure envelope?

Do not equate **storage/trace-volume reduction** with **CPU/throughput overhead reduction**, or a soft average budget with a deterministic per-interval guarantee.

## A. Highest-priority direct papers

1. **Bridging Observability and Security: A Graph-Based Arbitration and Adaptive Sensing Approach via eBPF** — Heng Ran, Chuanping Hu, Yan Zhuang; *IEEE Access*, 2026. Peer-reviewed. DOI: https://doi.org/10.1109/ACCESS.2026.3658370  
   *What it does:* Multi-modal eBPF sensing; low-load mode by default; dynamic hook orchestration and deeper forensic/security hooks in response to anomalies or drift.  
   *Why essential:* Most direct precedent against claiming that multi-mode eBPF adaptation itself is new.  
   *Our potentially distinct axis:* Quantitative CPU/throughput budgets, event-loss visibility, adaptation delay, small-burst detection trade-offs, and multiple baselines. **Requires full evaluation-section review.**

2. **LMAT: An adaptive tracing approach based on efficient system behavior analysis using language models** — *Journal of Systems and Software* 238 (Aug 2026), 112890. Peer-reviewed. DOI: https://doi.org/10.1016/j.jss.2026.112890 ; accessible: https://www.sciencedirect.com/science/article/pii/S0164121226001238  
   *What it does:* Predicts kernel event identity and duration; changes tracing granularity when deviations occur. Reports 70.6% less recorded trace data in tested scenarios.  
   *Crucial qualification:* It uses **LTTng**, not a demonstrated eBPF overhead-budget controller; reduced trace volume is not synonymous with CPU overhead. In one deployment-oriented workload, asynchronous inference added no measurable incremental latency beyond tracing.

3. **StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference (Operational Systems)** — Haonan Wu et al.; *OSDI 2026*, July 2026. Peer-reviewed/top-tier. https://www.usenix.org/conference/osdi26/presentation/wu-haonan  
   *What it does:* Critical synchronization and path tracing; detailed capture during abnormalities; reports 97.8% tracing overhead reduction versus alternatives in LLM inference.  
   *Our distinction:* General-purpose eBPF event collection with explicit observer budget and burst detection under load, rather than an LLM-serving-specific diagnosis pipeline.

4. **Dissecting Storage I/O Tracing Overhead of eBPF: A Component-Level Analysis** — Mohammed Islam Naas, Pierre Olivier, Stéphane Rubini, Frank Singhoff, Jalil Boukhobza; *CHEOPS @ EuroSys 2026* workshop, April 2026. Peer-reviewed workshop. DOI: https://doi.org/10.1145/3805687.3806254 ; author slides/preprint: https://cheops-workshop.github.io/talks2026/cheops26-naas.pdf  
   *What it does:* Decomposes eBPF tracing cost into instrumentation components. Reports up to 41% overhead under small-I/O, high-concurrency workloads; export and probe triggering significant contributors.  
   *Implication:* Calibrate actual hook activation, map operations, buffer delivery, and user-space work separately. Sampling *after* probe entry does not eliminate probe-trigger costs.

5. **PeeR: First-Class Scheduling for Latency-Critical eBPF Applications** — Jeremy Carin, Ben Holmes, Weiyang Wang, Ankit Bhardwaj, Manya Ghobadi; *OSDI 2026*, July 2026. Peer-reviewed/top-tier. https://www.usenix.org/conference/osdi26/presentation/carin  
   *What it does:* Cooperative preemption, scheduling, and CPU budget controls for certain eBPF runtime paths.  
   *Why essential:* Already addresses **resource controls on eBPF execution**. The distinction for us must be resource-aware observability decisions coupled to *detection quality*, not claiming the invention of eBPF budgeting generally.

6. **Aquila: Efficient In-Kernel System Call Telemetry for Cloud-Native Environments** — Juyong Shin, Jisu Kim, Jaehyun Nam; *Sensors* 25(21), 6511, October 2025. Peer-reviewed. DOI: https://doi.org/10.3390/s25216511 ; open access: https://pmc.ncbi.nlm.nih.gov/articles/PMC12608121/  
   *What it does:* Efficient dual-path event delivery, priority-aware buffering, explicit drop detection and workload attribution.  
   *Why essential:* Lost events and transport bottlenecks are known, important prior art. New contribution must go beyond simply counting drops.

## B. High-value supporting papers (peer-reviewed)

7. **A Control Plane Enabling Automated and Fully Adaptive Network Traffic Monitoring With eBPF** — S. Magnani, F. Risso, D. Siracusa; *IEEE Access* 10, 90778–90791, 2022. DOI: https://doi.org/10.1109/ACCESS.2022.3202644 ; institution record: https://iris.polito.it/handle/11583/2972688  
   Adaptive network-traffic telemetry with dynamic collection and efficiency comparisons. Crucial early related work; don't claim first adaptive eBPF controller.

8. **SampleHST-X: A Point and Collective Anomaly-Aware Trace Sampling Pipeline with Approximate Half Space Trees** — Alim Ul Gias et al.; *Journal of Network and Systems Management* 32(3), art. 44, 2024. DOI: https://doi.org/10.1007/s10922-024-09818-8 ; open copy: https://openaccess.city.ac.uk/id/eprint/32709/  
   Explicit *storage/sampling quota*, online anomaly-aware trace selection, point and collective anomalies. Different budget definition from application CPU overhead. Useful sampling-quality baseline.

9. **EAudit: A Fast, Scalable and Deployable Audit Data Collection System** — R. Sekar, Hanke Kimm, Rohit Aich; *IEEE Symposium on Security and Privacy*, 2024. DOI: https://doi.org/10.1109/SP54263.2024.00087 ; code: https://github.com/seclab-stonybrook/eaudit  
   High-throughput eBPF auditing, reduced data volume and loss. Use to motivate transport baseline and efficiency evaluation.

10. **eBeeMetrics: An eBPF-based Library Framework for Feedback-free Observability of QoS Metrics** — *IEEE ISPASS*, April 2026. DOI: https://doi.org/10.1109/ISPASS69572.2026.00056 ; code: https://github.com/Ibnathism/eBeeMetrics  
   Derives application QoS performance metrics from eBPF-observable kernel events without application instrumentation. Possible cheap feedback signal.

11. **eHashPipe: Lightweight Top-K and Per-PID Resource Monitoring with eBPF** — Yuanjun Dai, Qingzhe Guo, Xiangren Wang; *IEEE CCNC*, January 2026. DOI: https://doi.org/10.1109/CCNC65079.2026.11366341 ; preprint: https://arxiv.org/abs/2509.09879  
   Compact in-kernel sketch for top-k process CPU/memory monitoring; reports faster burst visibility than top. Related to lightweight always-on trigger design, not explicit anomaly-overhead optimization.

12. **eInfer: Unlocking Fine-Grained Tracing for Distributed LLM Inference with eBPF** — *3rd Workshop on eBPF and Kernel Extensions*, 2025. DOI: https://doi.org/10.1145/3748355.3748372  
   Runtime-adaptive eBPF tracing for end-to-end distributed LLM inference. Sector-specific but relevant to dynamic collection and overhead claims.

13. **TracePicker: Optimization-Based Trace Sampling for Microservice-Based Systems** — *Proceedings of the ACM on Software Engineering*, 2025. DOI: https://doi.org/10.1145/3729351  
   Optimization-based sampling of valuable distributed traces and anomaly coverage. Pertinent to defining a *trace quota* budget but not identical to capping eBPF CPU cost.

14. **Extending Applications Safely and Efficiently** — *OSDI 2025*. https://www.usenix.org/conference/osdi25/presentation/zheng-yusheng ; full paper: https://www.usenix.org/system/files/osdi25-zheng-yusheng.pdf  
   Introduces user-space eBPF runtime / bpftime for application extensions and observability. More peripheral; implementation context rather than a direct budget baseline. Check primary presentation before formal bibliographic citation.

## C. Frontier / contextual sources: do NOT count as peer-reviewed papers without confirming publication

- **Pull-based Scraping vs. eBPF Auto-instrumentation: Overhead, Coverage, and Trade-offs** — TU Delft repository, 2026, https://repository.tudelft.nl/record/uuid%3Af5e63a79-6255-48d0-a74f-4cc9b7b4afbf. Thesis/repository work. Particularly provocative finding: lowering Beyla's sampling rate may barely reduce instrumentation overhead because the uprobes still execute. Valuable hypothesis to reproduce, but source is not established here as a peer-reviewed conference paper.
- **Comparing change detectors for adaptive execution tracing: Large-scale validation and design insights** — *Information and Software Technology*, volume dated **December 2026**, DOI https://doi.org/10.1016/j.infsof.2026.108339. Searchable online but its issue date is after our 29 Oct 2026 cutoff; treat as an upcoming/online-available study with publication timing to verify, not a completed already-published benchmark.
- **eBPF-based cybersecurity mechanisms: a systematic literature review** — *International Journal of Information Security*, Aug 2026, DOI https://doi.org/10.1007/s10207-026-01326-x. Useful survey and citation-mining source, but focused on security.
- **eBPF Research Papers (curated index)** — https://pchaigno.github.io/bpf/2025/01/07/research-papers-bpf.html. Updated Oct 2026; not a peer-reviewed publication. Good way to discover recent OSDI/NSDI/EuroSys papers.

## Preliminary research gap ranking

### G1: Cost-accountable adaptive observability (recommended primary gap)

**Question:** Can telemetry intensity be adjusted using a calibrated, updatable *observer cost model* while respecting a declared CPU or application throughput-loss budget?

**Different from:** Adaptive tracing without explicit cost control (Ran/LMAT), eBPF runtime CPU scheduling (PeeR), offline cost decomposition (Naas), and storage-quotas for trace retention (SampleHST-X).

**Method:** Break total cost into fixed probe-trigger costs, in-kernel map/aggregation costs, export/transfer, user-space collector and controller costs; calibrate and track event rates. Compare to simple threshold-only adaptive mode selection under matched workloads. Validate budget compliance with independent application throughput, latency, and CPU measurements.

**Danger:** True incremental overhead cannot be known online without a counterfactual unmonitored run. Call this **model-based soft budget enforcement**; do not promise a hard guarantee. A mandatory always-on signal sets a minimum overhead floor. No online scheme can assure capturing information it never observed.

### G2: Short-burst-aware sensing with a tight budget (excellent secondary gap)

**Question:** How does anomaly duration relative to controller interval and sampling fraction determine miss probability/detection delay, and can a cheap in-kernel burst trigger reduce this blind spot?

**Method:** Force anomalies lasting 10/25/50/100/250/500/1000 ms at randomized times and under controlled contention. Compare low/medium/high, simple reactive adaptation, and 2-timescale burst-aware budget controller. Keep detection and trace-capture metrics separate.

**Caution:** With independent per-event sampling at rate `p` and a burst containing `n` eligible events, probability of capturing zero is `(1-p)^n`; this is a *sanity check under ideal assumptions*, not a universal recall formula. Also measure timing aliasing from controller polling.

### G3: Backpressure-aware fidelity under workload drift (harder, strong extension)

**Question:** When ring buffers back up and workload characteristics drift, can adaptive control maintain measured event-fidelity per overhead instead of silently losing diagnostic events?

**Method:** Expose separate counters for unsampled events, failed buffer reservations, and consumed events; use drop feedback, collector lag, change-point flags, and per-CPU aggregation. Evaluate abrupt workload transitions and adversarial timing. Compare with Aquila and eAudit design lessons.

**Caution:** Simply measuring drops is prior art. Novelty, if any, would lie in decision policy and evaluation of anomaly coverage under a declared budget.

## Proposed experiment matrix

- Policies: no telemetry; fixed-low; fixed-medium; fixed-high; threshold-only adaptive; hysteresis+dwell adaptive; **cost-aware adaptive**; optional cost-aware + short-burst trigger.
- Workload types: controlled scheduler burst, CPU contention, I/O burst; at least one held-out class.
- Duration conditions: 10, 25, 50, 100, 250, 500, 1000 ms, plus long anomalies.
- Background load: low/medium/high, with randomized onset times and fixed seeds.
- Budgets: several empirically calibrated throughput-loss targets (e.g., 1%, 3%, 5%) **only if feasible on the test machine**.
- Outcome metrics: interval budget exceedance; cumulative measured throughput loss; task CPU, p95/p99 application latency; event-trigger rate; kernel probe cost; userspace cost; dropped records; detection recall/precision; first-detection delay; trace completeness; mode switches; instability.
- Methodological safeguards: >=5 repetitions where feasible, rotating run order, uncertainty intervals, blind test seeds, no tuning on held-out patterns, controller-only baseline, clear per-CPU and global clocks.

## Concrete falsifiable hypotheses

- **H1:** Cost-aware adaptation reduces budget-violation frequency compared with threshold-only adaptation at comparable detection recall.
- **H2:** A lightweight burst-sensitive trigger reduces miss rate for events shorter than a controller epoch, without exceeding the chosen measured budget in most trials.
- **H3:** Counting export drops and accounting for probe invocation cost reduces gaps between the estimated and measured monitoring overhead relative to trace-volume-only proxies.

These are hypotheses to test, not expected outcomes or already established conclusions.

## Initial reading order

1. Ran et al. (2026) — disqualifies naive novelty claim.
2. LMAT (2026) — detection-driven trace control, distinguish LTTng/data reduction from eBPF/CPU budget.
3. Naas et al. (2026) — why trace-volume budgets are insufficient.
4. PeeR (2026) — resource budgeting for eBPF execution is already a research topic.
5. Aquila (2025) and eAudit (2024) — event loss and delivery cost.
6. Magnani et al. (2022), SampleHST-X (2024), StriaTrace (2026) — adaptive sampling and realistic baselines.
7. eBeeMetrics, eHashPipe, eInfer — ideas for low-cost signals and related control architecture.

## Novelty due diligence before drafting a paper

- Obtain and read **full design, evaluation, limitations, and related-work** sections of the six highest-priority papers, not just abstracts.
- Backward- and forward-citation chase the most direct papers; specifically search for published **budget-aware tracing**, **online instrumentation-cost estimation**, **adaptive trace fidelity**, and **short-lived anomaly monitoring**.
- Record which claims are experimentally proved, reported as simulations, or only asserted.
- Prototype the smallest meaningful budget-aware controller *before* committing to the final novelty claim.
- Document failed conditions as part of the contribution, especially infeasible budgets and bursts missed by all low-cost sensors.

**Assessment:** Promising as an empirical OS systems paper or workshop contribution if supported by new measurements and rigorous evaluation. A novel idea alone does not imply venue acceptance or priority over unexamined prior work.
