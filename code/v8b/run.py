"""v8b interface checks on frozen v8 scoring/tuning members; CRC formal only."""
import argparse,json,os,time
from dataclasses import asdict
import numpy as np
from plant import Params,Plant,Z,profile,equilibrium,score,commands
import reference_plant_v8 as old

EVENTS=[(.15,1.),(.15,3.),(.15,5.),(.15,7.),(.20,1.),(.20,3.),(.20,5.),(.20,7.),(.30,1.),(.30,3.),(.30,5.),(.30,7.)]
ROOT=os.path.dirname(os.path.abspath(__file__))

def regression():
    rng=np.random.default_rng(888); out=[]
    for i in range(3):
        p=Params(**{**asdict(Params()),'b':float(rng.uniform(.2,.6)),'s_q':float(rng.uniform(0,.8))})
        n=120;rows=rng.uniform(-4,17,(8,n));main=rng.uniform(2,15,n);terrain=rng.uniform(0,.16,2)
        left=old.Plant(old.Params(**asdict(p))).run(main,rows,terrain,n/p.fs)['series']
        right=Plant(p).run(main,rows,terrain,n/p.fs)['series']
        out.append(float(np.max(np.abs(left-right))))
    return {'max_differences':out,'pass':all(v==0 for v in out)}

def c4(scoring,smoke=False):
    # Deliberately joint nearest grid point; never substitute marginal rectangles.
    records=[]; members=scoring[:1] if smoke else scoring
    for entry in members:
        p=Params(**entry['params']); idx=entry['index'];grid=[]
        for rough in (0.,.08,.16):
            for amp in (0.,2.,5.):
                for lam in (.5,3.,10.):
                    if smoke and len(grid)>=2:break
                    result=score(p,8.,np.full(8,8.),np.array([rough,rough]),duration=30. if smoke else 600.,
                                 amplitude=np.full(8,amp),wavelength=np.full(8,lam),
                                 seeds=(1001,) if smoke else (1001,1002,1003),
                                 command_seeds=(2001,) if smoke else (2001,2002,2003))
                    grid.append({'roughness':rough,'amplitude':amp,'wavelength':lam,
                                 'Iu':float(result['Iu'][3]),'Lux':float(result['Lux'][3]),
                                 'valid':result['valid'],'min_ratio':result['min_ratio'],
                                 'clip_fraction':result['clip_fraction']})
                if smoke and len(grid)>=2:break
            if smoke and len(grid)>=2:break
        candidates=[g for g in grid if g['valid']]
        events=[]
        for iu,lux in EVENTS:
            if not candidates:
                events.append({'target':[iu,lux],'nearest':None});continue
            best=min(candidates,key=lambda g:max(abs(g['Iu']/iu-1),abs(g['Lux']/lux-1)))
            ei=abs(best['Iu']/iu-1);el=abs(best['Lux']/lux-1)
            events.append({'target':[iu,lux],'nearest':best,'rel_Iu':ei,'rel_Lux':el,
                           'both_10pct':ei<=.1 and el<=.1,'both_20pct':ei<=.2 and el<=.2})
        records.append({'index':idx,'events':events,'grid':grid,'both_10pct':sum(e.get('both_10pct',False) for e in events),
                        'both_20pct':sum(e.get('both_20pct',False) for e in events)})
        print('PROGRESS',int(65*len(records)/len(members)),flush=True)
    return records

def c5(scoring,smoke=False):
    result=[]
    for item in (scoring[:1] if smoke else scoring):
        p=Params(**item['params'])
        for duration in ((30.,) if smoke else (600.,1800.)):
            x=score(p,8.,np.full(8,8.),np.array([.04,.08]),duration=duration)
            result.append({'index':item['index'],'duration_s':duration,'seed_sd_u_Iu_Lux':x['seed_sd'].tolist(),
                           'valid':x['valid'],'min_ratio':x['min_ratio']})
    return result

