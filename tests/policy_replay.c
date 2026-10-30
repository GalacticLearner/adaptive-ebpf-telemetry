#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include "../src/common/policy.h"
int main(int argc,char **argv) {
    if(argc!=6)return 2;
    struct aet_policy p={.high=strtod(argv[1],0),.period_ms=atoi(argv[2]),.dwell_ms=atoi(argv[3]),.recovery_ms=500,.hysteresis=atoi(argv[4]),.last_change_ns=strtoull(argv[5],0,10)};
    uint64_t ns;double score;int gap,allowed;
    while(scanf("%"SCNu64" %lf %d %d",&ns,&score,&gap,&allowed)==4) {
        struct aet_decision d=aet_tick(&p,ns,score,gap,allowed);
        printf("%d %d %d %d %d %d %d %d\n",d.requested,d.allowed,d.applied,d.alert,d.alert_started,d.dwell_deferred,d.budget_override,d.sensor_uncertain);
    }
    return 0;
}
