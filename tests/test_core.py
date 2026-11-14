from __future__ import annotations

import copy
import math
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from runner.config import ConfigError, load_config, unresolved
from runner.collect import select_rate_rows
from runner.matrix import CORE, estimate, generate, schedule, select_within_budget
from runner.reference import Controller, Lifecycle, bin_value, config_word, score, threshold, train_baseline
from runner.util import ROOT, canonical_hash, host_lock, seed_for
from analysis.metrics import matches_source_futex
from analysis.stats import bootstrap_blocks, choose_blocks, holm, paired_throughput, poisson_rate_interval
from analysis.metrics import match_alerts, throughput
from analysis.wire import Event, EVENT, records, write_records
from analysis.validate import bounded_pilot_loss_errors, ledger


class ConfigMatrixTests(unittest.TestCase):
    def setUp(self):self.c=load_config()
    def test_primary_counts_and_pairing(self):
        rows=generate(self.c,"primary");self.assertEqual(len(rows),672);self.assertEqual(len({r["cell_id"] for r in rows}),56)
        blocks={}
        for r in rows:blocks.setdefault(r["block_id"],[]).append(r)
        for block in blocks.values():
            self.assertEqual({r["policy"] for r in block},set(CORE));self.assertEqual(len({canonical_hash(r["seeds"]) for r in block}),1)
        self.assertGreater(len({rs[0]["policy"] for rs in blocks.values()}),1)
    def test_time_budget_selects_complete_matched_blocks(self):
        rows=generate(self.c,"primary")
        one_block=[row for row in rows if row["block_id"]==rows[0]["block_id"]]
        block_hours=estimate(self.c,one_block)["host_hours"]
        selected=select_within_budget(self.c,rows,2*block_hours)
        blocks={}
        for row in selected:blocks.setdefault(row["block_id"],[]).append(row)
        self.assertEqual(len(selected),2*len(CORE))
        self.assertTrue(all({row["policy"] for row in block}==set(CORE) for block in blocks.values()))
        self.assertLessEqual(estimate(self.c,selected)["host_hours"],2*block_hours)
        with self.assertRaisesRegex(ValueError,"one complete matched block"):
            select_within_budget(self.c,rows,block_hours/2)
    def test_limited_rate_sample_includes_cpu_and_io_pairs(self):
        rows=[]
        for family in ("cpu","io"):
            for policy in ("NONE","FIX_LOW_GATE","SENT"):
                rows.append({"trial_id":f"{family}-{policy}","block_id":f"cal-b000","policy":policy,
                             "scenario":{"workload":family,"background":"low"}})
        selected=select_rate_rows(rows,5,include_io=True)
        self.assertEqual(len(selected),5)
        self.assertEqual({row["scenario"]["workload"] for row in selected},{"cpu","io"})
        self.assertTrue({"cpu-NONE","cpu-FIX_LOW_GATE","io-NONE","io-FIX_LOW_GATE"}.issubset({row["trial_id"] for row in selected}))
        with self.assertRaisesRegex(ValueError,"at least 4"):
            select_rate_rows(rows,3,include_io=True)
    def test_quick_pilot_is_bounded_and_fixed_policy(self):
        from runner.campaign import bounded_pilot_profile
        from runner.matrix import estimate
        c=load_config(ROOT/"configs/pilot.yaml")
        rows=generate(c,"primary")
        self.assertEqual(len(rows),16)
        self.assertEqual({r["scenario"]["workload"] for r in rows},{"cpu","io"})
        self.assertEqual({r["policy"] for r in rows},{"NONE","FIX_Q01"})
        self.assertLessEqual(estimate(c,rows)["host_hours"],.18)
        self.assertTrue(bounded_pilot_profile(c,rows))
        unsafe=copy.deepcopy(rows);unsafe[0]["policy"]="FIX_HIGH"
        self.assertFalse(bounded_pilot_profile(c,unsafe))
    def test_all_extensions_present(self):
        rows=generate(self.c);names={r["scenario"]["study"] for r in rows}
        self.assertTrue({"quiet","no_hysteresis","no_dwell","signal_total","unseen_cpu","isolated","second_host","attribution_stats_True","attribution_stats_False"}.issubset(names))
        ids={r["trial_id"] for r in rows}
        self.assertTrue(all(r["baseline_trial"] in ids for r in rows if r["baseline_trial"]))
    def test_schedule_both_phases(self):
        values=schedule(self.c,123);self.assertEqual(values,schedule(self.c,123));self.assertEqual(len(values),14)
        for half in (values[:7],values[7:]):self.assertEqual(sorted(r["nominal_ms"] for r in half),[10,25,50,100,250,500,1000])
    def test_secondary_short_schedule_has_one_short_incident(self):
        from runner.trial import trial_config
        row=next(r for r in generate(self.c,"robustness") if r["scenario"]["study"]=="second_host_short")
        configured=trial_config(self.c,row);values=schedule(configured,row["seeds"]["episode"])
        self.assertEqual(len(values),1);self.assertEqual(values[0]["nominal_ms"],10)
    def test_unknown_config_rejected(self):
        import yaml
        c=copy.deepcopy(self.c);c["detail"]["silent_drop"]=True
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.yaml";p.write_text(yaml.safe_dump(c))
            with self.assertRaises(ConfigError):load_config(p)
    def test_unresolved_freeze_dependencies(self):self.assertIn("host.id",unresolved(self.c))
    def test_seed_stable_and_separated(self):
        self.assertEqual(seed_for(300000,"workload","b1"),seed_for(300000,"workload","b1"))
        self.assertNotEqual(seed_for(300000,"workload","b1"),seed_for(300000,"episode","b1"))
    def test_host_lock_exclusion(self):
        with tempfile.TemporaryDirectory() as d:
            with host_lock(Path(d)/"lock"):
                with self.assertRaises(RuntimeError):
                    with host_lock(Path(d)/"lock"):pass


