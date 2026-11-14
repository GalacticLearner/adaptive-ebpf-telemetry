"""One fresh Linux process/map population per immutable attempt."""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
from pathlib import Path
import platform
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid

from .config import config_hash, resolve
from .doctor import discover
from .matrix import schedule
from .util import ROOT, canonical_hash, command, digest, git_state, read_json, utc_now, write_json


class TrialFailure(RuntimeError):
    pass


class Child:
    def __init__(self, argv, output, name, commands):
        self.name = name
        self.lines = queue.Queue()
        self.out = (output / f"{name}.stdout.log").open("x", encoding="utf-8")
        self.err = (output / f"{name}.stderr.log").open("x", encoding="utf-8")
        self.process = subprocess.Popen([str(a) for a in argv], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.err, text=True, bufsize=1, start_new_session=True)
        commands.write(json.dumps({"at": utc_now(), "argv": [str(a) for a in argv], "pid": self.process.pid}) + "\n")
        commands.flush()
        def reader():
            for line in self.process.stdout:
                self.out.write(line)
                self.out.flush()
                self.lines.put(line)
            self.lines.put(None)
        self.reader = threading.Thread(target=reader, daemon=True)
        self.reader.start()

    def message(self, timeout):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty as exc:
            raise TrialFailure(f"{self.name}: readiness/stop timeout") from exc
        if line is None:
            raise TrialFailure(f"{self.name}: unexpected exit {self.process.poll()}")
        return json.loads(line)

    def send(self, text):
        self.process.stdin.write(text + "\n")
        self.process.stdin.flush()

    def stop(self, grace=5):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        self.process.stdout.close()
        self.process.stdin.close()
        self.out.close()
        self.err.close()


def _proc(pid):
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        fields = text[text.rfind(")") + 2:].split()
        return {"pid": pid, "utime_ticks": int(fields[11]), "stime_ticks": int(fields[12]),
                "rss_bytes": int(fields[21]) * os.sysconf("SC_PAGE_SIZE"), "start_ticks": int(fields[19])}
    except (OSError, ValueError, IndexError):
        return {"pid": pid, "missing": True}


