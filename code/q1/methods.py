"""Q1 A0--A4: methods see only finite noisy measurements, never model parameters.

No import of reference.py, reference candidate commands, or object members here.
Stateful object and objective targets are only used by the external driver.
"""
import numpy as np
from common import LO,HI,BASE,vector_command,metrics,errors,normalized,Z,target
from gca_spectrum import update as warp_update,warped_rows

SCHEDULE=[30.]*10+[60.]*14+[200.]
assert sum(SCHEDULE)+25*45==2465

def init(event):
    """Pinyochotiwong PDF pp.71--77 initialization adapted to 27-D family.
    Fan follows u_ref, FFM initial mean 1 m/s, terrain 10 mm; spectral
    amplitude 1 m/s and wavelength 2 m are explicit assumptions.
    """
    x=BASE.copy();x[0]=6.;x[1:9]=1.;x[9:17]=1.;x[17:25]=event[3];x[25:]=.01
    return np.clip(x,LO,HI)

def probe(base,rng,scale=.13):
    x=base.copy();idx=rng.choice(27,size=6,replace=False)
    x[idx]=np.clip(x[idx]+rng.normal(0,scale,len(idx))*(HI-LO)[idx],LO[idx],HI[idx])
    return x

def grouped_probe(base,iteration,scale=.13):
    """Seven prespecified actuator groups; paired signs across probe rounds."""
    direction=np.zeros(27)
    group=iteration%7
    if group==0:direction[0]=1
    elif group==1:direction[1:9]=1
    elif group==2:direction[1:5]=1;direction[5:9]=-1
    elif group==3:direction[9:17]=1
    elif group==4:direction[17:25]=1
    elif group==5:direction[25]=1
    else:direction[26]=1
    sign=1 if (iteration//7)%2==0 else -1
    return np.clip(base+sign*scale*(HI-LO)*direction,LO,HI)

def model_step(X,Y,x,desired,regularization,variances=None,step_cap=.2):
    X=np.asarray(X);Y=np.asarray(Y)
    if len(X)<2:return x
    xd=X[-1];yd=Y[-1]
    dx=(X[:-1]-xd)/(HI-LO);dy=Y[:-1]-yd
    # Inverse measurement-variance weights estimated from finite sample blocks.
    if variances is None:weight=np.ones(len(yd))
    else:
        estimate=np.nanmedian(np.asarray(variances),axis=0)
        weight=np.sqrt(1/np.maximum(estimate,1e-4))
        weight=np.clip(weight,1e-2,10.)
    dy=dy*weight;residual=(desired-yd)*weight
    # Ridge on dual for underdetermined probes; no access to hidden plant.
    try:
        gram=[邮箱]+regularization*np.eye(len(dx))
        coeff=[邮箱](gram,dy)
        update=[邮箱](coeff.T@coeff+regularization*np.eye(len(yd)),residual)
        # The residual uses Y[-1], measured at X[-1]; anchor the update there.
        return np.clip(xd+(HI-LO)*np.clip(update,-step_cap,step_cap),LO,HI)
    except np.linalg.LinAlgError:return x

def gca_step(x,obs,event,hyper,last_input=None,last_measure=None):
    """Three coupled incremental loops; PDF pp.72--75, 119--121.
    Published numerical gains for these loops are absent; every numerical gain
    here is a tunable assumption. Spectrum uses nonnegative additive warping.
    """
    x=x.copy();t=target(event);u=obs['u'];iu=obs['Iu'];lux=obs['Lux']
    ku=hyper.get('K_FFM',.25);kt=hyper.get('K_TF',.01);kv=hyper.get('K_VAF',.08)
    kw=hyper.get('K_warp',.12)
    # Each row receives local mean and vertical slope error, as in p.73.
    for j in range(8):
        z=(j+.5)*3/13;h=int(np.argmin(abs(Z-z)));left=max(0,h-1);right=min(11,h+1)
        err=(t[0,h]-u[h])+((t[0,right]-t[0,left])-(u[right]-u[left]))
        x[1+j]+=ku*err
    x[1:9]=np.clip(x[1:9],LO[1:9],HI[1:9])
    # Fixed FFM working-point offset, not the midpoint of this iteration's rows.
    fc=float(hyper.get('F_c',1.5))
    x[0]+=kv*(x[1:9].mean()-fc)
    # Upstream gradient; downstream additionally handles sigma_u error.
    du=(t[0,3]-t[0,0])-(u[3]-u[0]); ds=(t[1,3]*t[0,3]-iu[3]*u[3])
    x[25]+=kt*du;x[26]+=kt*(du+ds)
    # p.119--121 spectral warping: PSD ratio -> amplitude sqrt(Psd ratio),
    # wavelength adjusted by measured/target integral scale. PSD floor and
    # lowpass attenuation prevent negative PSD; same scale for all 8 rows.
    ratio=max(0.,np.clip(np.mean(t[1]/np.maximum(iu,1e-5)),0,5))
    gain=np.sqrt(max(0.,1+kw*(ratio*ratio-1)))
    x[9:17]*=gain
    x[17:25]*=np.clip(1+kw*(np.mean(t[2]/np.maximum(lux,.05))-1),.5,1.5)
    return np.clip(x,LO,HI)

def measure(plant,x,event,wait,duration,seed,command_seed,warp=None):
    """One continuous command loading with same phase across wait and sample."""
    cmd=vector_command(x,plant.p,wait+duration,command_seed)
    nw=int(round(wait*plant.p.fs));rows=warped_rows(x,plant.p,wait+duration,command_seed,warp) if warp is not None else cmd['rows']
    # Reset validity bookkeeping only, never the physical state or RNG.
    plant.valid=True;plant.min_ratio=float('inf')
    plant.run(cmd['main'],rows[:,:nw],cmd['terrain'],wait,sample=False)
    out=plant.run(cmd['main'],rows[:,nw:],cmd['terrain'],duration,seed=seed)
    m=metrics(out['series'],1/plant.p.fs)
    e=errors(m,event)
    return m,e,bool(out['valid']),float(out['min_ratio']),out['series']

def run_sequence(plant,event,method,hyper=None,seed=1,smoke=False,literal=False):
    """Run full 2465-s sequence, including 25 waits, without resetting state.
    Every method chooses using only finite noisy samples; reference commands
    are not imported. Invalid commands remain in logs but cannot be selected.
    """
    if method not in ('A0','A1','A2','A3','A4'):raise ValueError(method)
    hyper={} if hyper is None else dict(hyper)
    rng=np.random.default_rng(seed);x=init(event)
    X=[];Y=[];V=[];records=[];best=None;best_error=float('inf');remaining=1340.
    probes=int(hyper.get('probes',4));reg=float(hyper.get('ridge',.08))
    design=hyper.get('probe_design','random')
    if design not in ('random','grouped'):raise ValueError(design)
    prev_error=1.;warp=None;best_warp=None;integral=np.zeros(8)
    # Backtracking is based only on previously measured, valid commands.
    step_cap=.2;last_valid=x.copy();last_valid_score=float('inf')
    a1_baseline=x.copy();a1_trial=None;a1_fixed=None
    if literal:
        if method!='A2':raise ValueError('literal gain applies only to A2')
        hyper={'K_FFM':3.,'K_TF':3.,'K_VAF':3.,'K_warp':30.}
    for k in range(1 if smoke else 25):
        if smoke:duration=2.
        elif method=='A4':
            left=25-k
            if left==1:duration=remaining
            else:
                # Allocation based only on past noisy residual; keep future minimum.
                proposed=(remaining/left)*np.clip(prev_error/.8,.55,1.5)
                duration=float(np.clip(round(proposed*20)/20,10,remaining-10*(left-1)))
        else:duration=SCHEDULE[k]
        if method in ('A1','A3','A4') and k<probes:
            candidate=(grouped_probe(x,k-1) if design=='grouped' else probe(x,rng)) if k else x.copy()
        elif method=='A0':candidate=x.copy()
        elif method=='A2':candidate=x.copy()
        elif method=='A1':
            if a1_fixed is not None:
                candidate=a1_fixed.copy()
            elif a1_trial is None:
                a1_trial=model_step(X,Y,x,target(event).reshape(-1),reg,V)
                candidate=a1_trial.copy()
            else:
                # Each rejected inverse-design trial consumes a full round.
                a1_trial=np.clip(a1_baseline+.5*(a1_trial-a1_baseline),LO,HI)
                candidate=a1_trial.copy()
        else:
            candidate=model_step(X,Y,last_valid,target(event).reshape(-1),reg,V,step_cap=step_cap)
        # Fresh method seed per sample: measurement drift resampled by Plant.run.
        obs,e,valid,min_ratio,series=measure(plant,candidate,event,1. if smoke else 45.,duration,
            seed=int(rng.integers(1,2**31)),command_seed=int(rng.integers(1,2**31)),
            warp=warp if method=='A2' else None)
        score=normalized(e);prev_error=score
        if method in ('A3','A4'):
            if not valid:
                # Never keep issuing an invalid command as the next base point.
                x=last_valid.copy();step_cap=max(.0125,step_cap/2)
            else:
                if score<last_valid_score:step_cap=min(.2,step_cap*1.5)
                last_valid=candidate.copy();last_valid_score=score;x=candidate.copy()
        elif method=='A1' and k>=probes:
            if valid:
                a1_fixed=candidate.copy();x=candidate.copy()
            else:
                x=a1_baseline.copy()
        # Out-of-domain measurements have no physical meaning for local fitting.
        if valid and method in ('A1','A3','A4'):
            X.append(candidate.copy());Y.append(np.concatenate([obs[n] for n in ('u','Iu','Lux')]))
            blocks=np.array_split(series,5,axis=-1)
            samples=[metrics(block,1/plant.p.fs) for block in blocks]
            V.append(np.var([np.concatenate([m[n] for n in ('u','Iu','Lux')]) for m in samples],axis=0,ddof=1))
        if valid and score<best_error:
            best_error=score;best=candidate.copy();best_warp=None if warp is None else warp.copy()
        records.append({'iteration':k+1,'duration_s':duration,'time_used_s':sum(r['duration_s']+(1 if smoke else 45) for r in records)+duration+(1 if smoke else 45),
                        'e':e.tolist(),'normalized_error':score,'valid':valid,'min_ratio':min_ratio,
                        'command':candidate.tolist(),
                        'warp':None if warp is None else warp.tolist()})
        if method=='A2':
            warp=warp_update(warp,series,event,hyper.get('K_warp',.12))
            x=gca_step(candidate,obs,event,hyper)
            if literal:
                # Position-form integral of row mean errors, Ki=1 per iteration.
                for j in range(8):
                    h=int(np.argmin(abs(Z-(j+.5)*3/13)))
                    integral[j]+=target(event)[0,h]-obs['u'][h]
                x[1:9]=np.clip(x[1:9]+integral,LO[1:9],HI[1:9])
        remaining-=duration
    if not smoke and not np.isclose(sum(r['duration_s']+45 for r in records),2465.,atol=1e-6):
        raise AssertionError('budget exceeded or unused')
    return {'method':method,'event':event[0],'best_command':None if best is None else best.tolist(),
            'best_warp':None if best_warp is None else best_warp.tolist(),
            'last_command':records[-1]['command'],'last_warp':None if warp is None else warp.tolist(),'best_iteration':None if best is None else int(np.argmin([r['normalized_error'] if r['valid'] else np.inf for r in records]))+1,
            'iterations':records,'total_time_s':3. if smoke else 2465.,'valid_rounds':sum(r['valid'] for r in records)}
