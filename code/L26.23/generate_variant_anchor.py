#!/usr/bin/env python3
"""Generate per-run anchor via the ORIGINAL frozen functions; never edit frozen script."""
import argparse,csv,importlib.util,json
from pathlib import Path
import numpy as np
from scipy.io import loadmat

def main():
    p=argparse.ArgumentParser()
    for k in ('frozen','params','taps','mat','building','ref','out'):p.add_argument('--'+k,required=True)
    a=p.parse_args(); out=Path(a.out)
    if out.exists():raise FileExistsError(out)
    spec=importlib.util.spec_from_file_location('frozen_negpeak',a.frozen)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    cfg=json.loads(Path(a.params).read_text());taps=mod.read_csv(a.taps)
    ids=[int(r['tap_id']) for r in taps]
    if len(ids)!=360 or len(set(ids))!=360:raise ValueError('360 unique tap IDs required')
    m=loadmat(a.mat);loc=np.asarray(m['Location_of_measured_points'])
    if not np.array_equal(loc[2].astype(int),ids):raise ValueError('MAT order')
    wt=np.asarray(m['Wind_pressure_coefficients'],float)
    if wt.shape!=(32768,360):raise ValueError('MAT shape')
    Uwt=float(np.ravel(m['Uh_AverageWindSpeed'])[0]);fswt=float(np.ravel(m['Sample_frequency'])[0])
    if abs(fswt-1000)>1e-8:raise ValueError('MAT sample rate')
    raw=np.loadtxt(a.building,comments='#');ref=np.loadtxt(a.ref,comments='#')
    if raw.shape[1]!=361 or ref.shape[1]!=6:raise ValueError('column count')
    t=raw[:,0];rt=ref[:,0]
    if any(np.any(np.diff(z)<=0) for z in (t,rt)) or np.max(abs(np.diff(t)-.001))>cfg['sample_tolerance_s']:raise ValueError('timestamp gate')
    rm=(rt>=10)&(rt<=44)
    pref=ref[rm,1:5].mean(axis=0).mean()
    if not np.isfinite(pref):raise ValueError('REF2 nonfinite')
    win=(t>=10-1e-9)&(t<=44+1e-9);tw=t[win]
    pk=(tw>cfg['peak_start_s']+1e-9)&(tw<=cfg['peak_end_s']+1e-9)
    if len(tw)!=34001 or int(pk.sum())!=32952:raise ValueError('window frame gate')
    q=.5*cfg['U_LES_mps']**2
    hw=mod.stat(wt,fswt,Uwt,cfg['H_m'],10)
    hl=mod.stat((raw[win,1:]-pref)/q,1000,cfg['U_LES_mps'],cfg['H_m'],10,tw,cfg['peak_start_s'],cfg['peak_end_s'])
    with out.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['tap_id','cfd_min','v0_min']);w.writeheader()
        for i in range(360):w.writerow({'tap_id':ids[i],'cfd_min':format(hl['history_min'][i],'.5f'),'v0_min':format(hw['history_min'][i],'.5f')})
    mod.check_anchor(mod.read_csv(out),[dict(tap_id=ids[i],cfd_min=hl['history_min'][i],v0_min=hw['history_min'][i]) for i in range(360)],cfg['anchor_tolerance'])
    print(json.dumps({'rows':360,'full_frames':len(tw),'peak_frames':int(pk.sum()),'anchor':'PASS'},ensure_ascii=False))
if __name__=='__main__':main()
