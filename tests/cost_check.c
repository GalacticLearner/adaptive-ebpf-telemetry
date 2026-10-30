#include <math.h>
#include <stdio.h>
#include "../src/common/cost.h"
int main(void) {
    double table[3][3][3],actions[3]={NAN,NAN,NAN},worst[3]={.01,.20,.04};
    for(int m=0;m<3;m++)for(int r=0;r<3;r++)for(int u=0;u<3;u++)table[m][r][u]=m==1?.20:m==2?.04:.01;
    struct aet_cost_result x=aet_cost_choose(1,0,10,.9,5,20,.05,table,worst,actions);
    if(x.selected!=0||x.allowed!=0)return 1; /* HIGH feasible does not license unsafe MEDIUM. */
    x=aet_cost_choose(2,0,10,.9,5,20,.05,table,worst,actions);
    if(x.selected!=2||x.infeasible||!x.transition_unresolved)return 2;
    x=aet_cost_choose(0,2,10,.9,5,20,.05,table,worst,actions);
    if(x.allowed!=2)return 3; /* affordable detector reduction respects dwell */
    for(int r=0;r<3;r++)for(int u=0;u<3;u++)table[2][r][u]=.20;
    x=aet_cost_choose(0,2,NAN,NAN,5,20,.05,table,worst,actions);
    if(x.allowed!=0||!x.fallback)return 4;
    for(int m=0;m<3;m++)for(int r=0;r<3;r++)for(int u=0;u<3;u++)table[m][r][u]=NAN;
    x=aet_cost_choose(2,0,10,.9,5,20,.05,table,worst,actions);
    if(x.selected!=2||!x.fallback||x.infeasible)return 5;
    puts("cost-supervisor checks passed");return 0;
}
