#!/usr/bin/env python3
"""Analyze licensed ROSCO 2.10.6 ABI pulse only; never interpret as downburst."""
from pathlib import Path
import json, shutil, subprocess
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
base=Path('./lab_a3/downburst_ff')
out=Path('./22_Lab/06_Logs/a3_turbine/downburst_ff/licensed_ff_smoke')
out.mkdir(exist_ok=False)
rows={}
for mode in ['feedback','feedforward']:
    root=base/f'ff_smoke_{mode}'
    log=(root/'openfast.log').read_text()
    assert 'OpenFAST terminated normally.' in log and 'ROSCO_FF_INIT' in log
    s=(root/'NREL-5MW.out').read_text().splitlines()
    keys=s[6].split(); data=np.loadtxt(root/'NREL-5MW.out',skiprows=8)
    assert data.shape[1]==len(keys) and data[-1,0]==30
    rows[mode]={k:data[:,keys.index(k)] for k in ['Time','BldPitch1','TwrBsMyt','Wind1VelX']}
    for fn in ['openfast.log','walltime.txt','preview.txt']:
        shutil.copy2(root/fn,out/f'{mode}_{fn}')
    assert '0.13962634 ! PC_MaxRat' in (root/'DISCON.IN').read_text()
    assert str(base/'rosco210_ff_build/libdiscon.so') in (root/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat').read_text()
assert np.allclose(rows['feedback']['Wind1VelX'],rows['feedforward']['Wind1VelX'])
t=rows['feedback']['Time']; band=(t>=10)&(t<=20)
summ={mode:{'pitch_10_20_max_deg':float(v['BldPitch1'][band].max()),'tower_FA_10_20_max_kNm':float(v['TwrBsMyt'][band].max()),'wind_mean_ms':float(v['Wind1VelX'].mean())} for mode,v in rows.items()}
summ['max_pitch_difference_10_20_deg']=float(np.max(np.abs(rows['feedforward']['BldPitch1'][band]-rows['feedback']['BldPitch1'][band])))
assert summ['max_pitch_difference_10_20_deg']>0.1
fig,ax=plt.subplots(3,1,sharex=True,figsize=(9,8))
for mode,v in rows.items():
    ax[0].plot(t,v['Wind1VelX'],label=f'rotor input {mode}')
    ax[1].plot(t,v['BldPitch1'],label=mode)
    ax[2].plot(t,v['TwrBsMyt'],label=mode)
ax[0].plot([0,9,10,17,18,30],[14,14,18,18,14,14],color='black',linestyle='--',label='artificial preview pulse')
for a,y in zip(ax,['wind (m/s)','pitch (deg)','tower FA (kN m)']): a.set_ylabel(y); a.legend(fontsize=8)
ax[-1].set_xlabel('time (s)'); fig.suptitle('ABI test ONLY: constant 14 m/s rotor, artificial preview pulse')
fig.text(.02,.01,'Source: OpenFAST 5.0.0 NREL-5MW onshore outputs; ROSCO 2.10.6 Apache-2.0 local modification. Not downburst data.',fontsize=8)
fig.tight_layout(rect=[0,.03,1,.96]); fig.savefig(out/'licensed_ff_pulse.png',dpi=150)
(out/'smoke_metrics.json').write_text(json.dumps(summ,indent=2)+'\n')
original=Path('./lab_a3/src/rosco-v2.10.6/rosco/controller/src/Controllers.f90')
modified=base/'rosco210_ff_src/src/Controllers.f90'
patch=subprocess.run(['diff','-u',str(original),str(modified)],capture_output=True,text=True)
assert patch.returncode==1
(out/'rosco210_ff.patch').write_text(patch.stdout)
print(json.dumps(summ,indent=2)); print(out)