def resource_sampler(output, children, stop, cpu=None):
    if cpu is not None:os.sched_setaffinity(0,{cpu})
    with (output / "resources.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["monotonic_ns", "role", "pid", "utime_ticks", "stime_ticks", "rss_bytes", "host_cpu", "pressure_cpu", "mem_available_kb"])
        deadline = time.monotonic()
        while not stop.is_set():
            now = time.monotonic_ns()
            stat = Path("/proc/stat").read_text().splitlines()[0]
            pressure = Path("/proc/pressure/cpu").read_text().strip() if Path("/proc/pressure/cpu").exists() else ""
            mem = next((l.split()[1] for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemAvailable:")), "")
            for role, pid in [("harness", os.getpid()), *[(c.name, c.process.pid) for c in children.copy()]]:
                p = _proc(pid)
                writer.writerow([now, role, pid, p.get("utime_ticks"), p.get("stime_ticks"), p.get("rss_bytes"), stat, pressure, mem])
            stream.flush()
            deadline += 1
            stop.wait(max(0, deadline - time.monotonic()))


def runtime_config(c, policy):
    detector = read_json(c["detector"]["model"]) if c["detector"]["model"] else None
    adaptive = policy.startswith(("ADAPT", "TRIGGER"))
    bootstrap = detector is None and c["protocol"]["population"] in ("calibration", "pilot") and not adaptive
    if detector is None and not bootstrap:
        raise TrialFailure("normal-training detector baseline missing")
    key = f"{c['workload']['family']}/{c['incidents']['background']}/{c['detector']['signal']}"
    if bootstrap:
        detector = {"deployments": {key: {"median": 0, "scale": .1, "threshold": 12}}}
    if key not in detector["deployments"]:
        raise TrialFailure(f"detector deployment not calibrated: {key}")
    base = detector["deployments"][key]
    supervisor = adaptive and policy.startswith("ADAPT") and c["controller"]["supervisor"]
    mechanism = "SWITCH" if policy.endswith("SWITCH") else "GATE"
    model = read_json(c["controller"]["model"]) if c["controller"]["model"] else None
    if supervisor and model is None:
        raise TrialFailure("adaptive supervisor requires real independent calibration cost table")
    cpus = c["host"]["cpus"]
    values = {"policy": policy, "period_ms": c["detector"]["period_ms"], "dwell_ms": c["controller"]["dwell_ms"],
              "grace_ms": c["detail"]["drain_grace_ms"], "hysteresis": int(c["controller"]["hysteresis"]),
              "supervisor": int(supervisor or policy == "SHADOW"), "stats": 0,
              "component": {"EMPTY": 1, "FILTER": 2, "PAIR": 3}.get(policy, 0),
              "signal_total": int(c["detector"]["signal"] == "total"),
              "cpu1": cpus[1], "cpu2": cpus[2], "isolated": cpus[3] + 1 if c["host"]["placement"] == "isolated" else 0,
              "ring_bytes": c["detail"]["ring_bytes"], "queue_bytes": c["detail"]["queue_bytes"],
              "stage_bytes": 4096 if policy in ("SENT", "LOADED", "FIX_LOW_GATE") else stage_requirement(c), "median": base["median"], "scale": base["scale"],
              "high": base["threshold"], "budget": c["controller"]["budget"], "rate_low": 0, "rate_high": 0}
    if model:
        values["rate_low"], values["rate_high"] = model["rate_tertiles"]
        for m in range(3):
            rows = [x for x in model["cells"] if x["mechanism"] == mechanism and x["mode"] == m]
            fallback = model.get("fallbacks", {}).get(f"{mechanism}/{m}", {}).get("ucl")
            if fallback is None:
                fallback = max((x["ucl"] for x in rows), default=None)
            if supervisor and fallback is None:
                raise TrialFailure(f"no calibrated cost fallback for {mechanism}/mode {m}")
            values[f"fallback_{m}"]=fallback if fallback is not None else "nan"
            for r in range(3):
                for u in range(3):
                    cell = next((x for x in rows if x["rate_band"] == r and x["util_band"] == u), None)
                    values[f"cost_{m}_{r}_{u}"] = cell["ucl"] if cell else "nan"
            action = model.get("transitions", {}).get(f"{mechanism}/{m}")
            values[f"transition_{m}"] = action["loss_ucl"] if action and action.get("loss_ucl") is not None else "nan"
    return values


def stage_requirement(c):
    rate = c["detail"]["calibrated_peak_rate"]
    if rate is None:
        if c["protocol"]["population"] in ("calibration", "pilot"):
            return c["workload"]["max_stage_bytes"]
        raise TrialFailure("aggregate peak eligible rate (including incidents) is not calibrated")
    # 72-byte transport stride plus worst-case one-record 16-byte frame overhead.
    seconds = c["workload"]["warmup_s"] + c["workload"]["measure_s"] + c["workload"]["drain_s"]
    return math.ceil((32 + seconds * rate * 88) * 1.20)


def _inventory():
    return {kind: command(["bpftool", "-j", kind, "show"], timeout=15) for kind in ("link", "prog", "map")}


def trial_config(c, row):
    s = row["scenario"]
    cfg = resolve(c, workload={"family": s["workload"], "drift": s["drift"],
                               "truth_aggregation":s.get("truth_aggregation",c["workload"].get("truth_aggregation",True)),
                               "sample_units_every":s.get("sample_units_every",c["workload"]["sample_units_every"]),
                               "input_seed": row["seeds"]["workload"], "measure_s": s.get("measure_s", c["workload"]["measure_s"])},
                  incidents={"background": s["background"], "kind": s.get("kind", "futex"),
                             "slots":1 if s.get("short") else c["incidents"]["slots"],
                             "durations_ms":[10] if s.get("short") else c["incidents"]["durations_ms"]},
                  host={"placement": s.get("placement", c["host"]["placement"])},
                  detail={"ring_bytes": s.get("ring_bytes", c["detail"]["ring_bytes"])},
                  detector={"period_ms": s.get("period_ms", c["detector"]["period_ms"]), "signal": s.get("signal", c["detector"]["signal"])},
                  controller={"budget": s.get("budget", c["controller"]["budget"]), "dwell_ms": s.get("dwell_ms", c["controller"]["dwell_ms"]),
                              "hysteresis": s.get("hysteresis", c["controller"]["hysteresis"])})
    cfg["experiment"]["resource_sampling"]=s.get("resource_sampling",c["experiment"].get("resource_sampling",True))
    return cfg


def execute(c, row, population, output, *, sample_resources=None):
    if platform.system() != "Linux":
        raise TrialFailure("real trials require a feature-tested Linux host")
    c = trial_config(c, row)
    if sample_resources is None:sample_resources=c["experiment"].get("resource_sampling",True)
    if c["host"]["cpus"] is None or c["workload"]["compute_repeats"] is None:
        raise TrialFailure("CPU placement and frozen workload repeat count must be resolved")
    attempt = Path(output) / f"{row['trial_id']}-a-{uuid.uuid4().hex}"
    attempt.mkdir(parents=True, exist_ok=False)
    synthetic = population == "synthetic"
    if synthetic:
        raise TrialFailure("execute() never generates synthetic experiments")
    cfg_hash = config_hash(c)
    manifest = {"schema_version": 1, "run_uuid": uuid.uuid4().hex, "population": population, "synthetic": False,
                "protocol_version": c["protocol"]["version"], "config_hash": cfg_hash, "code": git_state(),
                "trial": row, "host": discover(), "policy": row["policy"], "model_hashes": {},
                "clock": "CLOCK_MONOTONIC", "stats_enabled": bool(row["scenario"].get("stats", False)),
                "start": utc_now(), "finish": None, "exit": None, "valid": False}
    manifest["build_hashes"]={name:digest(ROOT/"build"/name) for name in ("agent","workload","known_count") if (ROOT/"build"/name).is_file()}
    for key in ("detector", "controller"):
        if c[key]["model"]:
            manifest["model_hashes"][key] = digest(c[key]["model"])
    write_json(attempt / "resolved_config.json", c, exclusive=True)
    write_json(attempt / "manifest.json", manifest, exclusive=True)
    intended = schedule(c, row["seeds"]["episode"], c["incidents"]["kind"])
    write_json(attempt / "intended_schedule.json", intended, exclusive=True)
    (attempt / "schedule.tsv").write_text("".join(f"{e['episode_id']} {e['offset_ns']} {e['nominal_ms']} {int(e['kind']=='cpu')}\n" for e in intended), encoding="ascii")
    children = []
    errors = []
    stop = threading.Event()
    sampler = None
    stage = None
    cgroups = []
    before = _inventory()
    write_json(attempt / "inventory_before.json", before, exclusive=True)
    original_affinity=os.sched_getaffinity(0)
    os.sched_setaffinity(0,{c["host"]["cpus"][0]})
    with (attempt / "commands.jsonl").open("x", encoding="utf-8") as commands:
        try:
            if shutil.disk_usage(attempt).free < c["workload"]["min_free_disk_bytes"]:
                raise TrialFailure("disk guard: insufficient archive capacity")
            stage = Path(tempfile.mkdtemp(prefix="aet-", dir="/dev/shm"))
            stage.chmod(0o700)
            mem = {l.split(":")[0]: int(l.split()[1]) * 1024 for l in Path("/proc/meminfo").read_text().splitlines() if l.split()[1].isdigit()}
            if row["policy"] != "NONE":
                required = 4096 if row["policy"] in ("SENT", "LOADED", "FIX_LOW_GATE") else stage_requirement(c)
                cap = min(c["workload"]["max_stage_bytes"], int(mem["MemTotal"] * c["workload"]["max_ram_fraction"]))
                if required > cap or required + 150_000_000 > min(mem["MemAvailable"], shutil.disk_usage(stage).free):
                    raise TrialFailure(f"staging memory guard: required {required}, per-trial cap {cap}")
            cpus = c["host"]["cpus"]
            args = [ROOT / "build/workload", c["workload"]["family"], attempt, attempt / "schedule.tsv", stage,
                    int(c["workload"]["compute_repeats"]), row["seeds"]["workload"], c["workload"]["warmup_s"],
                    c["workload"]["measure_s"], int(c["workload"]["drift"]), c["workload"]["drift_at_s"],
                    int(c["incidents"]["background"] == "high"), *cpus, c["workload"]["sample_units_every"],int(c["workload"].get("truth_aggregation",True))]
            workload = Child(args, attempt, "workload", commands)
            children.append(workload)
            ready = workload.message(60)
            manifest["membership"] = ready
            (attempt / "targets.txt").write_text("".join(f"{t['tid']}\n" for t in ready["targets"]), encoding="ascii")
            cgroot = Path(c["host"]["cgroup_root"])
            for child in children:
                cg = cgroot / f"aet-{manifest['run_uuid']}-{child.name}"
                cg.mkdir()
                (cg / "cgroup.procs").write_text(str(child.process.pid))
                cgroups.append(cg)
            agent = None
            if row["policy"] != "NONE":
                runtime = runtime_config(c, row["policy"])
                runtime["stats"] = int(manifest["stats_enabled"])
                (attempt / "runtime.conf").write_text("".join(f"{k} {v}\n" for k, v in runtime.items()), encoding="ascii")
                agent = Child([ROOT / "build/agent", attempt, attempt / "targets.txt", attempt / "runtime.conf", stage / "detail.bin"], attempt, "agent", commands)
                children.append(agent)
                cg = cgroot / f"aet-{manifest['run_uuid']}-agent"
                cg.mkdir(); (cg / "cgroup.procs").write_text(str(agent.process.pid)); cgroups.append(cg)
                manifest["agent_ready"] = agent.message(30)
                if abs(time.monotonic_ns() - manifest["agent_ready"]["monotonic_ns"]) > 1_000_000_000:
                    raise TrialFailure("monotonic clock mismatch/readiness scheduling delay")
            if sample_resources:
                sampler = threading.Thread(target=resource_sampler, args=(attempt, children, stop, c["host"]["cpus"][3]), daemon=True)
                sampler.start()
            epoch = time.monotonic_ns() + int((c["workload"]["warmup_s"] + 1) * 1e9)
            manifest["epoch_ns"] = epoch
            workload.send(f"START {epoch}")
            parked = workload.message(c["workload"]["warmup_s"] + c["workload"]["measure_s"] + 15)
            if parked.get("type") != "parked":
                raise TrialFailure("missing worker stop barrier")
            manifest["parked"] = parked
            if agent:
                agent.stop(grace=c["workload"]["drain_s"] + 2)
                if agent.process.returncode:
                    raise TrialFailure(f"agent exit {agent.process.returncode}; inspect verifier/stderr logs")
            workload.send("STOP")
            workload.process.wait(timeout=10)
            if workload.process.returncode:
                raise TrialFailure(f"workload exit {workload.process.returncode}")
            manifest["exit"] = 0
        except (OSError, ValueError, subprocess.TimeoutExpired, TrialFailure) as exc:
            errors.append(str(exc))
            manifest["exit"] = 2
        finally:
            stop.set()
            if sampler:
                sampler.join(timeout=3)
            for child in reversed(children):
                try:
                    child.stop()
                except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                    errors.append(f"cleanup {child.name}: {exc}")
            for cg in reversed(cgroups):
                try:
                    if (cg / "memory.peak").exists():
                        manifest.setdefault("cgroup_memory_peak", {})[cg.name] = (cg / "memory.peak").read_text().strip()
                    cg.rmdir()
                except OSError as exc:
                    errors.append(f"owned cgroup cleanup: {exc}")
            archive_ok=True
            if stage and (stage / "detail.bin").exists():
                try:archive_raw(stage / "detail.bin", attempt)
                except (OSError,ValueError,TrialFailure) as exc:
                    archive_ok=False;errors.append(f"archive verification:{exc}; retain raw staging:{stage}")
            if stage and archive_ok:
                # Resolved, explicitly owned mkdtemp path; never remove shared /dev/shm.
                if stage.resolve().parent != Path("/dev/shm").resolve() or not stage.name.startswith("aet-"):
                    raise TrialFailure("unsafe cleanup target")
                try:shutil.rmtree(stage)
                except OSError as exc:errors.append(f"owned staging cleanup:{exc}")
            os.sched_setaffinity(0,original_affinity)
    for suffix in ("stdout","stderr"):
        with (attempt/f"{suffix}.log").open("x",encoding="utf-8") as merged:
            for log in sorted(attempt.glob(f"*.{suffix}.log")):
                merged.write(f"[{log.name}]\n");merged.write(log.read_text(encoding="utf-8",errors="replace"))
    after = _inventory()
    write_json(attempt / "inventory_after.json", after, exclusive=True)
    cleanup = {"schema_version": 1, "children_exited": all(ch.process.poll() is not None for ch in children),
               "owned_cgroups_removed": all(not p.exists() for p in cgroups), "staging_removed": stage is None or not stage.exists(),
               "before": before, "after": after}
    write_json(attempt / "cleanup.json", cleanup, exclusive=True)
    manifest["finish"] = utc_now()
    manifest["valid"] = not errors
    flags=[]
    if (attempt/"resources.csv").exists():
        from analysis.noise import noise_flags
        try:
            noise=noise_flags(attempt/"resources.csv",hz=os.sysconf("SC_CLK_TCK"),target_cpus=2,
                steal_limit=c["experiment"]["vm_steal_threshold"],external_limit=c["experiment"]["external_cpu_threshold"],fraction=c["experiment"]["noise_fraction"])
            flags=noise["flags"];write_json(attempt/"noise.json",noise,exclusive=True)
        except (OSError,ValueError,KeyError) as exc:errors.append(f"resource sample validation:{exc}")
    manifest["valid"]=not errors
    # The attempt is sealed only after validation. No edits are allowed after seal.json.
    write_json(attempt / "manifest.json", manifest)
    write_json(attempt / "validity.json", {"schema_version": 1, "valid": not errors, "infrastructure_errors": errors, "noise_flags": flags}, exclusive=True)
    if not errors:
        from analysis.validate import validate_attempt
        checked = validate_attempt(attempt, require_seal=False)
        if not checked["valid"]:
            errors.extend(checked["errors"])
            manifest["valid"] = False
            write_json(attempt / "manifest.json", manifest)
            write_json(attempt / "validity.json", {"schema_version": 1, "valid": False, "infrastructure_errors": errors, "noise_flags": flags})
    write_json(attempt / "seal.json", {"schema_version": 1, "sealed_at": utc_now(),
               "files": {p.relative_to(attempt).as_posix(): digest(p) for p in attempt.rglob("*") if p.is_file()}}, exclusive=True)
    return attempt, not errors


def archive_raw(source, output):
    source = Path(source)
    checksum = digest(source)
    archive = output / "detail.bin.gz"
    with source.open("rb") as inp, archive.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as sink:
            shutil.copyfileobj(inp, sink, 1024 * 1024)
    import hashlib
    restored = hashlib.sha256()
    with gzip.open(archive, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            restored.update(chunk)
    if restored.hexdigest() != checksum:
        raise TrialFailure("compressed archive restoration checksum mismatch; retain source")
    write_json(output / "detail.archive.json", {"raw_sha256": checksum, "archive_sha256": digest(archive),
               "raw_bytes": source.stat().st_size, "archive_bytes": archive.stat().st_size}, exclusive=True)
