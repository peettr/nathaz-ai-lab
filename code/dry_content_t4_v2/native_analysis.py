#!/usr/bin/env python3
"""Analyze native continuous T17-B producer. No solver restarts or synthetic statistics."""
import csv, json, math, pathlib, struct, os
from assert_T17 import spread
NX,NY,NZ=(int(os.environ.get('T17_TEST_NX',512)),int(os.environ.get('T17_TEST_NY',256)),64)
AREA=NX*NY
USTAR=.27810
F=.00120843

def rows(path):
    with open(path,newline='') as f: return [{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]

def integral_at(ledger,step):
    """Linearly interpolate the native cumulative force integral at a T/2 edge."""
    if step<ledger[0]['step'] or step>ledger[-1]['step']:raise ValueError('uncovered integral edge')
    for a,b in zip(ledger,ledger[1:]):
        if a['step']<=step<=b['step']:
            w=(step-a['step'])/(b['step']-a['step'])
            return a['ground_drag_integral_lattice']*(1-w)+b['ground_drag_integral_lattice']*w
    raise ValueError('integral gap')

def window(ledger,lo,hi,unit_u):
    data=[r for r in ledger if lo<r['step']<=hi]
    if len(data)<2: raise ValueError(f'window has <2 samples {lo}:{hi}')
    # The ground drag is integrated at its own native cadence, not averaged
    # over irregularly spaced ledger samples; sign is positive opposing +x.
    meanpx=sum(r['px_lattice'] for r in data)/len(data)
    drag=(integral_at(ledger,hi)-integral_at(ledger,lo))/(hi-lo)
    rho=sum(r['rho_mean_lattice'] for r in data)/len(data)
    if rho<=0 or drag<=0: raise ValueError('nonpositive native rho/drag')
    tau=drag/AREA*unit_u**2*rho
    return {'momentum':meanpx,'tau_x':tau,'ustar':math.sqrt(tau/rho)}

def v0_pair(directory,end,half,unit_u):
    ledger=rows(directory/'ledger.csv')
    if ledger[-1]['step']<end:raise ValueError('incomplete V0 ledger')
    return [window(ledger,end-2*half,end-half,unit_u),window(ledger,end-half,end,unit_u)]

def native_unit_u(directory):
    with (directory/'timing.csv').open(newline='') as f:timing=list(csv.DictReader(f))
    if not timing:raise ValueError('missing native units record')
    vals={float(row['velocity_si_per_lattice']) for row in timing}
    if len(vals)!=1 or next(iter(vals))<=0:raise ValueError('inconsistent native units')
    return next(iter(vals))

def decide(directory,attempt,end,half,smoke=False):
    pair=v0_pair(directory,end,half,native_unit_u(directory))
    passed=all(spread(pair[0][k],pair[1][k])<=.02 for k in ('momentum','tau_x','ustar'))
    decision='pass' if passed else 'extend'
    if smoke:decision='pass'
    (directory/f'v0_{attempt}.decision').write_text(decision+'\n')
    return pair,decision

def summarize(directory):
    with (directory/'timing.csv').open(newline='') as f: timing=list(csv.DictReader(f))
    if not timing: raise ValueError('missing V0 attempts')
    half=int(timing[0]['half_T_steps']);attempts=[];unit_u=native_unit_u(directory)
    for a in timing:attempts.append(v0_pair(directory,int(a['equilibrium_end_step']),half,unit_u))
    start=int((directory/'statistics_start.txt').read_text())
    ledger=rows(directory/'ledger.csv')
    if ledger[-1]['step'] < start+4*half: raise ValueError('incomplete 2T interval')
    profile=rows(directory/'profiles.csv')
    pu={str(k):[] for k in range(1,65)}
    for r in profile:
        if start<r['step']<=start+4*half: pu[str(int(r['k']))].append(r['u_x_mean_si'])
    if any(not x for x in pu.values()):raise ValueError('missing native profile level')
    profile_u={k:sum(v)/len(v) for k,v in pu.items()}
    plane=directory/'planes.bin';frame_bytes=2*AREA*3*4
    size=plane.stat().st_size
    if size%frame_bytes:raise ValueError('truncated plane binary')
    nframes=size//frame_bytes
    # C++ writes frames at absolute step%200 == 0 inside the statistics interval.
    sample_stride=int(timing[0]['sample_stride'])
    # The large-domain producer archives frames from the first spin-up step,
    # whereas the small-domain producer began its plane file at statistics_start.
    # Validate the complete absolute-step axis before slicing the 2T interval.
    all_steps=list(range(sample_stride,start+4*half+1,sample_stride))
    steps=[s for s in all_steps if start<s<=start+4*half]
    if nframes!=len(all_steps):raise ValueError(f'plane frames {nframes} != full-run {len(all_steps)}')
    import numpy as np
    blocks=[];cxy=[]
    with plane.open('rb') as f:
        for b in range(4):
            lo,hi=start+b*half,start+(b+1)*half
            frame3=[];frame10=[]
            for step in [s for s in steps if lo<s<=hi]:
                offset=(step//sample_stride-1)*frame_bytes
                f.seek(offset)
                arr=np.frombuffer(f.read(frame_bytes),dtype='<f4').reshape((2,NY,NX,3)).astype('float64')
                frame3.append(arr[0]);frame10.append(arr[1])
            if not frame3:raise ValueError('empty T/2 block')
            p3=np.stack(frame3);p10=np.stack(frame10)
            mean=p10.mean(axis=(0,1,2))
            fluct=p10-mean
            var=(fluct**2).mean(axis=(0,1,2))
            k_res=float(var.sum()/2)
            ux=p10[...,0];uxfluct=fluct[...,0];den=float(var[0])
            if den<=0:raise ValueError('zero streamwise variance')
            rx=float((uxfluct*np.roll(uxfluct,NX//2,axis=2)).mean()/den)
            ry=float((uxfluct*np.roll(uxfluct,NY//2,axis=1)).mean()/den)
            cxy.append((rx,ry))
            blocks.append({'k_res_z9p5':k_res,'u_k3':float(p3[...,0].mean()),
                           'u_x_mean_z9p5':float(mean[0]),'u_x_variance_z9p5':den})
    # Correlation over full 2T, centered on full-window horizontal-time mean.
    # Weighted average of block correlations is only an approximation to this;
    # accumulate full-window moments using all recorded frames instead.
    # The four blocks have near-equal sampling but not necessarily equal counts.
    with plane.open('rb') as f:
        correlations=[];allx=[]
        for step in steps:
            f.seek((step//sample_stride-1)*frame_bytes+AREA*3*4)
            a=np.frombuffer(f.read(AREA*3*4),dtype='<f4').reshape((NY,NX,3))[:,:,0].astype('float64')
            allx.append(a)
        a=np.stack(allx);d=a-a.mean();den=float((d*d).mean())
        if den<=0:raise ValueError('zero full-window variance')
        correlations=[float((d*np.roll(d,NX//2,axis=2)).mean()/den),
                      float((d*np.roll(d,NY//2,axis=1)).mean()/den)]
    stat=window(ledger,start,start+4*half,unit_u)
    rho=ledger[-1]['rho_mean_lattice']
    digest=__import__('hashlib').sha256()
    with plane.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): digest.update(chunk)
    return {'v0_attempts':attempts,'stress':{'tau_x_time_mean':stat['tau_x'],'rho':rho},
            'blocks':blocks,'correlations':dict(zip(('rx_half','ry_half'),correlations)),
            'profile_u':profile_u,'native_provenance':{'frames':nframes,'first_step':steps[0],
            'last_step':steps[-1],'statistics_start':start,'statistics_end':start+4*half,
            'half_steps':half,'plane_sha256':digest.hexdigest()}}
