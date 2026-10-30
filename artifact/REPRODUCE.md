# Reproduction and current scope

This checkout was developed on Windows11/Python3.14.8. Windows has no installed WSL distribution. Portable tests and development C/BPF compilation checks were performed; no real Linux/eBPF workload,calibration,performance result or second-host replication is claimed. See `PROGRESS.md` and `state/evidence/`.

## Host readiness and quick smoke (under15min once dependencies are ready)

Use an otherwise idle authorized x86-64 Linux6.8+ host,preferably Ubuntu24.04 bare metal,with four physical cores,8GiB+ RAM,cgroupv2,readable BTF,and tracing privileges. A VM needs explicit contention/steal limits; WSL is only a development host if actual feature/load checks pass. Do not disable lockdown or replace kernels to force a pass.

```bash
bash artifact/bootstrap-linux.sh
sudo .venv/bin/python -m runner doctor --output state/host.json
.venv/bin/python tools/configure_host.py --config configs/calibration.yaml --output state/calibration-host.yaml --compute-repeats 32
sudo .venv/bin/python -m runner test --privileged --config state/calibration-host.yaml --output state/evidence/linux-smoke-001
.venv/bin/python -m runner test --unprivileged
```

`doctor` deliberately returns nonzero until real smoke is recorded. Bootstrap resolves exact Ubuntu package versions before installing,and builds checksummed libbpf1.5.1 under `.deps/`; it changes no kernel,boot or security setting. The quick real check requires exactly2,000 selected/completed/received pairs for1,000 pread64+futex iterations at q=1,and zero selections at q=0/SENT. A smoke success establishes basic function,not all race/performance gates.

The calibration candidate32 is an explicit starting value,not a measured work-unit calibration. Select/freeze CPU20–100us work units and the IO compute batch from actual calibration. No confirmatory config can retain unresolved fields.

## Calibration,pilot and freeze

Follow `CALIBRATION.md` in order. Normal training and validation are independent10-minute-or-longer populations for each workload/background; final incidents never tune thresholds. Freeze requires a clean source commit,a real smoke pass,resolved model paths,actual host/toolchain locks and a justified block count.

```bash
.venv/bin/python -m runner estimate-matrix --config state/final-draft.yaml --study all --output state/final-matrix.json
.venv/bin/python -m runner freeze --config state/final-draft.yaml --output state/freeze.json
```

Keep the frozen draft's original bytes. Create a separate resolved execution config with `protocol.preregistration_hash` from the freeze record; this avoids hashing the hash into itself. Execution config can live outside the tracked source tree so that the frozen source remains clean. Any other code/config/model change requires a new protocol amendment and new attempts.

## Canonical subset and full campaign

```bash
sudo .venv/bin/python -m runner pilot --config state/pilot-ready.yaml --study primary --output data/pilot/integration-001 --limit 14
sudo .venv/bin/python -m runner run --config /path/to/frozen-execution.yaml --study primary --output data/confirmatory/campaign-001
sudo .venv/bin/python -m runner run --config /path/to/frozen-execution.yaml --study supplementary --output data/robustness/supplementary-001
sudo .venv/bin/python -m runner run --config /path/to/frozen-execution.yaml --study robustness --output data/robustness/robustness-001
```

The complete primary matrix is672trials/54.1nominal host-hours. The current conservative registry including all new matched baselines,stats attribution and secondary-host subsets is2,188trials/~205.1host-hours before calibration/retries. These are scheduling estimates,not measurements. `estimate-matrix` recalculates after pilot N is frozen. Aggregate event-rate calibration must include helper bursts. Storage is checked for the full declared campaign plus20% headroom; preallocated per-trial staging also checks RAM,tmpfs and queue/map requirements. No default command launches a campaign.

Trials run serially under one host lock. Readiness/stop barriers maintain stable target TIDs. Every trial uses fresh owned processes,BPF objects/links and cgroups. Two infrastructure retries are allowed with new attempt IDs and the same intended schedule. Legitimate event loss,budget failure or missed incidents never trigger a retry. `--resume` verifies existing attempts rather than trusting old status text. One unavailable NONE reference prevents paired inference for that block. Secondary-host cells require an independently discovered/frozen host configuration with `host.role: secondary`; preserve the actual machine ID and freeze that host's models separately. Host-role routing never invents an identity.

## Analysis-only path

```bash
.venv/bin/python -m runner validate --input data/confirmatory/campaign-001 --output state/validation-001.json
.venv/bin/python -m runner analyze --input data/confirmatory/campaign-001 --output results/aet-v1/campaign-001 --figures
.venv/bin/python -m runner report --input results/aet-v1/campaign-001 --output paper/campaign-001
.venv/bin/python -m runner package --input data/confirmatory/campaign-001 --output artifact/releases
```

Every attempt's `seal.json` covers its entire raw file inventory. CRCs,restored archive hashes,schemas,clock order,truth and ledgers are checked before metrics. Failed attempts remain visible. The release tarball is read back against every file hash. Do not mix synthetic,calibration,pilot and confirmatory populations or incompatible protocol versions.

## Portable verification on Windows or Linux

```text
python -m venv .venv
<venv-python> -m pip install -r requirements-analysis.lock
<venv-python> -m runner test --unprivileged
<venv-python> tools/synthetic_fixture.py --output data/synthetic/replay-001
<venv-python> -m runner analyze --input data/synthetic/replay-001 --output data/synthetic/replay-001-analysis --figures
```

Compile `build/policy_replay` and `build/cost_check` on Linux with Make,or install development-only `ziglang==0.13.0` locally and compile their C sources on Windows. These enable actual C/reference comparison instead of skipped tests. Development BPF-target compilation with minimal type headers is explicitly not a CO-RE verifier/load pass.

## Cleanup and known failure modes

Closing owned FDs removes unpinned instrumentation after agent termination. Runner always terminates owned children,removes only its recorded cgroups and staging directory,and saves pre/post inventories. `cleanup` audits; it never globally kills processes or detaches someone else's BPF. Original governor,turbo,SMT and security settings are never changed by this implementation. Check per-attempt cleanup reports; a real forced-termination/race audit is still required before primary measurements.

Missing tracepoint permissions,BTF,cgroups,tools,storage,normal baselines or sparse calibration are explicit blockers. Unsupported ABIs fail. Excess loss is an outcome when its ledger reconciles; corrupt or unexplained accounting is invalid. Quantify harness/truth/histogram perturbation and application boundary interpolation resolution before interpreting small effects. Read the access matrix before making publication claims.
