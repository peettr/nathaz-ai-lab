#!/usr/bin/env python3
"""Nguyen (2012) eqs 3.2--3.11, 3.21--3.24: deterministic 4D prototype.

Diagnostic ONLY: no Veers turbulence, no OpenFAST loads, no control outcome.
The preview samples the analytic field at different x, not a Taylor-shifted rotor box.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
D = 126.0
@dataclass(frozen=True)
class Case:
    name: str
    urm: float
    trans: float
    zm0: float
    kzm: float
    rm0: float
    krm: float
    t0: float
    t1: float
    x0: float
    y0: float

CASES = (
    Case('I_near',47,12,90,0,1000,1,360,720,-6000,-100),
    Case('III_offset',47,14,70,0,610,.05,540,600,-7570,-610),
)

def field(case, x, y, z, t):
    """Vector wind [u,v,w] m/s at any broadcastable (x,y,z,t); no fluctuation."""
    x, y, z, t = np.broadcast_arrays(np.asarray(x,float),np.asarray(y,float),
                                       np.asarray(z,float),np.asarray(t,float))
    xstorm = case.x0 + case.trans*t
    ystorm = case.y0  # Nguyen cases I/III translate along +x, phi=0
    dx, dy = x-xstorm, y-ystorm
    r = np.hypot(dx,dy)
    rm = case.rm0 + case.krm*t
    zm = case.zm0 - case.kzm*t
    assert np.all(zm > 0)
    c1,c2,alpha = .22,2.75,2.
    rr = r/rm
    e = np.exp((1-rr**(2*alpha))/(2*alpha))
    f = rr*e
    g = (2-rr**(2*alpha))*e
    h = z/zm
    den = np.exp(-c1)-np.exp(-c2)
    p = (np.exp(-c1*h)-np.exp(-c2*h))/den
    q = (zm/rm)*((np.exp(-c1*h)-1)/c1-(np.exp(-c2*h)-1)/c2)/den
    intensity=np.where(t<=case.t0, np.maximum(t,0)/case.t0,
                       np.exp(-(t-case.t0)/case.t1))
    ur=intensity*case.urm*f*p
    uz=intensity*case.urm*g*q
    u=12*(np.maximum(z,0)/90)**.2+ur*np.divide(dx,r,out=np.zeros_like(r),where=r>0)
    v=ur*np.divide(dy,r,out=np.zeros_like(r),where=r>0)
    return u,v,uz

def crossing(t,v,threshold=25):
    ix=np.flatnonzero((v[:-1]<threshold)&(v[1:]>=threshold))
    if not ix.size: return None
    i=ix[0]
    return float(t[i]+(threshold-v[i])*(t[i+1]-t[i])/(v[i+1]-v[i]))

def main():
    t=np.arange(0,801,.25)
    result={}
    fig, axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
    for row,case in enumerate(CASES):
        u,v,w=field(case,0,0,90,t)
        speed=np.hypot(u,v)
        angle=np.rad2deg(np.unwrap(np.arctan2(v,u)))
        t0=crossing(t,speed)
        probes={}
        axes[row,0].plot(t,speed,label='rotor hub')
        axes[row,1].plot(t,angle,label='rotor direction')
        for n in (1,2):
            up,vp,_=field(case,-n*D,0,90,t)
            sp=np.hypot(up,vp)
            t_cross=crossing(t,sp)
            probes[f'{n}D']={'first_cross_25_s':t_cross,'geometric_arrival_lead_s':None if t0 is None or t_cross is None else t0-t_cross}
            axes[row,0].plot(t,sp,label=f'upstream {n}D (independent x)')
        axes[row,0].axhline(25,c='k',lw=.7,ls='--')
        axes[row,0].set_ylabel(f'{case.name}: horizontal speed [m/s]')
        axes[row,1].set_ylabel('direction atan2(v,u) [deg]')
        axes[row,0].legend(fontsize=8,loc='upper right')
        result[case.name]={'hub_first_cross_25_s':t0,'hub_peak_mps':float(speed.max()),'upstream':probes,
                           'parameters':vars(case)}
    for a in axes[-1]: a.set_xlabel('time since touchdown [s]')
    fig.suptitle('Deterministic field preview geometry ONLY — no turbulence/controller/loads\nSource: Nguyen (2012), Ch. 3 eqs 3.2–3.11, 3.21–3.24; Table 4.4 cases I/III')
    fig.tight_layout()
    fig.savefig(OUT/'wind_probe_deterministic.png',dpi=150)
    (OUT/'wind_probe.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
