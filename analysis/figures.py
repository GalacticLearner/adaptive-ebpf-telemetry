from __future__ import annotations

from pathlib import Path
import statistics
import copy

from runner.util import canonical_hash, digest, read_json, write_json
from .stats import bootstrap_blocks
from .metrics import csv_rows


def render(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output=Path(output)
    result=read_json(output/"results.json")
    runs=read_json(output/"run_metrics.json")
    scenarios={canonical_hash(r["trial"]["scenario"]) for r in runs}
    if len(scenarios)>1:
        inventory=[]
        for scenario in sorted(scenarios):
            child=output/f"condition-{scenario[:12]}";child.mkdir(exist_ok=False)
            subset=copy.deepcopy(result)
            subset["comparisons"]=[r for r in result["comparisons"] if canonical_hash(r["scenario"])==scenario]
            write_json(child/"results.json",subset,exclusive=True)
            write_json(child/"run_metrics.json",[r for r in runs if canonical_hash(r["trial"]["scenario"])==scenario],exclusive=True)
            if (output/"model_error.csv").exists():
                import csv
                with (child/"model_error.csv").open("x",newline="",encoding="utf-8") as stream:
                    values=[r for r in csv_rows(output/"model_error.csv") if r["scenario_hash"]==scenario]
                    fields=["block_id","policy","phase","scenario_hash","mean_prediction_ucl","measured_block_loss","error","tick_count"]
                    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(values)
            inventory.extend({**p,"directory":str(child)} for p in render(child))
        write_json(output/"figure_inventory.json",inventory,exclusive=True)
        return inventory
    label="SYNTHETIC VERIFICATION — " if result["synthetic"] else ""
    plots=[]
    def save(fig,name):
        fig.tight_layout()
        for ext in ("pdf","svg","png"):
            fig.savefig(output/f"{name}.{ext}",dpi=160)
        plt.close(fig);plots.append({"figure":name,"status":"generated","inputs":result["input_hashes"],
            "files":{f"{name}.{ext}":digest(output/f"{name}.{ext}") for ext in ("pdf","svg","png")}})
    fig,ax=plt.subplots(figsize=(8,5))
    for r in result["comparisons"]:
        if not r["capture"]:continue
        l,c=r["throughput_loss"],r["capture"]
        ax.errorbar(100*l["estimate"],c["estimate"],xerr=[[100*(l["estimate"]-l["ci_low"])],[100*(l["ci_high"]-l["estimate"])]],
            yerr=[[c["estimate"]-c["ci_low"]],[c["ci_high"]-c["estimate"]]],fmt="o",label=f"{r['policy']} / {r['scenario']['workload']} / phase {r['phase']}")
    ax.set(xlabel="Application throughput loss (%)",ylabel="Common-cutoff incident capture",title=label+"Impact–capture frontier")
    if len(result["comparisons"])<=12:ax.legend(fontsize=7)
    save(fig,"frontier")
    for name,field,ylabel in (("duration_capture","common_capture","Common-cutoff capture"),("duration_recall","on_time","On-time recall")):
        fig,ax=plt.subplots(figsize=(8,5))
        for policy in sorted({r["policy"] for r in runs if r["policy"]!="NONE"}):
            points={}
            for run in runs:
                if run["policy"]!=policy:continue
                block={}
                for e in run["episodes"]:
                    if e["valid"] and e[field] is not None:block.setdefault(e["nominal_ms"],[]).append((e["actual_ms"],e[field]))
                for nominal,episodes in block.items():
                    points.setdefault(nominal,[]).append((statistics.mean(x for x,y in episodes),statistics.mean(y for x,y in episodes)))
            summaries=[bootstrap_blocks([y for x,y in points[k]]) for k in sorted(points)]
            ax.errorbar([statistics.mean(x for x,y in points[k]) for k in sorted(points)],
                    [s["estimate"] for s in summaries],yerr=[[max(0,s["estimate"]-s["ci_low"]) for s in summaries],
                    [max(0,s["ci_high"]-s["estimate"]) for s in summaries]],fmt="o-",capsize=3,label=policy)
        ax.set(xscale="log",xlabel="Mean actual incident duration (ms)",ylabel=ylabel,title=label+"Duration sensitivity (whole-block intervals)")
        ax.legend(fontsize=7);save(fig,name)
    fig,ax=plt.subplots(figsize=(8,5));lossfields=["rejected","insert_failed","reserve_failed","sink_drop","abandoned","undrained"]
    available=[r for r in runs if r["counters"]]
    bypolicy={p:[r for r in available if r["policy"]==p] for p in sorted({r["policy"] for r in available})}
    bottom=[0.0]*len(bypolicy)
    for field in lossfields:
        vals=[statistics.mean(r["counters"][field] for r in rs) for rs in bypolicy.values()]
        ax.bar(list(bypolicy),vals,bottom=bottom,label=field);bottom=[a+b for a,b in zip(bottom,vals)]
    ax.set(ylabel="Mean records/calls per run (separate categories)",title=label+"Sampling and loss ledger");ax.tick_params(axis="x",rotation=30);ax.legend(fontsize=7)
    save(fig,"loss")
    fig,axes=plt.subplots(1,2,figsize=(10,4));names=list(bypolicy)
    axes[0].bar(names,[statistics.mean(r["mode_changes_per_min"] for r in bypolicy[p]) for p in names]);axes[0].set(ylabel="Mode changes/min")
    axes[1].bar(names,[statistics.mean(r["occupancy"]["2"] or 0 for r in bypolicy[p]) for p in names]);axes[1].set(ylabel="HIGH occupancy")
    for ax in axes:ax.tick_params(axis="x",rotation=40)
    fig.suptitle(label+"Controller stability (descriptive means)");save(fig,"stability")
    fig,ax=plt.subplots(figsize=(8,5))
    grid=[0,1,5,10,25,50,100,250,500,1000,1500]
    for policy in sorted({r["policy"] for r in runs if r["policy"]!="NONE"}):
        blocks=[r for r in runs if r["policy"]==policy]
        ys=[]
        for delay in grid:
            rates=[]
            for run in blocks:
                episodes=[e for e in run["episodes"] if e["valid"]]
                if episodes:rates.append(sum(e["alert_delay_ns"] is not None and e["alert_delay_ns"]<=delay*1e6 for e in episodes)/len(episodes))
            ys.append(statistics.mean(rates) if rates else 0)
        ax.step(grid,ys,where="post",label=policy)
    ax.set(xlabel="Onset to alert (ms)",ylabel="Fraction of all valid incidents detected by delay",ylim=(0,1.02),title=label+"Delay including missed incidents")
    ax.legend(fontsize=7);save(fig,"delay_cdf")
    from .timeline import timeline
    figure,metadata=timeline(result,runs,plt,label)
    if figure is not None:save(figure,"timeline");plots[-1].update(metadata)
    else:plots.append({"figure":"timeline","status":"blocked","reason":metadata["reason"]})
    model=csv_rows(output/"model_error.csv") if (output/"model_error.csv").exists() else []
    if model:
        fig,ax=plt.subplots(figsize=(7,5))
        for policy in sorted({r["policy"] for r in model}):
            rows=[r for r in model if r["policy"]==policy]
            ax.scatter([100*float(r["mean_prediction_ucl"]) for r in rows],[100*float(r["measured_block_loss"]) for r in rows],label=policy)
        ax.set(xlabel="Phase mean calibrated prediction UCL (%)",ylabel="Paired block phase loss (%)",title=label+"Frozen-model error; uncertainty in model_error_summary.json")
        ax.legend(fontsize=8);save(fig,"model_error")
    else:plots.append({"figure":"model_error","status":"blocked","reason":"no independent calibration predictions"})
    attribution=[r for r in result["comparisons"] if r["scenario"]["study"].startswith(("attribution","isolated","second_host"))]
    if attribution:
        fig,ax=plt.subplots(figsize=(10,5))
        for index,row in enumerate(attribution):
            effect=row["throughput_loss"]
            ax.errorbar(index,100*effect["estimate"],yerr=[[100*max(0,effect["estimate"]-effect["ci_low"])] ,[100*max(0,effect["ci_high"]-effect["estimate"])]],fmt="o")
        ax.set(xticks=range(len(attribution)),xticklabels=[f"{r['policy']}/p{r['phase']}" for r in attribution],ylabel="Throughput loss (%)",title=label+"Attribution/host/placement: separate condition")
        ax.tick_params(axis="x",rotation=40);save(fig,"attribution_robustness")
    else:plots.append({"figure":"attribution_robustness","status":"blocked","reason":"no validated attribution/host/placement cells"})
    write_json(output/"figure_inventory.json",plots,exclusive=True)
    return plots
