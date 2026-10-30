#include "cost.h"
#include <math.h>
static double predict(int mode,int applied,int rb,int ub,bool context,
    const double table[3][3][3],const double worst[3],const double transition[3],bool *fallback,bool *unresolved) {
    double cost=context?table[mode][rb][ub]:NAN;
    if(!isfinite(cost)) {
        *fallback=true;cost=isfinite(worst[mode])?worst[mode]:-INFINITY;
        for(int r=0;r<3;r++)for(int u=0;u<3;u++)if(isfinite(table[mode][r][u])&&table[mode][r][u]>cost)cost=table[mode][r][u];
    }
    if(!isfinite(cost))return NAN;
    if(mode!=applied) {
        if(isfinite(transition[mode]))cost+=transition[mode];
        else *unresolved=true;
    }
    return cost;
}
struct aet_cost_result aet_cost_choose(int requested,int applied,double rate,double utilization,double low,double high,
    double budget,const double table[3][3][3],const double worst[3],const double transition[3]) {
    struct aet_cost_result out={.allowed=2,.selected=0,.prediction=NAN,.infeasible=true};
    bool context=isfinite(rate)&&isfinite(utilization);
    int rb=rate<low?0:rate<high?1:2,ub=utilization<.5?0:utilization<.8?1:2;
    for(int m=requested;m>=0;m--) {
        double cost=predict(m,applied,rb,ub,context,table,worst,transition,&out.fallback,&out.transition_unresolved);
        if(m==0)out.prediction=cost;
        if(isfinite(cost)&&cost<=budget){out.selected=m;out.prediction=cost;out.infeasible=false;break;}
    }
    bool ignored=false;
    double current=predict(applied,applied,rb,ub,context,table,worst,transition,&out.fallback,&ignored);
    /* Restrict only a budget-denied request or an unsafe current mode. A detector-only
     * downshift still respects dwell. Nonmonotonic mode cost tables are supported. */
    if(out.selected<requested||(out.selected<applied&&(!isfinite(current)||current>budget)))out.allowed=out.selected;
    if(out.infeasible)out.allowed=0;
    return out;
}