class MetricsTests(unittest.TestCase):
    def test_capture_uses_helper_source_call_window(self):
        incident={"kind":"futex","valid":True,"start_ns":100,"end_ns":400,
                  "helpers":[{"tid":10,"first_ns":150,"last_ns":350}]}
        self.assertFalse(matches_source_futex(SimpleNamespace(syscall_id=202,tid=10,entry_ns=149),incident))
        self.assertTrue(matches_source_futex(SimpleNamespace(syscall_id=202,tid=10,entry_ns=150),incident))
        self.assertTrue(matches_source_futex(SimpleNamespace(syscall_id=202,tid=10,entry_ns=350),incident))
        self.assertFalse(matches_source_futex(SimpleNamespace(syscall_id=202,tid=10,entry_ns=351),incident))
        self.assertFalse(matches_source_futex(SimpleNamespace(syscall_id=202,tid=99,entry_ns=200),incident))
    def test_bounded_pilot_rejects_sink_loss_but_reports_classified_abandonment(self):
        counters={"reserve_failed":0,"pending":0,"undrained":0,"sink_drop":0,"sink_error":0,"abandoned":1}
        self.assertEqual(bounded_pilot_loss_errors(counters),[])
        counters["sink_error"]=28
        self.assertTrue(bounded_pilot_loss_errors(counters))


