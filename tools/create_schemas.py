"""Materialize explicit closed JSON schemas; not executed when validating runs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import yaml
from runner.util import ROOT, write_json


def infer(value):
    if isinstance(value, dict):
        return {"type": "object", "additionalProperties": False, "required": list(value),
                "properties": {k: infer(v) for k, v in value.items()}}
    if isinstance(value, list):
        item = infer(value[0]) if value else {}
        return {"type": "array", "items": item, "uniqueItems": True}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer", "minimum": 0}
    if isinstance(value, float):
        return {"type": "number", "minimum": 0}
    if value is None:
        return {"type": ["string", "null"]}
    return {"type": "string"}


if __name__ == "__main__":
    cfg = yaml.safe_load((ROOT / "configs/protocol.yaml").read_text())
    schema = infer(cfg)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    p = schema["properties"]
    # Additive v1 calibration controls: absent in earlier synthetic fixtures means true.
    p["workload"]["required"].remove("truth_aggregation")
    p["experiment"]["required"].remove("resource_sampling")
    p["host"]["required"].remove("role")
    def field(a, b, spec):
        p[a]["properties"][b] = spec
    for a, b in (("workload", "compute_repeats"), ("detail", "calibrated_peak_rate"),
                 ("detail", "sink_bytes_per_second"), ("detector", "threshold")):
        field(a, b, {"type": ["number", "null"], "exclusiveMinimum": 0})
    field("host", "cpus", {"type": ["array", "null"], "items": {"type": "integer", "minimum": 0},
                             "minItems": 4, "maxItems": 4, "uniqueItems": True})
    field("protocol", "source_hashes", {"type": "object", "additionalProperties": {"type": "string", "pattern": "^[0-9a-f]{64}$"}})
    for a, b, values in (("protocol", "population", ["synthetic", "calibration", "pilot", "confirmatory", "robustness"]),
                         ("host", "placement", ["shared", "isolated"]), ("workload", "family", ["cpu", "io"]),
                         ("host", "role", ["primary", "secondary"]),
                         ("incidents", "kind", ["futex", "cpu", "none"]), ("incidents", "background", ["low", "high"]),
                         ("controller", "mechanism", ["GATE", "SWITCH"]),
                         ("detector", "signal", ["max-bin", "total"])):
        field(a, b, {"enum": values})
    for a, b in (("controller", "budget"), ("workload", "max_ram_fraction"), ("incidents", "background_duty")):
        field(a, b, {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1})
    for a, b in (("workload", "measure_s"), ("detector", "period_ms"), ("experiment", "blocks"),
                 ("detail", "inflight_entries"), ("detail", "target_entries"), ("analysis", "bootstrap_draws")):
        field(a, b, {"type": "integer", "minimum": 1})
    write_json(ROOT / "schemas/protocol.schema.json", schema)
