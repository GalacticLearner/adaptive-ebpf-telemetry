#ifndef AET_COST_H
#define AET_COST_H
#include <stdbool.h>
struct aet_cost_result { int allowed,selected; double prediction; bool infeasible,fallback,transition_unresolved; };
struct aet_cost_result aet_cost_choose(int requested,int applied,double rate,double utilization,double low,double high,
    double budget,const double table[3][3][3],const double fallback[3],const double transition[3]);
#endif
