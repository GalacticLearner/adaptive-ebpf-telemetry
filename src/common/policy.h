#ifndef AET_POLICY_H
#define AET_POLICY_H
#include <stdint.h>
#include <stdbool.h>
#include <math.h>

struct aet_policy {
    double high;
    unsigned period_ms, dwell_ms, recovery_ms;
    bool hysteresis;
    int applied, desired;
    uint64_t last_change_ns;
    unsigned quiet, alert_quiet;
    bool alert;
};
struct aet_decision {
    int requested, allowed, applied;
    bool alert, alert_started, dwell_deferred, budget_override, sensor_uncertain;
};
struct aet_decision aet_tick(struct aet_policy *, uint64_t, double, bool, int);
uint32_t aet_threshold(double q);
double aet_score(uint64_t count, double median, double scale);
int aet_bin_read(uint64_t requested, uint64_t now_bin, uint64_t epoch,
                 uint64_t count, uint64_t seq, uint64_t *result);
#endif