class SensorControllerTests(unittest.TestCase):
    def test_idle_old_new_and_retention(self):
        self.assertEqual(bin_value(100,110,90,1000),0)
        self.assertEqual(bin_value(100,110,100,17),17)
        self.assertEqual(bin_value(100,110,2**64-1,0),0)
        self.assertIsNone(bin_value(100,110,101,0))
        self.assertIsNone(bin_value(100,2200,100,17))
        self.assertIsNone(bin_value(100,110,100,17,seq=1))
    def test_exact_sampling_branches(self):
        self.assertEqual(threshold(0),0);self.assertEqual(threshold(1),2**32-1)
        self.assertEqual(threshold(.1),429496729)
        self.assertEqual(config_word(7,.1),7<<32|429496729)
    def test_sampling_frequency(self):
        rng=random.Random(8);n=100000;q=.1
        selected=sum(rng.getrandbits(32)<threshold(q) for _ in range(n))
        self.assertLess(abs(selected/n-q),5*math.sqrt(q*(1-q)/n))
    def test_short_burst_inside_tick_visible(self):
        base=train_baseline([10]*100)
        self.assertGreater(score([10,10,1000,10],base),6)
    def test_gap_not_recovery(self):
        p=Controller(applied=2,desired=2,last_change_ns=0)
        d=p.tick(1_000_000_000,0,gap=True)
        self.assertEqual(d["applied"],0);self.assertTrue(d["sensor_uncertain"]);self.assertEqual(p.quiet,0)
    def test_dwell_and_budget_override(self):
        p=Controller(last_change_ns=1_000_000_000)
        self.assertTrue(p.tick(1_100_000_000,10)["dwell_deferred"])
        self.assertEqual(p.tick(1_300_000_000,10)["applied"],2)
        d=p.tick(1_310_000_000,10,allowed=0)
        self.assertEqual(d["applied"],0);self.assertTrue(d["budget_override"])
    def test_recovery_wall_time(self):
        for period in (25,100,500):
            p=Controller(period_ms=period,dwell_ms=0,applied=2,desired=2)
            for i in range(math.ceil(500/period)-1):self.assertEqual(p.tick((i+1)*period*1_000_000,0)["applied"],2)
            self.assertEqual(p.tick(500_000_000,0)["applied"],1)
    def test_lifecycle_order_drain_queue(self):
        life=Lifecycle();life.request(2,0)
        self.assertEqual(life.actions[:3],["attach_exit","attach_entry","publish_config"])
        life.request(0,1_000_000,pending=3);self.assertFalse(life.entry);self.assertTrue(life.exit)
        life.request(1,2_000_000,pending=3);self.assertEqual(life.state,"DRAIN")
        self.assertEqual(life.poll(21_000_000,pending=3),3);self.assertEqual(life.state,"MEDIUM")
    def test_attach_rollback(self):
        life=Lifecycle()
        with self.assertRaises(RuntimeError):life.request(2,0,fail="entry")
        self.assertFalse(life.entry);self.assertFalse(life.exit)
    def test_c_matches_reference(self):
        exe=ROOT/"build"/("policy_replay.exe" if __import__('os').name=="nt" else "policy_replay")
        if not exe.exists():self.skipTest("compile policy_replay to compare actual C code")
        for period in (25,100,500):
            rng=random.Random(period);p=Controller(period_ms=period)
            inputs=[];expected=[]
            for i in range(200):
                ns=(i+1)*period*1_000_000;s=rng.choice([0,1,2,4,8,12]);gap=rng.random()<.05;allowed=rng.randrange(3)
                inputs.append(f"{ns} {s} {int(gap)} {allowed}")
                d=p.tick(ns,s,gap=gap,allowed=allowed)
                expected.append([int(d[k]) for k in ("requested","allowed","applied","alert","alert_started","dwell_deferred","budget_override","sensor_uncertain")])
            try:done=subprocess.run([str(exe),"6",str(period),"250","1","0"],input="\n".join(inputs)+"\n",text=True,capture_output=True,check=True)
            except OSError as exc:
                if getattr(exc,"winerror",None)==4551:self.skipTest("Windows Application Control blocked rebuilt native C checker; requires permitted host execution")
                raise
            self.assertEqual([[int(v) for v in line.split()] for line in done.stdout.splitlines()],expected)
    def test_c_cost_supervisor_edge_cases(self):
        exe=ROOT/"build"/("cost_check.exe" if __import__('os').name=="nt" else "cost_check")
        if not exe.exists():self.skipTest("compile cost_check for actual C supervisor verification")
        try:done=subprocess.run([str(exe)],capture_output=True,text=True)
        except OSError as exc:
            if getattr(exc,"winerror",None)==4551:self.skipTest("Windows Application Control blocked rebuilt native C checker; requires permitted host execution")
            raise
        self.assertEqual(done.returncode,0,done.stdout+done.stderr)


