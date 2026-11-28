#!/usr/bin/env python3
"""Pipeline-only synthetic branch tests. B0 is read-only regression reference."""
import copy, json, math
from pathlib import Path
from assert_T18 import evaluate,calibrate,metrics,ve,vp,t17,ORDER

B0=Path('./24_Urban_Wind_LBM/06_Logs/R21.4a_T17_periodic_ABL/big6v3_periodic_t15_k2_20261121_103455/session_luw-t17b3-b65b60624/evidence/t15_s1_case.json')
base=json.loads(B0.read_text())
print('B0 S3',metrics(base)['S3']['max_abs_difference'])
assert round(metrics(base)['S3']['max_abs_difference'],4)==.3439

def synthetic(slope=.24):
    c=copy.deepcopy(base)
    for k in range(1,65):c['profile_u'][str(k)]=t17.USTAR/t17.KAPPA*math.log((k-.5+t17.Z0)/t17.Z0)
    z=9
    base_slope=t17.KAPPA*z/t17.USTAR*(c['profile_u']['10']-c['profile_u']['9'])-z/(z+t17.Z0)
    c['profile_u']['10']+=(slope-base_slope)*t17.USTAR/(t17.KAPPA*z)
    assert abs(metrics(c)['S3']['max_abs_difference']-slope)<1e-10
    return c

def pair(a=-.02,b=-.02,baseline=.12):
    return {s:{'stable':True,'uncal':{'mae':.11,'mse_pat':.02,'C':.13},'cal':{'mae':.11+d,'mse_pat':.02,'C':.13},'baseline':{'mae':baseline}} for s,d in zip(('s101','s102'),(a,b))}

def run(label, calibration=None, validation_ABL=None, validation_E=None, expected=None):
    d={'calibration':calibration if calibration is not None else {'K1a':synthetic()},'validation_ABL':validation_ABL if validation_ABL is not None else synthetic(),'validation_E':validation_E if validation_E is not None else pair()}
    got=evaluate(d)['total_verdict'];assert got==expected,(label,got,expected);print('PASS',label,got)

m=calibrate({'K1a':synthetic(.300057),'K1b':synthetic(.298)})
assert m['selected']=='K1b';print('PASS S3=0.300057 excluded at threshold')
m=calibrate({'K1a':synthetic(.294),'K1b':synthetic(.28)})
assert m['selected']=='K1a' and len(m['tie_candidates'])==2;print('PASS tie 0.015/order')
run('usable',expected='能用（限 T17 平台、AIJ Case E 1 m、80 点风速 MAE）')
run('empty qualification',calibration={'K1a':dict(base,correlations={'rx_half':.3,'ry_half':.0})},expected='不判')
run('all candidates invalid',calibration={k:dict(base,correlations={'rx_half':.3,'ry_half':.0}) for k in ORDER},expected='不判')
run('calibration fail',calibration={'K1a':synthetic(.301)},expected='标定失败')
run('validation V3 fail',validation_ABL=dict(base,correlations={'rx_half':.3,'ry_half':.0}),expected='不判')
run('validation S3 fail',validation_ABL=synthetic(.34),expected='不能用')
run('V-E worsens',validation_E=pair(.02,.02),expected='不能用')
run('V-E unstable',validation_E={**pair(), 's101':{**pair()['s101'],'stable':False}},expected='不能用')
run('V-E below baseline guard',validation_E=pair(0,0,baseline=.08),expected='不能用')
run('mixed seeds',validation_E=pair(-.02,.02),expected='部分')
run('V-E missing',validation_E={},expected='不判')
run('calibration fail precedence missing VE',calibration={'K1a':synthetic(.31)},validation_E={},expected='标定失败')
assert ve(pair(-.009,-.009))['verdict']=='在种子变化内';print('PASS seed variation')
assert ve(pair(-.01,-.01))['verdict']=='改善';print('PASS paired improvement boundary')
obs={'mean':[.2,-.2,.05],'rms':[.2,.2,.05],'negative_peak':[-.3,-.4,-.2],'positive_peak':[.3,.4,.2]}
r=vp({'uncal':{'obs':obs,'model':obs},'cal':{'obs':obs,'model':obs}})
assert r['models']['cal']['mean']['FAC2']==1 and r['models']['cal']['mean']['FAC2_denominator']==2
print('PASS V-P FAC2 denominator; ALL TESTS PASS')

