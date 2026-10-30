"""Small real-kernel correctness test. A missing host is a failure, never a pass."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import signal
import tempfile
import time
import uuid

from analysis.wire import records
from analysis.validate import ledger
from .doctor import discover
from .trial import Child, _inventory
from .util import ROOT, host_lock, read_json, utc_now, write_json


def run_checks(c,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    result={"schema_version":1,"synthetic":False,"started":utc_now(),"passed":False,"checks":[],"blockers":[]}
    if platform.system()!="Linux":
        result["blockers"].append("real Linux BPF host unavailable")
        write_json(output/"checks.json",result,exclusive=True);return False
    host=discover()
    cpus=c["host"]["cpus"] or host.get("suggested_cpus")
    if not cpus or len(cpus)!=4:raise ValueError("four discovered CPU placements required")
    for name in ("agent","known_count","workload"):
        if not (ROOT/"build"/name).is_file():raise ValueError(f"build/{name} missing: make build first")
    before=_inventory()
    with host_lock(ROOT/"state/host.lock"):
        with tempfile.TemporaryDirectory(prefix="aet-check-",dir="/dev/shm") as staging:
            staging=Path(staging)
            for policy in ("FIX_LOW_GATE","FIX_HIGH","SENT"):
                case=output/policy;case.mkdir()
                commands=(case/"commands.jsonl").open("x",encoding="utf-8")
                children=[]
                try:
                    target=Child([ROOT/"build/known_count",1000,staging/f"input-{policy}",case/"per-call.csv"],case,"target",commands);children.append(target)
                    tid=target.message(5)["tid"]
                    (case/"targets.txt").write_text(f"{tid}\n")
                    values={"policy":policy,"period_ms":100,"dwell_ms":250,"grace_ms":20,"hysteresis":1,"supervisor":0,"stats":0,"component":0,"signal_total":0,
                            "cpu1":cpus[1],"cpu2":cpus[2],"isolated":0,"ring_bytes":8388608,"queue_bytes":8388608,"stage_bytes":8*1024*1024,
                            "median":0,"scale":.1,"high":12,"budget":.05,"rate_low":0,"rate_high":0}
                    (case/"runtime.conf").write_text("".join(f"{k} {v}\n" for k,v in values.items()))
                    agent=Child([ROOT/"build/agent",case,case/"targets.txt",case/"runtime.conf",staging/f"{policy}.bin"],case,"agent",commands);children.append(agent)
                    ready=agent.message(20)
                    clock_delta=time.monotonic_ns()-ready["monotonic_ns"]
                    target.send("GO");done=target.message(15)
                    if not done.get("done"):raise ValueError("known-count target did not finish")
                    # Known target parks; wait one poll period before detach/drain.
                    time.sleep(.2);agent.stop();target.send("STOP");target.process.wait(timeout=5)
                    counts=read_json(case/"counters.json")
                    values_=list(records(staging/f"{policy}.bin"))
                    expected=2000 if policy=="FIX_HIGH" else 0
                    ok=not ledger(counts) and counts["selected"]==expected and counts["completed"]==expected and len(values_)==expected and agent.process.returncode==0 and 0<=clock_delta<1_000_000_000
                    if policy=="FIX_HIGH":ok=ok and counts["eligible"]==2000 and {e.syscall_id for e,r in values_}=={17,202}
                    result["checks"].append({"policy":policy,"passed":ok,"expected_pairs":expected,"records":len(values_),"counts":counts,"clock_delta_ns":clock_delta})
                except (OSError,ValueError,RuntimeError) as exc:
                    result["blockers"].append(f"{policy}:{exc}")
                finally:
                    for ch in reversed(children):ch.stop()
                    commands.close()
    after=_inventory()
    result["before"]=before;result["after"]=after
    # Compare owned program IDs, allowing unrelated host instrumentation to change.
    def owned(inv):
        try:return {r["id"] for r in json.loads(inv["prog"]["stdout"]) if r.get("name") in ("sentinel_switch","detail_enter","detail_exit")}
        except (ValueError,KeyError):return None
    pre,post=owned(before),owned(after)
    result["cleanup_verified"]=pre is not None and post is not None and not (post-pre)
    result["passed"]=len(result["checks"])==3 and all(x["passed"] for x in result["checks"]) and not result["blockers"] and result["cleanup_verified"]
    write_json(output/"checks.json",result,exclusive=True)
    if result["passed"]:
        host["privileged_smoke_passed"]=True;host["functional_ready"]=True
        host["smoke_evidence"]=str(output/"checks.json")
        host["blockers"]=[b for b in host["blockers"] if "smoke" not in b]
        write_json(ROOT/"state/host.json",host)
    return result["passed"]
