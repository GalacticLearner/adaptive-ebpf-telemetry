from __future__ import annotations

import json
from pathlib import Path
import time
import shutil

from analysis.pipeline import find_attempts
from analysis.validate import validate_attempt
from .matrix import estimate, generate
from .trial import execute
from .util import canonical_hash, host_lock, read_json, utc_now, write_json


def run_campaign(c, output, *, study="primary", population="confirmatory", resume=False, limit=None):
    output=Path(output)
    rows=generate(c,study)
    estimate_=estimate(c,rows)
    if estimate_["rate_is_calibrated"] is False and any(r["policy"]!="NONE" for r in rows):
        raise ValueError("calibrate aggregate peak event rate before experiments")
    output.mkdir(parents=True,exist_ok=True)
    registry=output/"campaign.json"
    if registry.exists():
        if not resume:raise ValueError("campaign exists; use --resume")
        saved=read_json(registry)
        if saved["matrix_hash"]!=canonical_hash(rows):raise ValueError("matrix/config changed; new protocol/campaign required")
    else:
        saved={"schema_version":1,"created":utc_now(),"matrix_hash":canonical_hash(rows),"estimate":estimate_,"rows":rows}
        write_json(registry,saved,exclusive=True)
    completed=0
    batch_start=time.monotonic()
    if shutil.disk_usage(output).free < estimate_["bytes_with_headroom"]:
        raise ValueError("full campaign archive storage/headroom guard failed; provision capacity or amend/calibrate protocol before freeze")
    from .util import ROOT
    with host_lock(ROOT/"state/host.lock"):
        for row in saved["rows"]:
            if limit is not None and completed>=limit:break
            assigned=row["scenario"].get("host","primary")
            if assigned!=c["host"].get("role","primary"):
                row["status"]="blocked";row["blocker"]=f"assigned to {assigned} host role; preserve actual discovered machine ID";continue
            prior=[]
            for p in find_attempts(output):
                m=read_json(p/"manifest.json")
                if m["trial"]["trial_id"]==row["trial_id"]:prior.append(p)
            if any(validate_attempt(p)["valid"] for p in prior):
                row["status"]="valid";continue
            if len(prior)>c["experiment"]["retries"]:
                row["status"]="failed";continue
            for _ in range(len(prior),c["experiment"]["retries"]+1):
                attempt,valid=execute(c,row,population,output)
                row.setdefault("attempts",[]).append({"path":str(attempt),"valid":valid})
                print(json.dumps({"trial":row["trial_id"],"attempt":str(attempt),"valid":valid,"at":utc_now()}),flush=True)
                # Loss/overhead/misses are valid outcomes and never trigger retries.
                if valid:row["status"]="valid";break
                row["status"]="failed"
            completed+=1
            write_json(registry,saved)
            # A fixed cooldown is applied to all treatments and retries.
            remaining=c["workload"]["cooldown_s"]
            while remaining>0:
                delay=min(remaining,1);time.sleep(delay);remaining-=delay
            if time.monotonic()-batch_start>=c["experiment"]["max_batch_hours"]*3600:
                print(json.dumps({"checkpoint":"batch boundary","completed_this_batch":completed}),flush=True)
                batch_start=time.monotonic()
    write_json(registry,saved)
    return saved
