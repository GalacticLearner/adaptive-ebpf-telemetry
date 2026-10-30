"""Preregistered representative selection; deterministic deployment fallback disclosed."""
from pathlib import Path
from runner.util import read_json
from .metrics import csv_rows,jsonl


def timeline(result,runs,plt,label):
    candidates=[r for r in result["comparisons"] if r["policy"]=="ADAPT_GATE" and r["phase"]==0]
    candidates.sort(key=lambda r:(r["scenario"].get("study")!="primary",r["scenario"].get("workload")!="cpu",
        r["scenario"].get("background")!="high",not r["scenario"].get("drift"),str(r["scenario"])))
    if not candidates:return None,{"reason":"no complete ADAPT_GATE block"}
    chosen=candidates[0]
    blocks=sorted(chosen["block_values"],key=lambda b:(1-b["policy_q"]/b["none_q"],b["block_id"]))
    block=blocks[(len(blocks)-1)//2]["block_id"]
    source=None
    for seal in result["input_hashes"]:
        path=Path(seal).parent
        if (path/"manifest.json").exists():
            m=read_json(path/"manifest.json")
            if m["trial"]["block_id"]==block and m["policy"]=="ADAPT_GATE":source=path;break
    if source is None:return None,{"reason":"original raw inputs unavailable"}
    truth=list(jsonl(source/"truth.jsonl"));epoch=next(t for t in truth if t["type"]=="epoch");start=epoch["start_ns"]
    ticks=csv_rows(source/"ticks.csv");app=csv_rows(source/"app.csv")
    fig,axes=plt.subplots(4,1,figsize=(11,8),sharex=True)
    for incident in (t for t in truth if t["type"]=="episode"):
        for ax in axes:ax.axvspan((incident["start_ns"]-start)/1e9,(incident["end_ns"]-start)/1e9,color="#dfb179",alpha=.4)
    xs=[(int(t["monotonic_ns"])-start)/1e9 for t in ticks]
    axes[0].plot(xs,[float(t["score"]) for t in ticks]);axes[0].set(ylabel="Sentinel score")
    for field in ("requested","applied"):axes[1].step(xs,[int(t[field]) for t in ticks],where="post",label=field)
    axes[1].set(ylabel="Mode");axes[1].legend(fontsize=8)
    if ticks and "reserve_failed" in ticks[0]:
        for field in ("reserve_failed","sink_drop"):axes[2].step(xs,[int(t[field]) for t in ticks],where="post",label=field)
        axes[2].legend(fontsize=8)
    else:axes[2].text(.02,.5,"Per-tick loss counters unavailable in this input version",transform=axes[2].transAxes)
    axes[2].set(ylabel="Loss counters")
    for worker in sorted({a["worker"] for a in app}):
        rows=sorted((a for a in app if a["worker"]==worker),key=lambda a:int(a["monotonic_ns"]))
        tx,ty=[],[]
        for a,b in zip(rows,rows[1:]):
            dt=(int(b["monotonic_ns"])-int(a["monotonic_ns"]))/1e9
            if dt>0:tx.append((int(b["monotonic_ns"])-start)/1e9);ty.append((int(b["successful"])-int(a["successful"]))/dt)
        axes[3].plot(tx,ty,label=f"worker{worker}")
    axes[3].set(ylabel="Units/s",xlabel="Measured time (s)");axes[3].legend(fontsize=8)
    fig.suptitle(label+f"Representative block {block}")
    return fig,{"block_id":block,"rule":"lower median ADAPT_GATE phase0 loss; prefer primary CPU/high/drift,then deterministic available deployment"}
