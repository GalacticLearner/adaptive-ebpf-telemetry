#include "policy.h"
#include "wire.h"

uint32_t aet_threshold(double q) {
    if (q >= 1) return UINT32_MAX;
    if (q <= 0) return 0;
    return (uint32_t)floor(q * 4294967296.0);
}
double aet_score(uint64_t count, double median, double scale) {
    return fabs(log1p((double)count) - median) / fmax(scale, .10);
}
int aet_bin_read(uint64_t requested, uint64_t now_bin, uint64_t epoch,
                 uint64_t count, uint64_t seq, uint64_t *result) {
    if ((seq & 1) || now_bin < requested || now_bin - requested >= AET_BINS) return -1;
    if (epoch == AET_EMPTY_EPOCH || epoch < requested) { *result = 0; return 0; }
    if (epoch > requested) return -1;
    *result = count;
    return 0;
}
struct aet_decision aet_tick(struct aet_policy *p, uint64_t now, double score, bool gap, int allowed) {
    struct aet_decision d = {0};
    if (gap) {
        p->quiet = p->alert_quiet = 0;
        p->desired = AET_LOW;
    } else {
        unsigned recovery = p->hysteresis ? (p->recovery_ms + p->period_ms - 1) / p->period_ms : 1;
        double quiet_threshold = p->high / (p->hysteresis ? 4 : 2);
        if (score >= p->high) p->desired = AET_HIGH;
        else if (score >= p->high / 2) p->desired = AET_MEDIUM;
        if (score < quiet_threshold) {
            if (++p->quiet >= recovery) {
                p->desired = p->applied > AET_LOW ? p->applied - 1 : AET_LOW;
                p->quiet = 0;
            }
        } else p->quiet = 0;
        if (score >= p->high) { d.alert_started = !p->alert; p->alert = true; }
        if (score < p->high / 4) {
            if (++p->alert_quiet >= (500 + p->period_ms - 1) / p->period_ms) p->alert = false;
        } else p->alert_quiet = 0;
    }
    int wanted = p->desired < allowed ? p->desired : allowed;
    d.budget_override = allowed < p->applied;
    d.dwell_deferred = wanted != p->applied && !d.budget_override && !gap &&
        now - p->last_change_ns < (uint64_t)p->dwell_ms * 1000000ULL;
    if (!d.dwell_deferred && wanted != p->applied) {
        p->applied = wanted;
        p->last_change_ns = now;
    }
    d.requested = p->desired; d.allowed = allowed; d.applied = p->applied;
    d.alert = p->alert; d.sensor_uncertain = gap;
    return d;
}
