#!/usr/bin/env python3
"""Case III yaw-gate evidence, no invalid load plotted."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
h=Path(__file__).resolve().parent
out=h/'yaw_gate_A2_III_offset.png'
if out.exists():raise RuntimeError('refuse overwrite')
p=Path('./lab_a3/downburst_ff/segment_a2_v1/run_III_offset_feedback/NREL-5MW.out')
with p.open() as f:
    for i,line in enumerate(f):
        if i==6:c=line.split();break
names=('Time','NacYaw','Wind1VelX','Wind1VelY')
t,y,u,v=np.loadtxt(p,skiprows=8,usecols=[c.index(x) for x in names]).T
wd=np.degrees(np.arctan2(v,u));i=wd.argmax()
fig,ax=plt.subplots(figsize=(9,4));ax.plot(t,wd,label='rotor wind direction',lw=1);ax.plot(t,y,label='NacYaw (measured)',lw=1)
ax.scatter([t[i],t[i]],[wd[i],y[i]],s=15,color=['tab:blue','tab:orange']);ax.annotate(f'lag {wd[i]-y[i]:.1f}°', (t[i],wd[i]),xytext=(5,-25),textcoords='offset points')
ax.set(xlabel='simulation time [s]',ylabel='angle [deg]',title='Case III: yaw enabled but does not track fast direction change');ax.grid(alpha=.3);ax.legend()
fig.text(.02,.01,'Data: Nguyen (2012) analytic Case III field; OpenFAST 5.0.0 NREL 5MW + patched ROSCO 2.10.6. No load validity claim.',fontsize=8)
fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out,dpi=160);print(out)
