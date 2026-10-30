"""Preregistered host-noise flags; never invalidate loss/slowdown outcomes."""
from __future__ import annotations
from .metrics import csv_rows


def noise_flags(path,*,hz=100,target_cpus=2,steal_limit=.02,external_limit=.05,fraction=.10):
    rows=csv_rows(path);samples={}
    for row in rows:samples.setdefault(int(row["monotonic_ns"]),{})[row["role"]]=row
    previous=None;bad=intervals=0;steal_ticks=total_ticks=0
    for ns,roles in sorted(samples.items()):
        row=next(iter(roles.values()));raw=[int(x) for x in row["host_cpu"].split()[1:9]]
        if len(raw)!=8:raise ValueError("resource host CPU sample malformed")
        busy=sum(raw)-raw[3]-raw[4]
        owned=sum(int(r["utime_ticks"] or 0)+int(r["stime_ticks"] or 0) for r in roles.values())
        if previous:
            last_ns,last_busy,last_owned,last_steal,last_total=previous
            elapsed=(ns-last_ns)/1e9
            if elapsed>0:
                capacity=hz*target_cpus*elapsed
                external=max(0,(busy-last_busy)-(owned-last_owned))/capacity
                bad+=external>external_limit;intervals+=1
                steal_ticks+=max(0,raw[7]-last_steal);total_ticks+=max(0,sum(raw)-last_total)
        previous=(ns,busy,owned,raw[7],sum(raw))
    flags=[]
    if intervals and bad/intervals>fraction:flags.append("external_cpu_above_preregistered_threshold")
    if total_ticks and steal_ticks/total_ticks>steal_limit:flags.append("mean_steal_above_preregistered_threshold")
    return {"flags":flags,"intervals":intervals,"external_bad_fraction":bad/intervals if intervals else None,
            "mean_steal_fraction":steal_ticks/total_ticks if total_ticks else None,
            "assumption":"global host busy minus owned process CPU; target-core capacity normalizer; conservative host-noise proxy"}
