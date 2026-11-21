"""L22.6 T01 independent Monte Carlo truth; execute on CRC, not 工作站.
All numerical inputs frozen by delegated T01 request and source template; no LLM network calls.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
import csv, json, time, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from scipy.linalg import expm, solve_continuous_lyapunov
from scipy.optimize import minimize

OUT = Path(__file__).resolve().parent
DT = .02; N = 20000; SEED = 20261021
M=437000.; FS=.32; ZS=.01; KAPPA=245.; IU=.12; MU=.01; BETA=.05; PHI=.5
PF=np.array([-1.6461981787050797,.690763033834006,1.0263004204173023,1.254203536706782])
a0,a1,c0,c1=np.exp(PF); AF=np.array([[0.,1.],[-a0,-a1]]); CF=np.array([c0,c1]); BB=np.zeros((6,6)); BB[5,5]=1.
PFLT=solve_continuous_lyapunov(AF,-np.array([[0.,0.],[0.,1.]]))
FILTER_NORM=float(np.sqrt(CF@PFLT@CF))
WS=2*np.pi*FS
MASS=np.array([[M+BETA*M*PHI**2,-BETA*M*PHI],[-BETA*M*PHI,(MU+BETA)*M]])
MINV=np.linalg.inv(MASS)
SQ=np.array([1.,0.,0.,0.,0.,0.]); SS=np.array([1.,-1.,0.,0.,0.,0.])

def wind(t): return 10+20*np.exp(-((t-300)/60)**2)
def matrix(nu,zd,u):
    wd=nu*WS; md=(MU+BETA)*M; kd=md*wd**2; cd=2*zd*md*wd
    stiff=np.array([[M*WS**2+kd,-kd],[-kd,kd]])
    damp=np.array([[2*ZS*M*WS+KAPPA*u+cd,-cd],[-cd,cd]])
    a=np.zeros((6,6)); a[:2,2:4]=np.eye(2); a[2:4,:2]=-MINV@stiff
    a[2:4,2:4]=-MINV@damp
    a[2:4,4:6]=np.outer(MINV[:,0],CF)*(KAPPA*u)*(IU*u/FILTER_NORM)
    a[4:6,4:6]=AF
    return a

def stationary(nu,zd,u):
    a=matrix(nu,zd,u); return solve_continuous_lyapunov(a,-BB)

def discrete(a,dt):
    z=np.zeros((12,12)); z[:6,:6]=-a; z[:6,6:]=BB; z[6:,6:]=a.T
    e=expm(z*dt); phi=e[6:,6:].T; q=phi@e[:6,6:]; q=(q+q.T)*.5
    eig, v=np.linalg.eigh(q)
    if eig.min() < -1e-12*max(eig.max(),1.): raise ValueError('negative covariance eigenvalue')
    root=[邮箱](np.sqrt(np.maximum(eig,0.)))
    return phi,root

def bootstrap(q,s,seed=8,reps=500):
    rng=np.random.default_rng(seed); count=q.shape[1]; bq=np.empty((reps,len(q))); bs=np.empty_like(bq)
    for j in range(reps):
        ix=rng.integers(count,size=count)
        bq[j]=q[:,ix].var(axis=1,ddof=1); bs[j]=s[:,ix].var(axis=1,ddof=1)
    return [np.quantile(bq,[.025,.975],axis=0),np.quantile(bs,[.025,.975],axis=0),np.quantile(bq.max(axis=1),[.025,.975])]

def mc(nu,zd,n=N,dt=DT,seed=SEED,save=False,constant=False):
    steps=round(600/dt); stride=round(1/dt)
    assert abs(steps*dt-600)<1e-8 and abs(stride*dt-1)<1e-8
    rng=np.random.default_rng(seed); p0=stationary(nu,zd,30 if constant else wind(0))
    eig,v=np.linalg.eigh((p0+p0.T)*.5)
    x=([邮箱](np.sqrt(np.maximum(eig,0))))@rng.standard_normal((6,n))
    qs=np.empty((601,n),dtype=np.float32) if save else None
    ss=np.empty_like(qs) if save else None
    if save: qs[0]=x[0]; ss[0]=x[0]-x[1]
    peak=0.; peak_t=0.; subset_peak=0.; const_acc=0.; const_count=0
    # Midpoint piecewise-constant A; at each step independent exact Van Loan process noise.
    for k in range(steps):
        t=(k+.5)*dt; a=matrix(nu,zd,30 if constant else wind(t))
        phi,root=discrete(a,dt)
        x=phi@[邮箱]((6,n))
        if (k+1)%stride==0:
            idx=(k+1)//stride; vq=x[0].var(ddof=1)
            if save: qs[idx]=x[0]; ss[idx]=x[0]-x[1]
            if vq>peak: peak=float(vq); peak_t=float(idx)
            if n==3*N: subset_peak=max(subset_peak,float(x[0,:N].var(ddof=1)))
            if constant and idx>=400: const_acc+=vq; const_count+=1
    result=dict(nu=float(nu),zeta_d=float(zd),n=n,dt=dt,peak_var=peak,peak_time_s=peak_t)
    if n==3*N: result['subset_N_peak']=subset_peak
    if constant: result.update(steady_mc=const_acc/const_count,steady_lyapunov=float(stationary(nu,zd,30)[0,0]))
    if save:
        q=qs.astype(np.float64); s=ss.astype(np.float64)
        result.update(q_var=q.var(axis=1,ddof=1).tolist(),stroke_var=s.var(axis=1,ddof=1).tolist())
        ciq,cis,cip=bootstrap(q,s,seed+999)
        result.update(q_ci=ciq.tolist(),stroke_ci=cis.tolist(),peak_ci=cip.tolist())
    return result

def paired_dt(nu,zd,n=N,seed=SEED):
    """Exact marginals under each step size, coupled through shared Gaussian increments."""
    rng=np.random.default_rng(seed); p0=stationary(nu,zd,wind(0))
    eig,v=np.linalg.eigh((p0+p0.T)*.5)
    initial=([邮箱](np.sqrt(np.maximum(eig,0))))@rng.standard_normal((6,n))
    xc=initial.copy(); xf=initial.copy(); pc=pf=0.; tc=tf=0
    for k in range(round(600/DT)):
        t=k*DT; ac=matrix(nu,zd,wind(t+DT/2))
        ph,rc=discrete(ac,DT/2)
        a1=matrix(nu,zd,wind(t+DT/4)); a2=matrix(nu,zd,wind(t+3*DT/4))
        p1,r1=discrete(a1,DT/2); p2,r2=discrete(a2,DT/2)
        z1=rng.standard_normal((6,n));z2=rng.standard_normal((6,n))
        xc=ph@(ph@xc+rc@z1)+rc@z2
        xf=p2@(p1@xf+r1@z1)+r2@z2
        if (k+1)%round(1/DT)==0:
            vc=xc[0].var(ddof=1);vf=xf[0].var(ddof=1)
            if vc>pc:pc=float(vc);tc=(k+1)*DT
            if vf>pf:pf=float(vf);tf=(k+1)*DT
    return dict(coarse_peak=pc,fine_peak=pf,coarse_time=tc,fine_time=tf,relative=abs(pf/pc-1))

def grid_task(item):
    nu,zd=item; return mc(nu,zd)

def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')

def log(*args): print(time.strftime('%m-%d %H:%M'),*args,flush=True)

def main():
    start=time.time(); log('starting N',N,'dt',DT,'filter normalization',FILTER_NORM)
    # Template Nelder-Mead steady RMS optimization, with exactly same filter shape normalized to unit variance.
    # Scaling filter C globally does not affect optimum, so this is numerically equivalent to the template code.
    def obj(z): return np.sqrt(stationary(*np.exp(z),30)[0,0])
    best=min((minimize(obj,np.log([nu,zd]),method='Nelder-Mead',options=dict(xatol=1e-6,fatol=1e-12,maxiter=4000))
              for nu in (.8,1.,1.2) for zd in (.05,.15)),key=lambda a:a.fun)
    stationary_opt=np.exp(best.x).tolist(); base=(.9783,.0705)
    log('steady optimum',stationary_opt,'RMS',best.fun)
    # Gate 1: independent N=20000 constant U check, snapshot final sample vs stationary truth.
    steady=mc(*base,constant=True,save=True)
    lyap=steady['steady_lyapunov']; vals=np.array(steady['q_var'][400:]);
    # CI for final snapshot, not 201 serially dependent snapshots.
    vfinal=steady['q_var'][-1]; ci_final=[steady['q_ci'][i][-1] for i in (0,1)]
    gate1=ci_final[0]<=lyap<=ci_final[1]
    log('gate1 final',vfinal,ci_final,'lyap',lyap,'pass',gate1)
    del steady['q_var'],steady['stroke_var'],steady['q_ci'],steady['stroke_ci']
    dump('gate_progress.json',dict(steady=steady,steady_final_variance=vfinal,steady_final_ci=ci_final,gate1=gate1))
    if not gate1: raise RuntimeError('gate1 failed: Lyapunov outside MC final-snapshot bootstrap 95% CI')
    baseline=mc(*base,n=N,dt=DT,save=True)
    triple=mc(*base,n=3*N,dt=DT)
    delta_n=abs(triple['peak_var']/triple['subset_N_peak']-1.)
    log('gate2 N triple paired',triple['subset_N_peak'],triple['peak_var'],delta_n)
    dump('gate_progress.json',dict(steady=steady,baseline_peak=baseline['peak_var'],triple=triple,gate2_rel=delta_n,gate2=delta_n<.02))
    if delta_n>=.02: raise RuntimeError('gate2 failed N triple')
    half=paired_dt(*base,n=N)
    delta_dt=half['relative']
    log('gate3 dt half paired',half['coarse_peak'],half['fine_peak'],delta_dt)
    dump('gate_progress.json',dict(steady=steady,baseline_peak=baseline['peak_var'],triple=triple,half=half,gate2_rel=delta_n,gate3_rel=delta_dt,gate3=delta_dt<.01))
    if delta_dt>=.01: raise RuntimeError('gate3 failed dt half')
    steadyrun=mc(*stationary_opt,n=N,save=True)
    # Coarse then locally refined MC grid, each run identical RNG seed and initial normal draws.
    coarse=[(float(a),float(b)) for a in np.linspace(.90,1.06,7) for b in np.linspace(.035,.115,5)]
    completed={}
    def run_batch(items):
        todo=[it for it in items if it not in completed]
        with ProcessPoolExecutor(max_workers=14) as ex:
            futures={ex.submit(grid_task,it):it for it in todo}
            for future in as_completed(futures):
                it=futures[future]; result=future.result(); completed[it]=result
                with (OUT/'grid.jsonl').open('a') as fh: fh.write(json.dumps(result)+'\n')
                log('grid',len(completed),'/',len(coarse),'point',it,'peak',result['peak_var'])
    run_batch(coarse)
    p=min(completed,key=lambda it:completed[it]['peak_var']); log('coarse best',p)
    refine=[(round(float(a),7),round(float(b),7)) for a in np.linspace(p[0]-.025,p[0]+.025,7) for b in np.linspace(max(.015,p[1]-.025),p[1]+.025,7)]
    run_batch(refine)
    optimum=min(completed.values(),key=lambda r:r['peak_var'])
    optimal_curve=mc(optimum['nu'],optimum['zeta_d'],save=True)
    flat=[r for r in completed.values() if r['peak_var']<=1.02*optimum['peak_var']]
    truth=dict(source='L22.6 T01 template 01_推导.md §8; check_result.json filter_params_log; target problem',
               method='independent Gaussian trajectories; midpoint piecewise-constant A; exact Van Loan; per-snapshot sample variance ddof=1; paired common RNG seed',
               filter_params_log=PF.tolist(),filter_unit_normalizer=FILTER_NORM,dt=DT,n=N,seed=SEED,
               params=dict(M=M,f_s=FS,zeta_s=ZS,kappa=KAPPA,I_v=IU,L=340.2,mu=MU,beta=BETA,phi_b=PHI),
               stationary_opt=dict(nu=stationary_opt[0],zeta_d=stationary_opt[1],rms_lyapunov=float(best.fun)),
               checks=dict(steady=steady,steady_final_variance=vfinal,steady_final_ci=ci_final,gate1=gate1,
                           n_triple_peak=triple['peak_var'],n_triple_relative=delta_n,gate2=delta_n<.02,
                           dt_half_peak=half['fine_peak'],dt_half_coarse_peak=half['coarse_peak'],dt_half_relative=delta_dt,gate3=delta_dt<.01),
               cases=dict(template=baseline,steady_U30=steadyrun,event_opt=optimal_curve),
               optimization=dict(coarse_count=len(coarse),refine_count=len(refine),unique_count=len(completed),
                                 optimum=optimum,peak_ci=optimal_curve['peak_ci'],
                                 flat_2pct=dict(nu=[min(r['nu'] for r in flat),max(r['nu'] for r in flat)],
                                                zeta_d=[min(r['zeta_d'] for r in flat),max(r['zeta_d'] for r in flat)],count=len(flat))),
               wall_seconds=time.time()-start)
    dump('truth.json',truth)
    with (OUT/'curves.csv').open('w',newline='') as fh:
        w=csv.writer(fh); w.writerow(['source','t_s','case','q_var_m2','q_lo95_m2','q_hi95_m2','stroke_var_m2','stroke_lo95_m2','stroke_hi95_m2'])
        for key in ('template','steady_U30','event_opt'):
            r=truth['cases'][key]
            for i in range(601): w.writerow(['L22.6 T01 template+CRC Monte Carlo',i,key,r['q_var'][i],r['q_ci'][0][i],r['q_ci'][1][i],r['stroke_var'][i],r['stroke_ci'][0][i],r['stroke_ci'][1][i]])
    log('DONE',truth['optimization']['optimum'],'wall',truth['wall_seconds'])

if __name__=='__main__': main()
