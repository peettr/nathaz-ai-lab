#!/usr/bin/env python3
"""Postprocess host-verified 22T outputs; ACK timeout is separate from producer completion."""
import csv, hashlib, json, math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
E=R/'session_luw-t17-a100-c8c50ba2/evidence'
REF=R.parent/'longspin_20261120_002118_v3/session_luw-t17-a100-df21176d/evidence'
def verified(p):
    assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==(p.parent/(p.name+'.sha256')).read_text().strip(), p
    return p
assert verified(E/'producer.done').read_text().strip()=='394900'
manifest=json.loads(verified(E/'handoff.json').read_text())['sha256']
for name, sha in manifest.items():
    p=verified(E/name); assert hashlib.sha256(p.read_bytes()).hexdigest()==sha, name
verified(E/'run.failed')
windows=[]
for i in range(1,12):
    w=json.loads(verified(E/f'window_{i:02}.json').read_text())
    assert w['window']==i and w['T_range']==[2*i-2,2*i] and len(w['U_profile_si_mps'])==64
    for key in ('V1_ratio','R_uu_x_half','R_uu_y_half','Px_mean','k_res_z9p5','e_2p5','S2b_rms'):
        assert math.isfinite(float(w[key]))
    windows.append(w)
ref=[json.loads(verified(REF/f'window_{i:02}.json').read_text()) for i in (10,11)]
fields=('V1_ratio','R_uu_x_half','R_uu_y_half','Px_begin','Px_end','Px_mean','k_res_z9p5','e_2p5','S2b_rms')
rows=[]; profiles=[]; correlations=[]
USTAR=0.27810; KAPPA=0.4; Z0=0.024
for w in windows:
    prof=w['U_profile_si_mps']
    slopes={str(z):KAPPA*z/USTAR*(float(prof[str(z+1)])-float(prof[str(z)]))-z/(z+Z0) for z in range(3,10)}
    row={'window':w['window'],'start_T':w['T_range'][0],'end_T':w['T_range'][1], 'start_step':w['step_range'][0],'end_step':w['step_range'][1]}
    row.update({key:w[key] for key in fields})
    row['k_res_over_ustar_tau_sq']=w['k_res_z9p5']/USTAR**2
    row['S3_max_abs']=max(map(lambda v:abs(v),slopes.values()))
    row['S3_pass']=row['S3_max_abs']<=0.3
    row['V1_pass']=0.95<=w['V1_ratio']<=1.05
    row['V3_pass']=abs(w['R_uu_x_half'])<=.1 and abs(w['R_uu_y_half'])<=.1
    rows.append(row)
    for z,value in slopes.items():profiles.append({'window':w['window'],'z_m':z,'S3_difference':value})
    if w['window'] in (10,11):
        for k in range(1,21):profiles.append({'window':w['window'],'k':k,'z_m':k-.5,'U_mps':prof[str(k)]})
        for axis in ('x','y'):
            for distance, value in w['correlation_curve'][axis+'_m'].items():
                correlations.append({'window':w['window'],'axis':axis,'delta_m':int(distance),'R_uu':value})
def csvout(name,data):
    cols=list(dict.fromkeys(k for row in data for k in row))
    with (R/name).open('x',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=cols);wr.writeheader();wr.writerows(data)
csvout('WINDOWS_DOMAIN8H.csv',rows)
csvout('PROFILE_AND_S3_DOMAIN8H.csv',profiles)
csvout('CORRELATION_DOMAIN8H.csv',correlations)
small={field:sum(w[field] for w in ref)/2 for field in ('e_2p5','S2b_rms')}
comparison={field:{'large_20_22T':windows[-1][field], 'small_18_20T':ref[0][field], 'small_20_22T':ref[1][field], 'small_mean':small[field], 'delta_large_minus_small':windows[-1][field]-small[field]} for field in small}
def sustained(key):
    return next((row['start_T'] for i,row in enumerate(rows) if all(r[key] for r in rows[i:])),None)
result={'source_evidence':str(E),'producer_step':394900,'run_done':False,'run_failed_reason':'ACK timeout after producer done and host hash verification', 'windows':11,'comparison':comparison,'V1_sustained_from_T':sustained('V1_pass'),'V3_sustained_from_T':sustained('V3_pass'),'last':rows[-1], 'rho_scale_k':'k_res/(0.27810 m/s)^2'}
(R/'DOMAIN8H_RESULT.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
fig,axes=plt.subplots(4,2,figsize=(11,13));fieldsplot=('V1_ratio','R_uu_x_half','R_uu_y_half','Px_mean','k_res_over_ustar_tau_sq','e_2p5','S2b_rms','S3_max_abs')
for ax,field in zip(axes.flat,fieldsplot):
    ax.plot([r['end_T'] for r in rows],[r[field] for r in rows],'.-');ax.set(xlabel='T',title=field);ax.grid(alpha=.3)
fig.tight_layout();fig.savefig(R/'WINDOW_TRENDS_DOMAIN8H.svg');plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(12,4))
for ax,axis in zip(axes,('x','y')):
    for i in (10,11):
        curve=[r for r in correlations if r['window']==i and r['axis']==axis]
        ax.plot([r['delta_m'] for r in curve],[r['R_uu'] for r in curve],'.-',label=f'{2*i-2}-{2*i}T')
    ax.axhline(0,color='gray');ax.axhline(.1,color='red',linestyle=':');ax.axhline(-.1,color='red',linestyle=':');ax.set(xlabel='separation m',ylabel='R_uu',title=axis);ax.legend();ax.grid(alpha=.3)
fig.tight_layout();fig.savefig(R/'CORRELATION_DOMAIN8H.svg');plt.close(fig)
print(json.dumps(result,ensure_ascii=False))
