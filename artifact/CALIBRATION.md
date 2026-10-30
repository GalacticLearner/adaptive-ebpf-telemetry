# Calibration acquisition and phase gates

All collection requires the real-host correctness gate. Source implementation is insufficient. Keep acquisitions immutable and preserve failed attempts. Calibration and experiments share one host lock.

1. **P2/P5 workload/rate selection:** configure an explicit repeat-count candidate with `tools/configure_host.py`. Run `calibrate --collect --stage rate --config state/calibration-host.yaml --output data/calibration/rate-candidate-001`. It collects randomized NONE/SENT/fixed-mode blocks for both families/backgrounds. Inspect sparse work-unit histograms and completed-work/eligible-entry rates. Try new configs/namespaces until CPU units are 20–100us and IO normal eligible entries are at most 50,000/s. The current shared repeat count applies to both families; if one host cannot satisfy both constraints, document a protocol/implementation amendment before freeze. Never adapt the batch within a measured trial.
2. **Storage/sink feasibility:** `calibrate --stage rate --input data/calibration/rate-candidate-001 --output state/calibration/rates-001.json` derives observed averages. Whole-run averages do not bound helper-burst peaks. Peak remains unresolved until sustained q=1 sink and helper-burst tests bound complete staged output plus 20% headroom. Resolve `calibrated_peak_rate` and `sink_bytes_per_second` from actual evidence. Transport costs 72 bytes/event plus headers, not only the 64-byte event.
3. **Measurement perturbation:** run `calibrate --collect --stage perturbation` for eight paired NONE blocks per family/background, each with standard, no-resource-sampler, no-helper-counter and histogram variants. Derive `calibrate --stage perturbation --input <directory>`. Calibration-only switches retain independent boundaries while disabling helper count/checksum aggregation, so capture is N/A for that variant. Save effects, timing and cleanup evidence. No setting is labeled least intrusive without measurements.
4. **Normal detector data:** independently collect training and validation, at least ten observed minutes per workload/background:

```bash
sudo .venv/bin/python -m runner calibrate --collect --stage normal --split training --config state/calibration-host.yaml --output data/calibration/normal-training-001
sudo .venv/bin/python -m runner calibrate --collect --stage normal --split validation --config state/calibration-host.yaml --output data/calibration/normal-validation-001
.venv/bin/python -m runner calibrate --stage normal --config state/calibration-host.yaml --input data/calibration/normal-training-001 --validation data/calibration/normal-validation-001 --output state/calibration/detector.json
```

Initial SENT-only acquisition may use the explicit bootstrap detector (median0, scale0.1, h12); it cannot control detail links or freeze as trained evidence. Training derives both 5ms-max and separately calibrated 100ms-total references. Select h only using the prescribed normal-validation candidates; preserve unmet false-alarm targets.

5. **Context/action table:** add the detector path to a new calibration config. Collect `calibrate --collect --stage cost ...`, then derive `calibrate --stage cost --input <attempt-directory> --output state/calibration/cost.json`. At least eight independent blocks are required. Fixed MED/HIGH steady-path reuse across mechanism labels is explicit. Dedicated transition CPU/timing still requires collection; unidentifiable throughput conversion remains `transition_cost_unresolved`, never zero.
6. **Attribution:** run stats-off/on empty/filter/pair/export/shadow subsets through the same harness. Quantify stats perturbation separately. Primary manifests prohibit runtime stats.
7. **Precision pilot:** resolve models and run eight primary pilot blocks. `calibrate --stage precision --input <pilot-directory> --output state/calibration/precision.json` selects minimum12/cap30 from independent block variance. Preserve timing/noise/dependence evidence.
8. **Freeze:** resolve actual host/model/workload/storage/noise values and N, commit code/protocol/models/analysis, then freeze. Infeasible budgets remain outcomes. Storage shortages, unverified races and unreconciled accounting remain blockers. Rebuilding after bootstrap must preserve `PKG_CONFIG_PATH="$PWD/.deps/libbpf-1.5.1/lib/pkgconfig"` and `CLANG=clang-18` so a distribution libbpf is not silently substituted.

`--collect` is explicit and can be expensive; `--dry-run` starts no work. The plan's phase gates remain authoritative, including Linux checks not yet performed.