class WireAccountingTests(unittest.TestCase):
    def event(self):return Event(1,0,1,100,200,4,5,202,0,1,3,-11,7)
    def test_roundtrip_and_offsets(self):
        self.assertEqual(EVENT.size,64)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"detail.bin";write_records(p,[(self.event(),220)])
            self.assertEqual(list(records(p)),[(self.event(),220)])
    def test_corruption_truncation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"detail.bin";write_records(p,[(self.event(),220)]);data=p.read_bytes()
            for changed in (data[:-1],data[:12],data[:-1]+bytes([data[-1]^1])):
                p.write_bytes(changed)
                with self.assertRaises(ValueError):list(records(p))
    def test_impossible_clock_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"detail.bin";write_records(p,[(self.event(),150)])
            with self.assertRaises(ValueError):list(records(p))
    def test_ledger_nonoverlapping(self):
        c=dict(eligible=100,selected=20,rejected=80,insert_failed=1,replaced=1,malformed=0,completed=15,abandoned=2,pending=1,
               emitted=12,reserve_failed=3,consumed=11,undrained=1,written=10,sink_drop=1,component=0,ledger_ok=True)
        self.assertEqual(ledger(c),[]);c["sink_drop"]=0;self.assertIn("sink balance",ledger(c))


class InferenceTests(unittest.TestCase):
    def test_host_noise_uses_owned_cpu_and_capacity(self):
        import csv
        from analysis.noise import noise_flags
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"resources.csv"
            with path.open("w",newline="") as stream:
                writer=csv.writer(stream);writer.writerow(["monotonic_ns","role","utime_ticks","stime_ticks","host_cpu"])
                for sec in range(3):writer.writerow([sec*1_000_000_000,"harness",0,0,f"cpu {sec*20} 0 0 {sec*180} 0 0 0 0"])
            self.assertIn("external_cpu_above_preregistered_threshold",noise_flags(path)["flags"])
            self.assertEqual(noise_flags(path,external_limit=.2)["flags"],[])
    def test_one_to_one_preexisting_alert(self):
        incidents=[dict(episode_id=0,start_ns=100,end_ns=200,valid=True),dict(episode_id=1,start_ns=300,end_ns=400,valid=True)]
        alerts=[dict(start_ns=150,end_ns=450)]
        result=match_alerts(incidents,alerts,after_ns=0)
        self.assertEqual(result["recall"],.5);self.assertEqual(result["already_alerting"],[1]);self.assertEqual(result["precision"],1)
    def test_zero_alert_precision_na(self):self.assertIsNone(match_alerts([],[])["precision"])
    def test_known_paired_effect_and_negative_loss(self):
        result=paired_throughput([95]*12,[100]*12,draws=100)
        self.assertAlmostEqual(result["estimate"],.05)
        self.assertLess(paired_throughput([101]*12,[100]*12,draws=100)["estimate"],0)
    def test_no_false_precision_from_one_block(self):self.assertEqual(paired_throughput([100],[100],draws=10)["compliance"],"inconclusive")
    def test_reproducible_block_bootstrap(self):self.assertEqual(bootstrap_blocks([1,2,5],draws=100),bootstrap_blocks([1,2,5],draws=100))
    def test_holm(self):self.assertEqual(holm([.01,.04,.03]),[.03,.06,.06])
    def test_zero_false_alarms_has_positive_upper_bound(self):
        rate=poisson_rate_interval(0,1);self.assertEqual(rate["ci_low"],0);self.assertAlmostEqual(rate["ci_high"],3.688879454,places=6)
    def test_precision_floor_cap(self):
        self.assertEqual(choose_blocks(.001,.01)["selected"],12);self.assertTrue(choose_blocks(1,1)["precision_limited"])
    def test_throughput_sampling_resolution(self):
        app=[dict(worker="0",monotonic_ns=str(t),successful=str(n)) for t,n in ((0,0),(1000000000,100),(2000000000,200))]
        self.assertEqual(throughput(app,500000000,1500000000)["units_per_s"],100)


if __name__=="__main__":unittest.main()
