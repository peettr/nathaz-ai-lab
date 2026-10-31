#!/usr/bin/env python3
"""CRC-side OpenFOAM patchProbes postprocessor for frozen T03 v1.2.
Usage: python3 analyze_T03.py ROOT/B0 ROOT/B1 OUT.json [--candidate ROOT/C]
Run on CRC, not 工作站. Requires numpy. Censored scales are null, never a finite guess.
"""
import argparse, json, math, re
from pathlib import Path
import numpy as np
NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?'
Z = (.1,.3,.5,.9,1.5)
COMP = ('xx','xy','xz','yy','yz','zz')

def read_vectors(path):
    # Probe files are ~0.6 GB. Stream and retain only the frozen 0.005 s grid;
    # never construct 240k Python arrays or load four complete files at once.
    rows=[]; previous=None; kept=0
    with path.open() as fh:
        for line in fh:
            if not line.strip() or line.startswith('#'): continue
            t=float(line.split(None,1)[0])
            if t<5.-1e-8 or t>120.+1e-8: continue
            tick=round(t/.005)
            if abs(t-tick*.005)>1e-7: continue
            if previous is not None and t<=previous: raise ValueError(f'nonmonotone retained time {path}: {t}')
            vals=np.fromstring(line.translate(str.maketrans('()','  ')),sep=' ')
            if len(vals)!=151: raise ValueError(f'{path}: expected time+50 vectors, got {len(vals)}')
            rows.append(vals); previous=t; kept+=1
    if not rows: raise ValueError(f'empty {path}')
    a=np.asarray(rows)
    return a[:,0], a[:,1:].reshape(-1,5,10,3)

def target(case):
    p=case/'constant/boundaryData/inlet'
    points=np.array([list(map(float,re.findall(NUM,line))) for line in (p/'points').read_text().splitlines() if line.lstrip().startswith('(') and len(re.findall(NUM,line))==3])
    def field(name,n):
        text=(p/name).read_text().splitlines()
        return np.array([list(map(float,re.findall(NUM,line))) for line in text if len(re.findall(NUM,line))==n and (n>1 or line.strip() not in ('164',))])
    u=field('U',1).ravel(); r=field('R',6); l=field('L',9)
    if len(points)!=len(u) or len(r)!=len(u): raise ValueError('target arrays mismatch')
    return {str(z): {'U':float(np.interp(z,points[:,2],u)), 'R':dict(zip(COMP,(float(np.interp(z,points[:,2],r[:,i])) for i in range(6)))), 'L_matrix':np.stack([np.interp(z,points[:,2],l[:,i]) for i in range(9)]).reshape(3,3).tolist()} for z in Z}

def first_zero_integral(x,dx):
    x=np.asarray(x,dtype=float)
    if len(x)<4 or not np.all(np.isfinite(x)) or x[0]<=0: return {'value_m':None,'censored':True,'reason':'insufficient_or_nonfinite'}
    rho=x/x[0]
    crossing=np.flatnonzero(rho[1:]<=0)
    if len(crossing)==0: return {'value_m':None,'censored':True,'lower_bound_m':float(np.trapz(rho,dx=dx)),'max_lag_m':float((len(x)-1)*dx)}
    j=int(crossing[0])+1
    frac=rho[j-1]/(rho[j-1]-rho[j])
    val=np.trapz(rho[:j],dx=dx)+0.5*rho[j-1]*frac*dx
    return {'value_m':float(val),'censored':False,'zero_lag_m':float((j-1+frac)*dx)}

def autocov(series, maxlag):
    # Series: time x probes. Remove each probe's temporal mean; FFT with pair-count normalization.
    x=series-series.mean(axis=0)
    n=len(x); size=1 << (2*n-1).bit_length()
    ft=np.fft.rfft(x,n=size,axis=0)
    corr=np.fft.irfft((ft*ft.conj()).real,n=size,axis=0)[:maxlag+1]
    return (corr/(n-np.arange(maxlag+1))[:,None]).mean(axis=1)

def spatial_cov(x, t, psi, speed):
    # input x: time x 10 y probes; sample all available pairs at fixed y separation.
    dt=float(np.median(np.diff(t))); dy=.2; sin=math.sin(psi); cos=math.cos(psi)
    vals=[float(np.mean(x*x))]
    for lag in range(1,10):
        d=lag*dy; s=d*cos; tau=s*math.tan(psi)/speed if speed>0 else 0.
        steps=tau/dt; k=int(math.floor(steps)); f=steps-k
        a=x[:len(t)-k-1,:10-lag]
        b=(1-f)*x[k:len(t)-1,lag:]+f*x[k+1:,lag:]
        vals.append(float(np.mean(a*b)))
    return first_zero_integral(vals,dy*cos)

