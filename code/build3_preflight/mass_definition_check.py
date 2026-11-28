#!/usr/bin/env python3.10
"""Read-only source-derived Esoteric-Pull check of M_all inventory on two phases.
Does not replace target-GPU testing; shows whether raw all-slot sum is an invariant.
"""
from pathlib import Path
import json
import numpy as np
SRC=Path('./21_Digital_Wind_Tunnel/04_Handoffs/For_R21.4_GroundWM_Review_20261116/emu_esoteric_mirror.py')
s=SRC.read_text().split("for v in ('code','alt')")[0]
ns={'__file__':str(SRC)}
exec(compile(s,str(SRC),'exec'),ns)
for k in ('Nx','Ny','N','solid','store_f','feq','mirror','load_f','C','idx'):
    globals()[k]=ns[k]
u0=.035
fl=[n for n in range(N) if not solid[n]]
def init():
    fi=np.zeros((N,19))
    for n in range(N):store_f(fi,n,feq(1.,np.zeros(3) if solid[n] else np.array([u0,0,0])),1)
    return fi
def step(fi,t,mir=True):
    F={n:(mirror(fi,n,t,'alt') if mir else load_f(fi,n,t)) for n in fl}
    new=fi.copy()
    for n in fl:
        f=F[n];rho=f.sum();u=(f@C)/rho
        store_f(new,n,f-(f-feq(rho,u))/.8,t)
    return new,sum(F[n].sum() for n in fl)
results=[]
for mir in (False,True):
    for parity in (0,1):
        fi=init()
        if parity:fi,_=step(fi,0,mir)
        base=fi.sum(dtype=np.float64)
        vals=[]
        for t in range(parity,parity+8):
            fi,rho=step(fi,t,mir)
            vals.append({'step':t+1,'M_all':float(fi.sum(dtype=np.float64)),
                         'relative_M_all':float((fi.sum(dtype=np.float64)-base)/base),
                         'fluid_rho':float(rho)})
        results.append({'mirror':mir,'phase':parity,'M_initial':float(base),'trace':vals,
                        'max_abs_relative_M_all':max(abs(x['relative_M_all']) for x in vals)})
p=Path(__file__).with_name('mass_definition_check.json')
p.write_text(json.dumps({'source':str(SRC),'representation':'raw stored DDF all slots',
                         'note':'Small source-derived emulator, not requested target-GPU 24^3 cube','cases':results},indent=2)+'\n')
for r in results:print('mirror',r['mirror'],'phase',r['phase'],'max_abs_relative_M_all',r['max_abs_relative_M_all'])
print('output',p)
