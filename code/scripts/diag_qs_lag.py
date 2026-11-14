# 事后诊断（只用训练组 v7）：准定常比时均还差，是代码错还是单点 U_ref 确实对不上？
import numpy as np,json,sys
z=np.load(sys.argv[1]+'/v7.npz'); t=z['t']; k=np.flatnonzero((t>=float(z['keep']))&(np.arange(len(t))>=100)); cp=z['cp'].astype('f4'); r=z['qs_ratio']; u=z['u']
names=list(z['tap_cols']); pts=[f'R_y{y}_z{zz}' for zz in (1,3,6,12) for y in (-12,-6,0,6,12)]+[f'P_x-30.00_z{zz}' for zz in (1,3,6,12)]+['REF']
def c(a,b): return float(np.corrcoef(a,b)[0,1])
wind=8000+np.array([i for i,n in enumerate(names) if n in('V2','V3','V4','V5','V6')])
y=cp[k][:,wind].mean(1); o={}
o['windward_V2_V6_vs_REF_U2_by_lag_s']={str(l/5):round(c(y,r[k-l]),3) for l in range(0,41,5)}
i=pts.index('R_y0_z6'); spd=(u[:,i*3:i*3+3]**2).sum(1); o['windward_vs_R_y0_z6_U2_by_lag_s']={str(l/5):round(c(y,spd[k-l]),3) for l in range(0,41,5)}
i=pts.index('R_y0_z3'); spd=(u[:,i*3:i*3+3]**2).sum(1); o['windward_vs_R_y0_z3_U2_by_lag_s']={str(l/5):round(c(y,spd[k-l]),3) for l in range(0,41,5)}
o['std_qs_ratio']=float(r[k].std()); o['mean_qs_ratio']=float(r[k].mean())
json.dump(o,open(sys.argv[2]+'/out/diag_qs_lag.json','w'),indent=1); print(o)
