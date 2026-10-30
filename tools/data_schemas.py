"""Write the versioned run schemas used before inference."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner.util import ROOT, write_json


def obj(required, properties, extra=False):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "required": required, "properties": properties, "additionalProperties": extra}


if __name__ == "__main__":
    integer = {"type": "integer", "minimum": 0}
    text = {"type": "string"}
    boolean = {"type": "boolean"}
    unrestricted_obj = {"type": "object"}
    counter_fields = ("eligible selected rejected insert_failed replaced malformed exit_without_selected completed reserve_failed emitted abandoned pending consumed sink_drop written undrained sink_bytes sink_flush_ns sink_error component".split())
    counters = {k: integer for k in counter_fields}
    counters.update(schema_version={"const": 1}, ledger_ok=boolean, stats_enabled=boolean)
    write_json(ROOT / "schemas/counters.schema.json", obj(list(counters), counters))
    manifest = {"schema_version": {"const": 1}, "run_uuid": text,
        "population": {"enum": ["synthetic", "calibration", "pilot", "confirmatory", "robustness"]},
        "synthetic": boolean, "protocol_version": text, "config_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "code": unrestricted_obj, "trial": unrestricted_obj, "host": unrestricted_obj, "policy": text,
        "model_hashes": unrestricted_obj, "clock": {"const": "CLOCK_MONOTONIC"}, "stats_enabled": boolean,
        "start": text, "finish": {"type": ["string", "null"]}, "exit": {"type": ["integer", "null"]}, "valid": boolean,
        "membership": unrestricted_obj, "agent_ready": unrestricted_obj, "epoch_ns": integer, "parked": unrestricted_obj,
        "cgroup_memory_peak": unrestricted_obj}
    manifest["build_hashes"]=unrestricted_obj
    write_json(ROOT / "schemas/manifest.schema.json", obj([k for k in manifest if k not in ("membership", "agent_ready", "epoch_ns", "parked", "cgroup_memory_peak","build_hashes")], manifest))
    trial = {"cell_id":text,"block_id":text,"trial_id":text,"position":integer,"policy":text,
             "scenario":unrestricted_obj,"seeds":unrestricted_obj,"baseline_trial":{"type":["string","null"]},"status":text}
    write_json(ROOT / "schemas/trial.schema.json", obj(list(trial),trial))
    helper = {"role":text,"tid":integer,"first_ns":integer,"last_ns":integer,"calls":integer,
              "waits":integer,"wakes":integer,"errors":integer,"interrupted":integer,"checksum":integer}
    incident = {"type":{"const":"episode"},"episode_id":integer,"kind":{"enum":["futex","cpu"]},
                "nominal_ms":integer,"intended_ns":integer,"start_ns":integer,"end_ns":integer,
                "eligible_calls":integer,"valid":boolean,"helpers":{"type":"array","items":obj(list(helper),helper),"minItems":1,"maxItems":2}}
    write_json(ROOT / "schemas/incident.schema.json", obj(list(incident),incident))
    validity = {"schema_version":{"const":1},"valid":boolean,"infrastructure_errors":{"type":"array","items":text},
                "noise_flags":{"type":"array","items":text}}
    write_json(ROOT / "schemas/validity.schema.json",obj(list(validity),validity))
    result = {"schema_version":{"const":1},"protocol_version":text,"synthetic":boolean,
              "input_hashes":unrestricted_obj,"attempts":{"type":"array"},"comparisons":{"type":"array"},
              "missing":{"type":"array"},"hypotheses":unrestricted_obj}
    write_json(ROOT / "schemas/results.schema.json",obj(list(result),result))
