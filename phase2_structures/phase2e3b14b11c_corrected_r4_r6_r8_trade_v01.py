from math import sqrt
def pct(new,old): return 100.0*(new-old)/old
r4={'stress':394.96,'force':-67310.0,'elong':-0.56810,'def':5.1407}
r6={'stress':412.24,'force':-67348.0,'elong':-0.56842,'def':5.1439}
r8={'stress':266.91,'force':-67391.0,'elong':-0.56878,'def':3.4981}
print('R4 vs R6 stress [%]:',pct(r4['stress'],r6['stress']))
print('R8 vs R6 stress [%]:',pct(r8['stress'],r6['stress']))
print('R8 vs R6 deformation [%]:',pct(r8['def'],r6['def']))
print('R8 vs R4 stress [%]:',pct(r8['stress'],r4['stress']))
