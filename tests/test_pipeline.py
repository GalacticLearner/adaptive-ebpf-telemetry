from pathlib import Path
import copy
import tempfile
import unittest

from runner.config import load_config
from runner.calibration import train_cost_table
from runner.freeze import freeze
from runner.util import ROOT,read_json,write_json
from tools.synthetic_fixture import create
from analysis.pipeline import analyze
from analysis.validate import validate_attempt


class PipelineTests(unittest.TestCase):
    def test_synthetic_full_path_and_seal_tampering(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"data/synthetic",prefix="test-") as parent:
            source=create(Path(parent)/"attempts",blocks=1)
            paths=sorted(p.parent for p in source.rglob("manifest.json"))
            self.assertEqual(len(paths),7)
            for path in paths:self.assertTrue(validate_attempt(path)["valid"],validate_attempt(path))
            c=load_config();c["analysis"]["bootstrap_draws"]=100
            result=analyze(source,Path(parent)/"analysis",c)
            self.assertTrue(result["synthetic"]);self.assertEqual(len(result["comparisons"]),6)
            self.assertTrue(all(r["throughput_loss"]["compliance"]=="inconclusive" for r in result["comparisons"]))
            target=paths[0]/"app.csv";target.write_text(target.read_text()+"\n")
            self.assertFalse(validate_attempt(paths[0])["valid"])
    def test_freeze_rejects_unresolved_host(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"unresolved"):freeze(load_config(),Path(temp)/"freeze.json")
    def test_cost_training_rejects_synthetic_and_sparse_data(self):
        with self.assertRaises(ValueError):train_cost_table([{"population":"calibration","synthetic":True}])
        rows=[dict(population="calibration",synthetic=False,block_id="one",mechanism="GATE",mode=0,
                   sentinel_rate=10,utilization=.9,log_ratio=-.02)]
        with self.assertRaisesRegex(ValueError,"eight independent"):train_cost_table(rows,draws=10)
    def test_all_declared_cli_dry_runs(self):
        from runner.cli import main
        for name,args in (("doctor",[]),("build",[]),("test",["--unprivileged"]),("calibrate",["--stage","normal"]),
                          ("pilot",[]),("freeze",[]),("run",[]),("validate",[]),("analyze",[]),("report",[]),("cleanup",[]),("package",[])):
            with self.subTest(command=name):self.assertEqual(main([name,"--dry-run",*args]),0)


if __name__=="__main__":unittest.main()
