from __future__ import annotations

import math
import random
import statistics


def quantile(values, p):
    xs = sorted(values)
    if not xs:
        raise ValueError("empty quantile")
    index = (len(xs) - 1) * p
    lo, hi = math.floor(index), math.ceil(index)
    return xs[lo] + (xs[hi] - xs[lo]) * (index - lo)


def bootstrap_blocks(values, *, draws=10000, seed=741911, transform=lambda x: x):
    if not values or any(not math.isfinite(v) for v in values):
        raise ValueError("finite nonempty block estimates required")
    rng = random.Random(seed)
    n = len(values)
    samples = [transform(sum(values[rng.randrange(n)] for _ in range(n)) / n) for _ in range(draws)]
    return {"estimate": transform(statistics.mean(values)), "ci_low": quantile(samples, .025),
            "ci_high": quantile(samples, .975), "lcl_one_sided": quantile(samples, .05),
            "ucl_one_sided": quantile(samples, .95), "blocks": n,
            "independent_unit": "block", "draws": draws, "seed": seed,
            "underpowered": n < 8}


def paired_throughput(policy, none, *, budget=.05, **kwargs):
    if len(policy) != len(none) or not policy or min([*policy, *none]) <= 0:
        raise ValueError("paired positive throughput arrays required")
    result = bootstrap_blocks([math.log(p / n) for p, n in zip(policy, none)], transform=lambda x: 1 - math.exp(x), **kwargs)
    if result["underpowered"]:
        compliance = "inconclusive"
    elif result["ucl_one_sided"] <= budget:
        compliance = "compliant"
    elif result["lcl_one_sided"] > budget:
        compliance = "violating"
    else:
        compliance = "inconclusive"
    result.update(budget=budget, compliance=compliance,
                  arithmetic_ratio_loss=1 - statistics.mean(policy) / statistics.mean(none))
    return result


def holm(pvalues):
    """Return raw-order Holm adjusted p values; ties handled monotonically."""
    if any(not 0 <= p <= 1 for p in pvalues):
        raise ValueError("invalid p value")
    order = sorted(range(len(pvalues)), key=pvalues.__getitem__)
    result = [0.0] * len(order)
    previous = 0.0
    for rank, index in enumerate(order):
        previous = max(previous, min(1.0, (len(order) - rank) * pvalues[index]))
        result[index] = previous
    return result


def poisson_rate_interval(count, hours, *, confidence=.95):
    """Exact central Poisson interval via integer-shape gamma inversion, no SciPy."""
    if count < 0 or hours <= 0:
        raise ValueError("invalid count/exposure")
    def cdf(k, x):
        # CDF of Gamma(k,1) = P(Poisson(x)>=k), stable using log-sum-exp.
        terms = [-x + i * math.log(x) - math.lgamma(i + 1) for i in range(k)] if x > 0 else [0.0] + [-math.inf] * (k - 1)
        maximum = max(terms)
        return max(0.0, min(1.0, 1 - math.exp(maximum) * sum(math.exp(t - maximum) for t in terms)))
    def inverse(k, p):
        lo, hi = 0.0, max(1.0, k * 2.0)
        while cdf(k, hi) < p:
            hi *= 2
        for _ in range(80):
            mid = (lo + hi) / 2
            if cdf(k, mid) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    alpha = 1 - confidence
    return {"rate_per_hour": count / hours, "ci_low": inverse(count, alpha / 2) / hours if count else 0.0,
            "ci_high": inverse(count + 1, 1 - alpha / 2) / hours, "count": count, "hours": hours,
            "assumption": "Poisson count model; cluster/run variability must also be disclosed"}


def choose_blocks(log_ratio_sd, capture_block_sd, *, cap=30):
    """Conservative normal interval half-width criterion, frozen before final runs."""
    if min(log_ratio_sd, capture_block_sd) < 0:
        raise ValueError("negative standard deviation")
    required = max(12, math.ceil((1.96 * log_ratio_sd / .02) ** 2), math.ceil((1.96 * capture_block_sd / .10) ** 2))
    return {"required": required, "selected": min(required, cap), "precision_limited": required > cap,
            "targets": {"throughput_loss_half_width": .02, "capture_half_width": .10}}
