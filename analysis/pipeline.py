from __future__ import annotations

import csv
import math
from pathlib import Path
import statistics

from .metrics import measure_attempt
from .metrics import csv_rows,jsonl
from .stats import bootstrap_blocks, paired_throughput
from .validate import schema, validate_attempt
from runner.util import canonical_hash, digest, read_json, utc_now, write_json


def find_attempts(source):
    source = Path(source)
    return [source] if (source / "manifest.json").is_file() else sorted(p.parent for p in source.rglob("manifest.json") if (p.parent / "resolved_config.json").exists())


def analyze(source, output, cfg):
    paths = find_attempts(source)
    if not paths:
        raise ValueError("no attempt records; calibration/synthetic fixtures are not empirical results")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("derived output already exists; choose a new output namespace")
    output.mkdir(parents=True, exist_ok=True)
    checked = [validate_attempt(p) for p in paths]
    valid = [p for p, v in zip(paths, checked) if v["valid"]]
    if not valid:
        write_json(output / "validation.json", checked)
        raise ValueError("no validated attempts; inspect validation.json")
    manifests = [read_json(p / "manifest.json") for p in valid]
    synthetic = {m["synthetic"] for m in manifests}
    populations = {m["population"] for m in manifests}
    protocols = {m["protocol_version"] for m in manifests}
    if len(synthetic) != 1 or len(populations) != 1 or len(protocols) != 1:
        raise ValueError("cannot pool synthetic/real, calibration/final, or incompatible protocols")
    # Retain all attempts; select first valid by creation time, never best outcome.
    ordered = sorted(zip(valid, manifests), key=lambda x: (x[1]["start"], x[0].name))
    first = {}
    duplicate = []
    for path, m in ordered:
        tid = m["trial"]["trial_id"]
        if tid not in first:
            first[tid] = path
        else:
            duplicate.append({"path": str(path), "reason": "later valid attempt excluded by preregistered first-valid rule"})
    measures = [measure_attempt(p) for p in first.values()]
    blocks = {}
    for record in measures:
        blocks.setdefault(record["trial"]["block_id"], {})[record["policy"]] = record
    groups = {}
    missing = []
    for bid, policies in blocks.items():
        for policy, record in policies.items():
            if policy == "NONE":
                continue
            scenario = record["trial"]["scenario"]
            if "NONE" not in policies:
                # Quiet false alarms need no throughput baseline; disclose omitted impact.
                missing.append({"block": bid, "policy": policy, "missing": "NONE", "impact_unavailable": True})
                continue
            control = policies["NONE"]
            if scenario != control["trial"]["scenario"] or record["trial"]["seeds"] != control["trial"]["seeds"]:
                raise ValueError("mismatched control scenario/schedule seed")
            for phase in record["phases"]:
                reference = next(p for p in control["phases"] if p["phase"] == phase["phase"])
                key = (canonical_hash(scenario), policy, phase["phase"])
                group = groups.setdefault(key, {"scenario": scenario, "policy": policy, "phase": phase["phase"], "blocks": []})
                episodes = [e for e in record["episodes"] if e["valid"] and e["phase"] == phase["phase"]]
                captures = [e["common_capture"] for e in episodes if e["common_capture"] is not None]
                recalls = [e["on_time"] for e in episodes if e["on_time"] is not None]
                group["blocks"].append({"block_id": bid, "policy_q": phase["units_per_s"], "none_q": reference["units_per_s"],
                    "noise_flagged_block":any(r["noise_flags"] for r in policies.values()),
                    "capture": statistics.mean(captures) if captures else None,
                    "on_time_recall": statistics.mean(recalls) if recalls else None,
                    "episodes": len(episodes), "max_boundary_resolution_ns": max(phase["boundary_resolution_ns"], reference["boundary_resolution_ns"])})
    comparisons = []
    kwargs = {"draws": cfg["analysis"]["bootstrap_draws"], "seed": cfg["analysis"]["bootstrap_seed"]}
    for group in groups.values():
        blocks_ = group.pop("blocks")
        impact = paired_throughput([b["policy_q"] for b in blocks_], [b["none_q"] for b in blocks_], budget=group["scenario"].get("budget", cfg["controller"]["budget"]), **kwargs)
        capture = [b["capture"] for b in blocks_ if b["capture"] is not None]
        recall = [b["on_time_recall"] for b in blocks_ if b["on_time_recall"] is not None]
        comparisons.append({**group, "throughput_loss": impact,
             "without_noise_flagged_blocks":paired_throughput([b["policy_q"] for b in blocks_ if not b["noise_flagged_block"]],
                 [b["none_q"] for b in blocks_ if not b["noise_flagged_block"]],budget=group["scenario"].get("budget",cfg["controller"]["budget"]),**kwargs)
                 if any(not b["noise_flagged_block"] for b in blocks_) else None,
             "capture": bootstrap_blocks(capture, **kwargs) if capture else None,
             "on_time_recall": bootstrap_blocks(recall, **kwargs) if recall else None,
             "block_values": blocks_, "source_calls": "see per-episode table; block rates unweighted"})
    direct = []
    pairs = {}
    for bid, p in blocks.items():
        if "ADAPT_GATE" not in p or "ADAPT_SWITCH" not in p:
            continue
        gate, switch = p["ADAPT_GATE"], p["ADAPT_SWITCH"]
        sid = canonical_hash(gate["trial"]["scenario"])
        for phase in gate["phases"]:
            other = next(s for s in switch["phases"] if s["phase"] == phase["phase"])
            capture = lambda r: [e["common_capture"] for e in r["episodes"] if e["valid"] and e["phase"] == phase["phase"] and e["common_capture"] is not None]
            gc, sc = capture(gate), capture(switch)
            pairs.setdefault((sid, phase["phase"]), []).append({"block_id": bid,
                "log_ratio": math.log(phase["units_per_s"] / other["units_per_s"]),
                "capture_difference": statistics.mean(gc) - statistics.mean(sc) if gc and sc else None})
    for (sid, phase), pair in pairs.items():
        diffs = [v["capture_difference"] for v in pair if v["capture_difference"] is not None]
        direct.append({"scenario_hash": sid, "phase": phase, "comparison": "ADAPT_GATE minus ADAPT_SWITCH",
             "relative_throughput_loss": bootstrap_blocks([p["log_ratio"] for p in pair], transform=lambda x: 1-math.exp(x), **kwargs),
             "capture_difference": bootstrap_blocks(diffs, **kwargs) if diffs else None})
    result = {"schema_version": 1, "protocol_version": next(iter(protocols)), "synthetic": next(iter(synthetic)),
              "input_hashes": {(p / "seal.json").as_posix(): digest(p / "seal.json") for p in paths if (p / "seal.json").exists()},
              "attempts": checked + duplicate, "comparisons": comparisons, "missing": missing,
              "hypotheses": {h: {"decision": "inconclusive", "reason": "synthetic verification only" if next(iter(synthetic)) else "requires scoped scientific review against fixed frontier, precision and robustness inventory"} for h in ("H1", "H2", "H3", "H4")}}
    schema(result, "results")
    write_json(output / "results.json", result, exclusive=True)
    write_json(output / "mechanism_comparisons.json", direct, exclusive=True)
    write_json(output / "run_metrics.json", measures, exclusive=True)
    write_json(output / "validation.json", checked, exclusive=True)
    model_rows=[]
    for path in first.values():
        m=read_json(path/"manifest.json");bid=m["trial"]["block_id"]
        if not m["policy"].startswith("ADAPT") or "NONE" not in blocks[bid] or not (path/"ticks.csv").exists():continue
        ticks=csv_rows(path/"ticks.csv");config=read_json(path/"resolved_config.json")
        epoch=next(t for t in jsonl(path/"truth.jsonl") if t["type"]=="epoch")
        for phase in blocks[bid][m["policy"]]["phases"]:
            boundary=epoch["start_ns"]+int(config["workload"]["drift_at_s"]*1e9)
            lo=epoch["start_ns"] if phase["phase"]==0 else boundary
            hi=boundary if config["workload"]["drift"] and phase["phase"]==0 else epoch["end_ns"]
            values=[float(t["prediction"]) for t in ticks if lo<=int(t["monotonic_ns"])<hi and t.get("prediction") and math.isfinite(float(t["prediction"]))]
            if not values:continue
            none=next(p for p in blocks[bid]["NONE"]["phases"] if p["phase"]==phase["phase"])
            measured=1-phase["units_per_s"]/none["units_per_s"]
            model_rows.append({"block_id":bid,"policy":m["policy"],"phase":phase["phase"],"scenario_hash":canonical_hash(m["trial"]["scenario"]),
                               "mean_prediction_ucl":statistics.mean(values),"measured_block_loss":measured,
                               "error":statistics.mean(values)-measured,"tick_count":len(values)})
    with (output/"model_error.csv").open("x",newline="",encoding="utf-8") as f:
        fields=["block_id","policy","phase","scenario_hash","mean_prediction_ucl","measured_block_loss","error","tick_count"]
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(model_rows)
    model_groups={}
    for row in model_rows:model_groups.setdefault((row["scenario_hash"],row["policy"],row["phase"]),[]).append(row["error"])
    write_json(output/"model_error_summary.json",[{"scenario_hash":key[0],"policy":key[1],"phase":key[2],"error":bootstrap_blocks(values,**kwargs)} for key,values in model_groups.items()],exclusive=True)
    required={"NONE","SENT","FIX_LOW_GATE","FIX_MED","FIX_HIGH","ADAPT_GATE","ADAPT_SWITCH"}
    baseline_audit=[]
    for scenario in {canonical_hash(r["trial"]["scenario"]) for r in measures}:
        policies={r["policy"] for r in measures if canonical_hash(r["trial"]["scenario"])==scenario}
        baseline_audit.append({"scenario_hash":scenario,"present":sorted(policies),"missing_core":sorted(required-policies),
                               "fixed_frontier_complete":required.issubset(policies),"q_frontier_present":all(p in policies for p in ("FIX_Q01","FIX_Q50"))})
    write_json(output/"baseline_audit.json",baseline_audit,exclusive=True)
    with (output / "effects.csv").open("x", newline="", encoding="utf-8") as f:
        writer=csv.writer(f);writer.writerow(["study","workload","background","drift","policy","phase","blocks","loss","ci_low","ci_high","compliance","capture","capture_low","capture_high"])
        for r in comparisons:
            s=r["scenario"];l=r["throughput_loss"];c=r["capture"] or {}
            writer.writerow([s["study"],s["workload"],s["background"],s["drift"],r["policy"],r["phase"],l["blocks"],l["estimate"],l["ci_low"],l["ci_high"],l["compliance"],c.get("estimate"),c.get("ci_low"),c.get("ci_high")])
    return result