def load(case, requested_psi):
    files=sorted((case/'postProcessing/InletPatch').glob('*/U'))
    if len(files)!=1: raise ValueError(f'expected one probe file {case}, got {files}')
    t,v=read_vectors(files[0]); mask=t>=5.
    t,v=t[mask],v[mask]
    if len(t)<20 or t[-1]<119.99: raise ValueError(f'incomplete 5-120 s samples: {case}, last={t[-1] if len(t) else None}')
    dt=float(np.median(np.diff(t)))
    if not np.allclose(np.diff(t),dt,rtol=.01,atol=1e-6): raise ValueError(f'irregular times in {case}')
    # Original solver often writes 0.0005 s. Decimate onto 0.005 s for frozen analysis.
    stride=int(round(.005/dt))
    if stride<1 or abs(stride*dt-.005)>1e-6: raise ValueError(f'cannot decimate {dt} to 0.005')
    t,v=t[::stride],v[::stride]; out={}
    for iz,z in enumerate(Z):
        psi=math.radians(requested_psi(z)); c,s=math.cos(psi),math.sin(psi)
        raw=v[:,iz,:,:]; local=[邮箱]([[c,-s,0],[s,c,0],[0,0,1]])
        m=local.mean(axis=(0,1)); mean_global=raw.mean(axis=(0,1))
        fluct=local-local.mean(axis=0,keepdims=True)
        cov=np.einsum('tyi,tyj->ij',fluct,fluct)/fluct.shape[0]/fluct.shape[1]
        R=dict(zip(COMP, (cov[0,0],cov[0,1],cov[0,2],cov[1,1],cov[1,2],cov[2,2])))
        speed=float(np.linalg.norm(mean_global[:2]))
        lx={}; ly={}
        # Max 1/3 record length avoids noise-dominated long-lag tails.
        for i,k in enumerate(('x','y','z')):
            series=fluct[:,:,i]
            cx=autocov(series,min(len(t)//3,6000))
            lx[k]=first_zero_integral(cx,.005*speed)
            ly[k]=spatial_cov(series,t,psi,speed)
        out[str(z)]={'z_m':z,'target_psi_deg':requested_psi(z),'mean_global_mps':mean_global.tolist(),'mean_local_mps':m.tolist(),'mean_direction_deg':float(math.degrees(math.atan2(mean_global[1],mean_global[0]))),'direction_abs_error_deg':abs((math.degrees(math.atan2(mean_global[1],mean_global[0]))-requested_psi(z)+180)%360-180),'R_local':{k:float(val) for k,val in R.items()},'Lx_local':lx,'Ly_local':ly}
    return {'sampling_dt_raw_s':dt,'sampling_dt_analysis_s':float(np.median(np.diff(t))),'interpolation_dt_s':float(np.median(np.diff(t))),'record_last_s':float(t[-1]),'heights':out}

def compare(a,b):
    out={}
    for z,one in a['heights'].items():
        base=b['heights'][z]
        rr={k:(one['R_local'][k]-base['R_local'][k])/abs(base['R_local'][k]) for k in ('xx','yy','zz')}
        def rho(r,k):
            i,j=k
            den=math.sqrt(r[i+i]*r[j+j])
            return r[k]/den if den>0 else None
        rc={k:(abs(rho(one['R_local'],k)-rho(base['R_local'],k))
               if rho(one['R_local'],k) is not None and rho(base['R_local'],k) is not None else None)
            for k in ('xy','xz','yz')}
        ll={}
        for key in ('Lx_local','Ly_local'):
            ll[key]={}
            for comp in ('x','y','z'):
                x,y=one[key][comp]['value_m'],base[key][comp]['value_m']
                ll[key][comp]={'relative_delta':(x-y)/abs(y) if x is not None and y not in (None,0) else None,'censored':x is None or y is None}
        direction_delta=abs((one['mean_direction_deg']-base['mean_direction_deg']+180)%360-180)
        speed_one=math.hypot(*one['mean_global_mps'][:2]); speed_base=math.hypot(*base['mean_global_mps'][:2])
        out[z]={'direction_abs_delta_deg':direction_delta,
                'direction_abs_error_target_deg':one['direction_abs_error_deg'],
                'mean_speed_relative_delta':(speed_one/speed_base-1) if speed_base>0 else None,
                'R_diagonal_relative_delta':rr,'rho_offdiagonal_abs_delta':rc,
                'scale_relative_delta_reference_only':ll}
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('B0',type=Path); ap.add_argument('B1',type=Path); ap.add_argument('output',type=Path); ap.add_argument('--B0prime',type=Path); ap.add_argument('--candidate',type=Path); a=ap.parse_args()
    t=target(a.B0); b0=load(a.B0,lambda z:0.); b1=load(a.B1,lambda z:20*z/1.8)
    result={'schema':'L22_6_T03_v1_2','source':'E7 TInF 8737a0d5','method':'5-120s; 0.005s decimation; first-zero trapezoid; yprime spacetime Taylor shift via linear interpolation; off-diagonal rho absolute delta','target':t,'B0':b0,'B1':b1,'B1_vs_B0':compare(b1,b0)}
    if a.B0prime:
        result['B0prime']=load(a.B0prime,lambda z:0.)
        result['noise_floor_B0prime_vs_B0']=compare(result['B0prime'],b0)
    if a.candidate:
        result['candidate']=load(a.candidate,lambda z:20*z/1.8)
        result['candidate_vs_B0']=compare(result['candidate'],b0)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(a.output),'heights':list(b0['heights']),'B1_direction_errors':{k:v['direction_abs_error_deg'] for k,v in result['B1_vs_B0'].items()}}))
if __name__=='__main__': main()
