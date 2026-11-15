# Open issues and evidence boundaries

| ID | Status | Evidence | Consequence |
|---|---|---|---|
| I001 | Resolved | Ubuntu 26.04 LTS Linux host inventory and passed privileged smoke in `state/host.json` and `state/evidence/linux-smoke-20261114-001/checks.json` | Linux build and execution are recorded. |
| I002 | Open | `novelty_review_v3.md`, `novelty_review_v4.md`, and the referenced research ZIP were not present in the supplied context | Do not make a novelty claim based on the missing source-precedence review. |
| I003 | Resolved | Repository was initialized and has recorded commits | Continue preserving source and immutable run history. |
| I004 | Resolved | Python environment and locked dependencies are present | Keep using the checked-in lock files. |
| I005 | Partially resolved | Some DOI/full-text sources were inaccessible during the earlier literature check; verified source metadata and current references are recorded in `latex_report/references.bib` | Keep related-work claims within sources actually checked. |
| I006 | Resolved for the recorded smoke | `state/evidence/linux-smoke-20261114-001/checks.json` has `passed: true`, `synthetic: false` | The known-count high/low/sentinel checks passed; this does not replace longer race/performance acceptance. |
| I007 | Resolved | Existing matrix construction tests and the preserved pilot campaign | No effect on reported pilot comparisons. |
| I008 | Resolved for recorded build | Linux toolchain and BPF build evidence under `state/bootstrap/` and `build/` | Rebuild against each target's BTF and toolchain. |
| I009 | Resolved for recorded target load | Privileged Linux smoke exercised the actual eBPF programs | Extend testing for all lifecycle races and modes before broad claims. |
| I010 | Open | Primary pilot has four paired blocks per workload; all 16 attempts carry `external_cpu_above_preregistered_threshold` | Treat pilot intervals as exploratory; budget decision remains inconclusive. |
| I011 | Open | `data/confirmatory/` and `data/robustness/` have no completed campaign; current pilot policy set is NONE/FIX_Q01 | No adaptive-vs-fixed, drift, robustness, or multi-host empirical conclusion is available from the pilot. |
