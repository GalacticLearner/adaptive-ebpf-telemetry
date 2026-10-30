"""Materialize parameter origins for review."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runner.config import load_config
from runner.util import ROOT,write_json
if __name__=="__main__":
    c=load_config();rows=[]
    for section,values in c.items():
        for name,value in values.items():
            kind="calibration-derived" if value is None or (section,name) in (("experiment","blocks"),("detector","threshold")) else "fixed"
            rows.append({"path":f"{section}.{name}","classification":kind,"draft_value":value})
    write_json(ROOT/"configs/parameter_registry.json",{"schema_version":1,"parameters":rows,
        "hypotheses":{"H1":"adaptive versus fixed impact/capture frontier","H2":"GATE versus SWITCH","H3":"prediction error under held-out drift","H4":"hysteresis and dwell ablations"},
        "exploratory":"Optional real-device/service workloads require a separate protocol."})
