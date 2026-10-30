"""Resolve a draft config from REAL discovery and an explicit calibration candidate."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import yaml
from runner.config import load_config
from runner.util import ROOT,digest,read_json,write_json

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--config",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--compute-repeats",type=int,required=True)
    a=p.parse_args();c=load_config(a.config);h=read_json(ROOT/"state/host.json")
    if h["system"]!="Linux" or not h.get("suggested_cpus") or len(h["suggested_cpus"])!=4:raise SystemExit("real Linux doctor with four physical cores required")
    if a.compute_repeats<1:raise SystemExit("positive calibration candidate required")
    c["host"].update(id=h.get("host_id"),kernel_lock=h["kernel"],cpus=h["suggested_cpus"],toolchain_lock="state/bootstrap/toolchain-actual.json")
    c["workload"]["compute_repeats"]=a.compute_repeats
    c["protocol"]["source_hashes"]={p:digest(ROOT/p) for p in ("context/plan.md","context/assignment.txt")}
    lock={"host":h["host"],"kernel":h["kernel"],"tools":h["tools"],"btf_sha256":digest("/sys/kernel/btf/vmlinux"),
          "generated":{str(p):digest(p) for p in (ROOT/"build").glob("*.skel.h")}}
    write_json(ROOT/"state/bootstrap/toolchain-actual.json",lock,exclusive=True)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x",encoding="utf-8") as stream:yaml.safe_dump(c,stream,sort_keys=False)
    print(a.output)
