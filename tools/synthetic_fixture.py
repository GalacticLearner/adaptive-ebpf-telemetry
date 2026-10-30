"""Generate tiny, explicitly synthetic attempts for a complete parser/inference replay."""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runner.config import load_config,config_hash
from runner.matrix import generate,schedule
from runner.util import ROOT,digest,git_state,utc_now,write_json
from analysis.wire import Event,write_records


def create(output,blocks=3):
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/"data/synthetic").resolve()):raise ValueError("synthetic fixtures must live under data/synthetic")
    output.mkdir(parents=True,exist_ok=False)
    c=load_config();c["protocol"]["population"]="synthetic";c["experiment"]["blocks"]=blocks
    rows=[r for r in generate(c,"primary") if r["scenario"]["workload"]=="cpu" and r["scenario"]["background"]=="low" and not r["scenario"]["drift"]]
    epoch=100_000_000_000
    for row in rows:
        path=output/row["trial_id"];path.mkdir();policy=row["policy"]
        write_json(path/"resolved_config.json",c,exclusive=True)
        write_json(path/"manifest.json",{"schema_version":1,"run_uuid":uuid.uuid4().hex,"population":"synthetic","synthetic":True,
            "protocol_version":"aet-v1","config_hash":config_hash(c),"code":git_state(),"trial":row,"host":{"id":"synthetic-fixture"},
            "policy":policy,"model_hashes":{},"clock":"CLOCK_MONOTONIC","stats_enabled":False,"start":utc_now(),"finish":utc_now(),"exit":0,"valid":True},exclusive=True)
        intended=schedule(c,row["seeds"]["episode"]);write_json(path/"intended_schedule.json",intended,exclusive=True)
        truth=[{"type":"epoch","start_ns":epoch,"end_ns":epoch+240_000_000_000,"clock":"CLOCK_MONOTONIC"}]
        events=[]
        for e in intended:
            start=epoch+e["offset_ns"];end=start+e["nominal_ms"]*1_000_000
            helpers=[{"role":f"futex{h}","tid":10+h,"first_ns":start+1000,"last_ns":end,"calls":2,"waits":1,"wakes":1,"errors":0,"interrupted":0,"checksum":1} for h in range(2)]
            truth.append({"type":"episode","episode_id":e["episode_id"],"kind":"futex","nominal_ms":e["nominal_ms"],"intended_ns":start,"start_ns":start,"end_ns":end,"eligible_calls":4,"valid":True,"helpers":helpers})
            if policy not in ("NONE","SENT","FIX_LOW_GATE"):
                count=4 if policy=="FIX_HIGH" else 2 if policy.startswith("ADAPT") else 1
                for i in range(count):
                    entry=start+1000+i*1000;exit_=entry+100
                    events.append((Event(1,0,1,entry,exit_,3,10+i%2,202,1,1,e["episode_id"]*4+i,0,1),exit_+100))
        (path/"truth.jsonl").write_text("".join(json.dumps(t)+"\n" for t in truth),encoding="utf-8")
        (path/"commands.jsonl").write_text(json.dumps({"synthetic":True})+"\n")
        write_json(path/"cleanup.json",{"children_exited":True,"owned_cgroups_removed":True,"staging_removed":True,"synthetic":True},exclusive=True)
        write_json(path/"validity.json",{"schema_version":1,"valid":True,"infrastructure_errors":[],"noise_flags":[]},exclusive=True)
        with (path/"app.csv").open("x",newline="") as f:
            writer=csv.writer(f);writer.writerow(["monotonic_ns","worker","phase","successful","attempted","short_reads","failed","checksum"])
            factor={"NONE":1,"SENT":.998,"FIX_LOW_GATE":.99,"FIX_MED":.975,"FIX_HIGH":.92,"ADAPT_GATE":.965,"ADAPT_SWITCH":.97}[policy]
            for worker in range(2):
                for second in range(-1,242):
                    n=round((second+1)*1000*factor)
                    writer.writerow([epoch+second*1_000_000_000,worker,0,n,n,0,0,17])
        if policy!="NONE":
            write_records(path/"detail.bin",events)
            n=len(events);eligible=56
            counts={k:0 for k in "eligible selected rejected insert_failed replaced malformed exit_without_selected completed reserve_failed emitted abandoned pending consumed sink_drop written undrained sink_bytes sink_flush_ns sink_error component".split()}
            counts.update(schema_version=1,eligible=eligible,selected=n,rejected=eligible-n,completed=n,emitted=n,consumed=n,written=n,sink_bytes=(path/"detail.bin").stat().st_size,ledger_ok=True,stats_enabled=False)
            write_json(path/"counters.json",counts,exclusive=True)
            (path/"bins.csv").write_text("absolute_bin,count,valid\n20000,1,1\n")
            (path/"transitions.jsonl").write_text("")
            with (path/"ticks.csv").open("x",newline="") as f:
                writer=csv.writer(f);writer.writerow(["monotonic_ns","first_bin","last_bin","count","score","gap","requested","allowed","applied","alert","alert_started"])
                for tenth in range(2400):
                    ns=epoch+tenth*100_000_000
                    state=any(epoch+e["offset_ns"]<=ns<epoch+e["offset_ns"]+700_000_000 for e in intended)
                    writer.writerow([ns,0,0,10,8 if state else 0,0,2 if state else 0,2,2 if state else 0,int(state),int(state)])
        write_json(path/"seal.json",{"schema_version":1,"sealed_at":utc_now(),"files":{str(p.relative_to(path)):digest(p) for p in path.iterdir() if p.is_file()}},exclusive=True)
    return output


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=ROOT/"data/synthetic"/f"fixture-{uuid.uuid4().hex[:8]}");p.add_argument("--blocks",type=int,default=3)
    args=p.parse_args();print(create(args.output,args.blocks))
