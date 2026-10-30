# Claim boundary

The proposed contribution is a reproducible comparison of in-probe sampling and link switching under an application throughput-loss target, including short-incident capture and failure boundaries. H1–H4 in `context/plan.md` are hypotheses, not findings.

No measured result exists on the Windows development host. Synthetic fixtures verify software only. No claim of first adaptive eBPF controller, first overhead budget, first hook-cost floor, first loss accounting, deterministic overhead guarantee, or universal best policy is permitted.

SMCO, QVM and adaptive eBPF network telemetry establish strong prior-art boundaries. Naas et al. directly motivate component attribution and event-rate-dependent overhead. Hindsight is a retroactive distributed tracing design; the present BPF ring buffer is only a bounded transport. Source access, metadata verification and missing full-text reviews are recorded in `evidence_access.csv`.

The source-precedence v4 review was not supplied. Its absence remains an explicit research-audit blocker. None of the initial literature review's preliminary novelty statements overrides the plan's conservative contract.

Every comparative/numerical manuscript finding must map to immutable validated runs, conditions, denominators and block-level uncertainty in `paper/claim_evidence.csv`. No automated hypothesis approval is inferred from compilation or synthetic plots.
