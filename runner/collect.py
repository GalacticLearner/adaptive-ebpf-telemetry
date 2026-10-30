"""Explicit calibration acquisition; never an implicit default full campaign."""
from __future__ import annotations

import copy
import random
import time
from pathlib import Path

from .matrix import CORE
from .trial import execute
from .util import ROOT, canonical_hash, host_lock, seed_for, write_json,read_json


def collect(args,c):
    if not read_json(ROOT/"state/host.json").get("privileged_smoke_passed"):
        raise ValueError("real privileged smoke/count/cleanup gate must pass before calibration collection")
    if args.stage=="precision":raise ValueError("precision acquisition uses pilot; derive with --input pilot-effects.json")
    if c["protocol"]["population"]!="calibration":raise ValueError("--collect requires a calibration configuration")
    if c["workload"]["compute_repeats"] is None:raise ValueError("set an explicit calibration candidate compute_repeats before collection")
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
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    write_json(output/"collection.json",{"schema_version":1,"stage":args.stage,"split":args.split,"rows":rows},exclusive=True)
    with host_lock(ROOT/"state/host.lock"):
        for index,row in enumerate(rows):
            if args.limit is not None and index>=args.limit:break
            path,valid=execute(c,row,"calibration",output)
            row.update(status="valid" if valid else "failed",attempt=str(path))
            print(f"calibration:{row['trial_id']}:{row['status']}",flush=True)
            for _ in range(c["workload"]["cooldown_s"]):time.sleep(1)
    write_json(output/"collection-status.json",rows,exclusive=True)
    return {"output":str(output),"planned_trials":len(rows),"completed":sum(r["status"]!="planned" for r in rows)}
