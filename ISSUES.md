# Issues

| ID | Status | Evidence | Consequence |
|---|---|---|---|
| I001 | Open | `wsl --status` and `wsl --list --verbose`: WSL not installed; platform Windows | No real BPF build/load, Linux workload, calibration, campaign or empirical results can be verified on this host. |
| I002 | Open | Initial inventory contains only three research sources | `novelty_review_v3.md`, `novelty_review_v4.md`, `adaptive_ebpf_research.zip` missing. Prior-art gate remains limited. |
| I003 | Resolved | Initial `git status` failed: no repository | Initialized a new Git repository without replacing supplied files. |
| I004 | Resolved | Initial venv ensurepip failed in restricted execution; authorized retry succeeded | Project dependencies use `.venv/`; no system package changes. |
| I005 | Open | Direct DOI retrieval returned errors/403 for several closest papers | Record access limitations; do not infer full-paper semantics from abstracts. |
| I006 | Resolved | Initial portable tests could not access protected temporary files/execute the compiled checker | Authorized retry passed; no Windows security policy was changed. Initial failure log retained. |
| I007 | Resolved | Full matrix initially supplied duplicate drift argument for secondary quiet study | Corrected construction; complete-matrix tests pass. |
| I008 | Resolved | Linux cross compiler caught conflicting UAPI integer typedefs and printf widths | Use Linux UAPI types and explicit format casts; compile checks repeated. |
| I009 | Resolved | Initial BPF backend rejected return-valued atomics with default ISA | Explicit BPF v3 target; both programs compile for bpfel. Target verifier/load remains unverified. |
| I010 | Accepted development limitation | BPF cross-checks use minimal development type headers and declaration-only skeleton headers | They check syntax/target code generation and libbpf APIs; actual target BTF/CO-RE verification and linking must run on Linux. |
| I011 | Open | Final rebuilt Windows C checkers hit Windows Application Control error4551, including an authorized retry | Final test run explicitly skips these two native executions; 35 other checks pass. Eight compilation checks pass. Earlier native checks passed, but do not substitute for executing the latest rebuilt binaries. No security policy was changed. |
