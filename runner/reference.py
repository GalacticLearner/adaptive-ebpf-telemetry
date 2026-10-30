"""Executable specification for C policy and sentinel correctness tests."""
from __future__ import annotations

from dataclasses import dataclass
import math
import statistics

LOW, MEDIUM, HIGH = range(3)
MODES = ("LOW", "MEDIUM", "HIGH")
UINT32_MAX = 2**32 - 1


def threshold(q):
    if not 0 <= q <= 1:
        raise ValueError("probability outside [0,1]")
    return UINT32_MAX if q == 1 else math.floor(q * 2**32)


def config_word(generation, q):
    if not 0 <= generation <= UINT32_MAX:
        raise ValueError("generation overflow")
    return generation << 32 | threshold(q)


def bin_value(requested, now_bin, saved_epoch, count, *, seq=0, retention=2048, readable=True):
    if not readable or seq % 2 or now_bin - requested >= retention:
        return None
    if saved_epoch == 2**64 - 1:
        return 0
    if saved_epoch > requested:
        return None
    if saved_epoch < requested:
        return 0
    return count


def train_baseline(counts):
    if not counts:
        raise ValueError("empty baseline")
    xs = [math.log1p(x) for x in counts]
    m = statistics.median(xs)
    return {"median": m, "scale": max(1.4826 * statistics.median(abs(x - m) for x in xs), 0.10)}


def score(counts, baseline):
    return max((abs(math.log1p(x) - baseline["median"]) / baseline["scale"] for x in counts), default=0.0)


@dataclass
class Controller:
    high: float = 6
    period_ms: int = 100
    dwell_ms: int = 250
    recovery_ms: int = 500
    hysteresis: bool = True
    applied: int = LOW
    desired: int = LOW
    last_change_ns: int = 0
    quiet: int = 0
    alert_quiet: int = 0
    alert: bool = False

    def tick(self, now_ns, value, *, gap=False, allowed=HIGH):
        started = False
        if gap:
            self.quiet = self.alert_quiet = 0
            self.desired = LOW
        else:
            quiet_threshold = self.high / 4 if self.hysteresis else self.high / 2
            recovery = math.ceil(self.recovery_ms / self.period_ms) if self.hysteresis else 1
            if value >= self.high:
                self.desired = HIGH
            elif value >= self.high / 2:
                self.desired = MEDIUM
            if value < quiet_threshold:
                self.quiet += 1
                if self.quiet >= recovery:
                    self.desired = max(LOW, self.applied - 1)
                    self.quiet = 0
            else:
                self.quiet = 0
            if value >= self.high:
                started = not self.alert
                self.alert = True
            if value < self.high / 4:
                self.alert_quiet += 1
                if self.alert_quiet >= math.ceil(500 / self.period_ms):
                    self.alert = False
            else:
                self.alert_quiet = 0
        desired = min(self.desired, allowed)
        budget_override = allowed < self.applied
        deferred = desired != self.applied and not budget_override and not gap and now_ns - self.last_change_ns < self.dwell_ms * 1_000_000
        if not deferred and desired != self.applied:
            self.applied = desired
            self.last_change_ns = now_ns
        return {"requested": self.desired, "allowed": allowed, "applied": self.applied,
                "alert": self.alert, "alert_started": started, "dwell_deferred": deferred,
                "budget_override": budget_override, "sensor_uncertain": gap}


class Lifecycle:
    """Nonblocking transition oracle. Actual link operations are C/libbpf."""
    def __init__(self, mechanism="SWITCH"):
        self.mechanism = mechanism
        self.state = "LOW"
        self.entry = self.exit = mechanism == "GATE"
        self.q = 0
        self.generation = 0
        self.deadline = None
        self.queued = LOW
        self.actions = []

    def request(self, mode, now_ns, *, pending=0, fail=None):
        self.queued = mode
        if self.state == "DRAIN":
            return self.poll(now_ns, pending=pending)
        if mode == LOW:
            self.q = 0
            self.generation += 1
            self.actions.append("disable_selection")
            if self.mechanism == "SWITCH" and self.entry:
                self.entry = False
                self.actions.append("detach_entry")
                self.state = "DRAIN"
                self.deadline = now_ns + 20_000_000
                return self.poll(now_ns, pending=pending)
            self.state = "LOW"
        else:
            if not self.exit:
                if fail == "exit":
                    raise RuntimeError("exit attachment failed")
                self.exit = True
                self.actions.append("attach_exit")
            if not self.entry:
                if fail == "entry":
                    self.exit = False
                    self.actions.append("rollback_exit")
                    raise RuntimeError("entry attachment failed")
                self.entry = True
                self.actions.append("attach_entry")
            self.q = (0, .1, 1)[mode]
            self.generation += 1
            self.actions.append("publish_config")
            self.state = MODES[mode]
        return 0

    def poll(self, now_ns, *, pending):
        abandoned = 0
        if self.state == "DRAIN" and (pending == 0 or now_ns >= self.deadline):
            self.exit = False
            self.actions.append("detach_exit")
            abandoned = pending
            self.state = "LOW"
            if self.queued != LOW:
                self.request(self.queued, now_ns)
        return abandoned
