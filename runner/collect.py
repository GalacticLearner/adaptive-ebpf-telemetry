"""Explicit calibration acquisition; never an implicit default full campaign."""
from __future__ import annotations

import copy
import random
import time
from pathlib import Path

from .matrix import CORE
from .trial import execute
from .util import ROOT, canonical_hash, host_lock, seed_for, write_json,read_json


def select_rate_rows(rows, limit, include_io=False):
    if limit is None:
        return rows
    if not include_io:
        return rows[:limit]
    if limit < 4:
        raise ValueError("--include-io requires --limit of at least 4 for CPU/I/O NONE and FIX_LOW_GATE pairs")
    selected = []
    for family, policy in (("cpu", "NONE"), ("cpu", "FIX_LOW_GATE"), ("io", "NONE"), ("io", "FIX_LOW_GATE")):
        row = next((r for r in rows if r["scenario"]["workload"] == family and
                    r["scenario"]["background"] == "low" and r["block_id"].endswith("b000") and
                    r["policy"] == policy), None)
        if row is None:
            raise ValueError(f"no low-background block-zero row for {family}/{policy}")
        selected.append(row)
    if len(selected) < limit:
        remaining = [r for r in rows if r not in selected]
        selected.extend(remaining[:limit - len(selected)])
    return selected[:limit]


def collect(args,c):
    if not read_json(ROOT/"state/host.json").get("privileged_smoke_passed"):
        raise ValueError("real privileged smoke/count/cleanup gate must pass before calibration collection")
    if args.stage=="precision":raise ValueError("precision acquisition uses pilot; derive with --input pilot-effects.json")
    if c["protocol"]["population"]!="calibration":raise ValueError("--collect requires a calibration configuration")
    if c["workload"]["compute_repeats"] is None:raise ValueError("set an explicit calibration candidate compute_repeats before collection")
    if args.include_io and args.stage!="rate":raise ValueError("--include-io is supported only for rate calibration")
    output=args.output or ROOT/"data/calibration"/f"{args.stage}-{args.split}"
    rows=[]
    for family in ("cpu","io"):
        for background in ("low","high"):
            for block in range(8):
                bid=f"cal-{args.stage}-{args.split}-{family}-{background}-b{block:03}"
                policies=("SENT",) if args.stage=="normal" else ("NONE",) if args.stage=="perturbation" else ("NONE","SENT","FIX_LOW_GATE","FIX_MED","FIX_HIGH")
                order=list(policies);random.Random(seed_for(100000,"order",bid)).shuffle(order)
                for position,policy in enumerate(order):
                    scenario={"study":f"calibration-{args.stage}","workload":family,"background":background,"drift":args.stage=="cost",
                              "kind":"none" if args.stage=="normal" else "futex", "measure_s":600 if args.stage=="normal" else 240,
                              "split":args.split}
                    rows.append({"cell_id":f"{bid.rsplit('-b',1)[0]}-{policy}","block_id":bid,"trial_id":f"{bid}-{policy}","position":position,
                                 "policy":policy,"scenario":scenario,"seeds":{k:seed_for(100000,k,bid) for k in ("workload","episode")},
                                 "baseline_trial":f"{bid}-NONE" if "NONE" in policies else None,"status":"planned"})
    if args.stage=="perturbation":
        expanded=[]
        for row in rows:
            for variant,options in (("standard",{}),("no_resources",{"resource_sampling":False}),
                                    ("no_truth",{"truth_aggregation":False}),("histogram",{"sample_units_every":100})):
                candidate=copy.deepcopy(row);candidate["trial_id"]+=f"-{variant}";candidate["scenario"].update(options,variant=variant)
                expanded.append(candidate)
        rows=expanded
    run_rows=select_rate_rows(rows,args.limit,args.include_io)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write_json(output/"collection.json",{"schema_version":1,"stage":args.stage,"split":args.split,"rows":rows},exclusive=True)
    with host_lock(ROOT/"state/host.lock"):
        for row in run_rows:
            path,valid=execute(c,row,"calibration",output)
            row.update(status="valid" if valid else "failed",attempt=str(path))
            print(f"calibration:{row['trial_id']}:{row['status']}",flush=True)
            for _ in range(c["workload"]["cooldown_s"]):time.sleep(1)
    write_json(output/"collection-status.json",rows,exclusive=True)
    return {"output":str(output),"planned_trials":len(rows),"completed":sum(r["status"]!="planned" for r in rows)}
