#!/usr/bin/env python3
"""Compare s1301 shortened G1/G2/G2Lc with immutable full smoke JSON."""
import os, sys, json, time, subprocess, traceback
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfiltfilt
os.environ.update(P1_SHA256='e55cf7ea02fa5fda56bf276883fb874ac2ac4145c9a4d5cf1f70d25d06f877fb',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import colab_a170_2 as m
from colab_a170_4 import mods
C=Path('/content'); REF=json.loads((C/'full_reference_s1301.json').read_text())

def calculate(dest,row,provenance):
    read_out=mods()[-1]
    d=read_out(dest/'NREL-5MW.out',['Time','NacYaw','Wind1VelX','Wind1VelY','TwrBsMxt','TwrBsMyt','YawBrMzp','RootMyb1','RootMyb2','RootMyb3','RotSpeed'])
    t=d['Time'];mask=(t+row['start_abs_s']>=provenance['rotor_3s_first13_abs_s'])&(t+row['start_abs_s']<=provenance['rotor_3s_last25_abs_s']+60)
    assert np.count_nonzero(mask)>100 and t[-1]+row['start_abs_s']>=provenance['rotor_3s_last25_abs_s']+60
    x,y=d['TwrBsMxt'][mask],d['TwrBsMyt'][mask];blades=np.stack([d[f'RootMyb{i}'][mask] for i in (1,2,3)])
    metrics=dict(tower_resultant_max_kNm=float(np.hypot(x,y).max()),tower_fore_aft_positive_max_kNm=float(y.max()),tower_fore_aft_negative_magnitude_kNm=float(max(0.,-y.min())),tower_top_yaw_absmax_kNm=float(np.abs(d['YawBrMzp'][mask]).max()),blade_root_positive_max_kNm=float(blades.max()),blade_root_negative_magnitude_kNm=float(max(0.,-blades.min())),rotor_speed_overshoot_vs_12p1_pct=float(100*(d['RotSpeed'][mask].max()/12.1-1)))
    yaw=np.rad2deg(np.unwrap(np.deg2rad(d['NacYaw'])));i=np.searchsorted(t,t+1.0,side='left');v=i<len(t)
    rate=float(np.max(np.abs((yaw[i[v]]-yaw[v])/(t[i[v]]-t[v]))))
    hp=sosfiltfilt(butter(3,.5,fs=1/np.median(np.diff(t)),btype='highpass',output='sos'),yaw)
    return metrics,rate,float(np.ptp(hp))

def main():
    assert (C/'a170_2_pilot_measure.done').exists()
    measurement=json.loads((C/'a170_2_pilot_measure.json').read_text())
    provenance=json.loads((m.S/'P1_power_s1301/provenance.json').read_text())
    assert provenance['bts_sha256']=='0c3a75bfa65c2e98e002460a2963d21cf3a1219c67150b48ac4c7038ecf5f2a7'
    cutoff=provenance['rotor_3s_last25_abs_s']+120
    m.old.P=m.P  # fresh interpreter must rebind the legacy module's run root
    results={}; b,a,*_=mods()
    for group in ('G1','G2','G2Lc'):
        ref=REF[f'P1_power_s1301_{group}.json'];row=m.row(1301,'power',group,ref['trigger_abs_s']);row['end_abs_s']=cutoff
        dest=m.stage_with_initial_yaw(row)
        a.replace_key(dest/'NREL-5MW.fst','TMax',f'{cutoff-m.START:.3f}')
        env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='0')
        began=time.monotonic()
        with (dest/'openfast.log').open('x') as log:
            rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=max(60,int(2*measurement['full_wall_s']))).returncode
        assert rc==0,(group,rc,(dest/'openfast.log').read_text(errors='replace')[-2000:])
        metrics,rate,hp=calculate(dest,row,provenance)
        diffs={k:abs(v-ref['metrics'][k])/max(abs(ref['metrics'][k]),1e-12)*100 for k,v in metrics.items()}
        diffs['yaw_rate_max_deg_s']=abs(rate-ref['yaw_rate_max_deg_s'])/max(abs(ref['yaw_rate_max_deg_s']),1e-12)*100
        diffs['yaw_highpass_gt_0p5hz_pp_deg']=abs(hp-ref['yaw_highpass_gt_0p5hz_pp_deg'])/max(abs(ref['yaw_highpass_gt_0p5hz_pp_deg']),1e-12)*100
        # Frozen gate covers load metrics and the full-time 1 s yaw secant; the
        # auxiliary >0.5 Hz peak-to-peak is recorded but not a gate metric.
        gate_keys=list(metrics)+['yaw_rate_max_deg_s']
        results[group]={'wall_s':time.monotonic()-began,'cutoff_abs_s':cutoff,'metrics':metrics,'yaw_rate_max_deg_s':rate,'yaw_highpass_gt_0p5hz_pp_deg':hp,'relative_diff_pct':diffs,'gate_keys':gate_keys,'pass_lt_0p1_pct':all(diffs[k]<0.1 for k in gate_keys)}
        (C/'a170_2_short_compare_v2.json').write_text(json.dumps(results,indent=2))
        print('SHORT',group,results[group]['wall_s'],max(diffs.values()),flush=True)
    (C/'a170_2_short_compare_v2.done').write_text('ok\n')

if __name__=='__main__':
    try:main()
    except BaseException:
        tb=traceback.format_exc();(C/'a170_2_short_compare_v2.failed').write_text(tb);print(tb,flush=True);raise
