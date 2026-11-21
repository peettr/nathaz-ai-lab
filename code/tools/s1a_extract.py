"""S1a 第一步：从 Silsoe v7 原始 CSV（只读）抽出 L22.3 v4b 用到的列，存成小 npz。
口径与 22_Lab/06_Logs/lbm_transfer/run_v4b.py load() 完全一致（Cp 定义、42 s 起、REF 2 s 因果平滑、q 只用训练段）。
用法: python3 -I s1a_extract.py <raw_dir> <out.npz>"""
import sys,csv,numpy as np
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2])
if out.exists(): raise FileExistsError(out)
TAPS=[f'V{i}' for i in range(2,7)]+[f'H{i}' for i in range(1,7)]
GROUPS={f'P_x{x}':[f'P_x{x}_z{z}' for z in (1,3,6)] for x in ('-33.05','-30.00','-25.00','-20.00','-15.00','-10.00')}
GROUPS['R_y0']=[f'R_y0_z{z}' for z in (1,3,6)]
ST=[s for g in GROUPS.values() for s in g]
def rd(p,cols):
    with p.open() as f: hdr=next(csv.reader(f))
    return np.loadtxt(p,delimiter=',',skiprows=1,usecols=[hdr.index(c) for c in cols],ndmin=2)
pc=['step','t_s']+[f'{s}_{c}' for s in ST for c in ('ux','uy','uz')]+['REF_rho','REF_ux','REF_uy','REF_uz']
tc=['step','t_s']+TAPS
taps=np.concatenate([rd(root/f'S600v7_seg{s}_taps.csv',tc) for s in (1,2)])
pr=np.concatenate([rd(root/f'S600v7_seg{s}_probes.csv',pc) for s in (1,2)])
assert len(taps)==32100 and np.array_equal(taps[:,0],pr[:,0]) and np.all(np.diff(taps[:,0])==16)
r=pr[:,pc.index('REF_rho')]; cs=np.r_[0.,np.cumsum(r)]; i=np.arange(len(r)); lo=np.maximum(0,i-99)
ref=(cs[i+1]-cs[lo])/(i-lo+1)
keep=taps[:,1]>=42; t=taps[keep,1]; p=pr[keep]; tp=taps[keep]; ref=ref[keep]
assert len(t)==30001
train=t<462; rv=p[:,[pc.index('REF_'+c) for c in ('ux','uy','uz')]]
q=np.mean(.5*p[train,pc.index('REF_rho')]*np.sum(rv[train]**2,axis=1))
y=(tp[:,2:]-ref[:,None])/(3*q)
x=p[:,2:2+3*len(ST)]
np.savez_compressed(out,t=t,y=y,x=x,q=q,stations=np.array(ST),taps=np.array(TAPS))
print('saved',out,'q',q,'y',y.shape,'x',x.shape)
