from __future__ import annotations

from pathlib import Path

from .config import config_hash, model_paths, unresolved
from .matrix import generate
from .util import ROOT, canonical_hash, digest, git_state, read_json, utc_now, write_json


def freeze(c, output):
    missing = unresolved(c)
    if missing:
        raise ValueError("cannot freeze unresolved calibration/host fields: " + ", ".join(missing))
    state = git_state()
    if state["dirty"] or not state["commit"]:
        raise ValueError("freeze requires a clean committed source tree")
    host = read_json(ROOT / "state/host.json")
    if not host.get("privileged_smoke_passed"):
        raise ValueError("real privileged smoke gate has not passed")
    precision = read_json(ROOT / "state/calibration/precision.json")
    if c["experiment"]["blocks"] != precision["selected"]:
        raise ValueError("block count differs from frozen pilot precision decision")
    sources = {str(p.relative_to(ROOT)): digest(p) for base in ("configs", "schemas", "analysis", "src", "runner", "context", "artifact")
               for p in (ROOT / base).rglob("*") if p.is_file() and "__pycache__" not in p.parts and "releases" not in p.parts}
    models = {str(p): digest(p) for p in model_paths(c)}
    runtime_names=["build/agent","build/workload","build/known_count","build/vmlinux.h","build/sentinel.skel.h","build/detail.skel.h",
                   "state/host.json",c["host"]["toolchain_lock"]]
    runtime_files={str(p):digest(ROOT/p) for p in runtime_names}
    cells = generate(c)
    frozen = {"schema_version": 1, "frozen_at": utc_now(), "source": state, "config_hash": config_hash(c),
              "dependencies": sources, "models": models, "runtime_files":runtime_files,"matrix_hash": canonical_hash(cells),
              "matrix": cells, "precision": precision, "retry_rule": "first valid immutable attempt, at most two infrastructure retries"}
    frozen["freeze_hash"] = canonical_hash(frozen)
    write_json(output, frozen, exclusive=True)
    return frozen


def verify_freeze(c, path):
    record = read_json(path)
    expected = record["freeze_hash"]
    if canonical_hash({k:v for k,v in record.items() if k!="freeze_hash"}) != expected:
        raise ValueError("preregistration hash is corrupt")
    if c["protocol"]["preregistration_hash"] != expected:
        raise ValueError("config preregistration does not reference this freeze")
    # The hash itself is excluded from the resolved-config comparison to avoid a cycle.
    canonical = {**c, "protocol": {**c["protocol"], "preregistration_hash": None}}
    if config_hash(canonical) != record["config_hash"]:
        raise ValueError("configuration changed after freeze")
    for name, checksum in {**record["dependencies"], **record["models"],**record["runtime_files"]}.items():
        if digest(ROOT / name) != checksum:
            raise ValueError(f"frozen dependency changed: {name}")
    if git_state()["commit"] != record["source"]["commit"]:
        raise ValueError("source commit changed; protocol amendment required")
    return record