def envelope(p,scenario,family):
    # Enumeration of binary row extrema and a 69-point main-fan grid, not a global certificate.
    W=Plant(p).weights;h=profile(p,np.zeros(2));j=np.arange(256)[:,None]
    masks=((j>>np.arange(8))&1).astype(bool)
    rows=np.where(masks,20.,-17.) if family=='independent' else np.array([[-17.]*8,[20.]*8])
    avg=rows.mean(axis=1);contrast=(rows-avg[:,None])@W.T
    def bounds(n):
        q=equilibrium(n,avg,p)
        baseline=q[:,None]*h[None,:]
        velocity=baseline+p.c*contrast
        feasible=np.all(velocity>=.5*baseline-1e-12,axis=1)
        if not feasible.any():return None
        v=velocity[feasible,3]
        return [float(v.min()),float(v.max())]
    if scenario=='variable':
        rr=[bounds(n) for n in np.linspace(0,17,69)]
        rr=[r for r in rr if r is not None]
        low=min(r[0] for r in rr);high=max(r[1] for r in rr)
        return {'joint_feasible':low<=2.3 and high>=11.,'range':[low,high], 'N':None}
    for n in np.linspace(0,17,69):
        rr=bounds(n)
        if rr is not None and rr[0]<=2.3 and rr[1]>=11.:
            return {'joint_feasible':True,'range':rr,'N':float(n)}
    return {'joint_feasible':False,'N':None,'range':None}

def c6(scoring,smoke=False):
    out=[]
    for item in (scoring[:1] if smoke else scoring):
        p=Params(**item['params'])
        for scenario in ('constant','variable'):
            for family in ('shared','independent'):
                out.append({'index':item['index'],'scenario':scenario,'family':family,
                            'YM02_envelope':envelope(p,scenario,family)})
    return out

def run(smoke=False):
    with open(os.path.join(ROOT,'scoring.json')) as f:scoring=json.load(f)
    with open(os.path.join(ROOT,'tuning.json')) as f:tuning=json.load(f)
    reg=regression()
    if not reg['pass']:raise RuntimeError('noiseless regression mismatch')
    # Exercise 27 parameters and arbitrary periodic time series, including validity flags.
    p=Params();rng=np.random.default_rng(812)
    cmd=commands(p,8.,np.full(8,8.),np.full(8,2.),np.full(8,3.),np.zeros(2),3.,2001)
    pulse=score(p,8.,np.full(8,8.),np.zeros(2),duration=3.,amplitude=np.full(8,2.),
                wavelength=np.full(8,3.),seeds=(1001,),command_seeds=(2001,))
    periodic=score(p,8.,rng.uniform(6,10,(8,20)),np.zeros(2),duration=3.,seeds=(1001,),command_seeds=(2001,))
    checks={'regression':reg,'pulse_clip_fraction':cmd['clip_fraction'],'pulse_valid':pulse['valid'],
            'periodic_valid':periodic['valid'],'pulse_min_ratio':pulse['min_ratio'],
            'periodic_min_ratio':periodic['min_ratio'],'scoring_members':len(scoring),'tuning_members':len(tuning)}
    if smoke:return {'smoke':checks}
    t=time.time(); joint=c4(scoring);repeat=c5(scoring);env=c6(scoring)
    return {'checks':checks,'C4_joint':joint,'C5_repeat':repeat,'C6_envelope':env,
            'elapsed_compute_s':time.time()-t,'no_independent_validation':True}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out');ap.add_argument('--smoke',action='store_true');args=ap.parse_args()
    if args.smoke:print(json.dumps(run(True)));raise SystemExit(0)
    if not args.out:ap.error('--out required')
    result=run()
    os.makedirs(args.out,exist_ok=False)
    with open(os.path.join(args.out,'metrics.json'),'w') as f:json.dump(result,f,indent=2)
    print('DONE',len(result['C4_joint']),len(result['C6_envelope']),flush=True)
