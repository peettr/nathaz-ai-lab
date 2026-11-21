"""L22.6 T01 C1/C2 independent Monte Carlo extension; CRC only."""
import csv, json, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from scipy.linalg import solve_continuous_lyapunov
import truth_core as core

OUT=Path(__file__).resolve().parent
BASE=(.9783,.0705)
core.N=20000  # paired N->3N convergence gate: 20000 -> 60000, per frozen allowance

def log(*s): print(time.strftime('%m-%d %H:%M:%S'),*s,flush=True)
def wind(t,tau): return 10+20*np.exp(-((t-300)/tau)**2)
def set_tau(tau): core.wind=lambda t: wind(t,tau)
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def compact(r): return {k:v for k,v in r.items() if k not in ('q_var','stroke_var','q_ci','stroke_ci')}
def quasi(tau):
    return [float(solve_continuous_lyapunov(core.matrix(*BASE,wind(t,tau)),-core.BB)[0,0]) for t in range(601)]
def grid_task(item): return core.mc(*item,n=20000)

def main():
    start=time.time(); log('start C1/C2','dt',core.DT,'seed',core.SEED,'paired gate 20000:60000')
    set_tau(10)
    # Gate 1: constant U=30, final snapshot Lyapunov within whole-trajectory bootstrap CI.
    steady=core.mc(*BASE,n=60000,constant=True,save=True)
    lyap=steady['steady_lyapunov']; ci=[steady['q_ci'][i][-1] for i in (0,1)]
    gates={'constant_U30':{'mc_final':steady['q_var'][-1],'lyapunov':lyap,'ci95':ci,'pass':ci[0]<=lyap<=ci[1]}}
    dump('gate_progress_C2.json',gates);log('gate1',gates['constant_U30'])
    if not gates['constant_U30']['pass']: raise RuntimeError('gate1 constant U Lyapunov outside bootstrap CI')
    del steady
    triple=core.mc(*BASE,n=60000)
    rel=abs(triple['peak_var']/triple['subset_N_peak']-1)
    gates['N_20000_to_60000']={'subset_peak':triple['subset_N_peak'],'full_peak':triple['peak_var'],'relative':rel,'pass':rel<.02}
    dump('gate_progress_C2.json',gates);log('gate2',gates['N_20000_to_60000'])
    if not gates['N_20000_to_60000']['pass']: raise RuntimeError('gate2 N convergence failed')
    half=core.paired_dt(*BASE,n=20000)
    gates['dt_002_to_001']={**half,'pass':half['relative']<.01}
    dump('gate_progress_C2.json',gates);log('gate3',gates['dt_002_to_001'])
    if not gates['dt_002_to_001']['pass']: raise RuntimeError('gate3 dt convergence failed')
    set_tau(60); c1=core.mc(*BASE,n=60000,save=True);dump('checkpoint_C1.json',c1);log('C1',c1['peak_var'],c1['peak_time_s'])
    set_tau(10);c2=core.mc(*BASE,n=60000,save=True);dump('checkpoint_C2.json',c2);log('C2',c2['peak_var'],c2['peak_time_s'])
    coarse=[(float(a),float(b)) for a in np.linspace(.90,1.06,7) for b in np.linspace(.035,.115,5)]
    results={}
    def batch(items):
        todo=[i for i in items if i not in results]
        with ProcessPoolExecutor(max_workers=14) as pool:
            futures={pool.submit(grid_task,i):i for i in todo}
            for fut in as_completed(futures):
                i=futures[fut];results[i]=fut.result()
                with (OUT/'grid_C2.jsonl').open('a') as fh:fh.write(json.dumps(results[i])+'\n')
                log('grid',len(results),i,results[i]['peak_var'])
    batch(coarse)
    p=min(results,key=lambda i:results[i]['peak_var']);log('coarse best',p)
    refine=[(round(float(a),7),round(float(b),7)) for a in np.linspace(p[0]-.025,p[0]+.025,7) for b in np.linspace(max(.015,p[1]-.025),p[1]+.025,7)]
    batch(refine)
    opt=min(results.values(),key=lambda r:r['peak_var'])
    opt_curve=core.mc(opt['nu'],opt['zeta_d'],n=60000,save=True)
    flat=[r for r in results.values() if r['peak_var']<=1.02*opt['peak_var']]
    q1=quasi(60);q2=quasi(10)
    truth={'source':'L22.6 T01 template §8; TASK_SPEC_T01_v1.md; CRC independent Monte Carlo',
           'method':'midpoint piecewise constant A; Van Loan; common seed; one-second grid; whole trajectory bootstrap; 20k grid then 60k confirmation',
           'dt':core.DT,'seed':core.SEED,'n_final':60000,'n_grid':20000,'checks_C2':gates,
           'cases':{'C1_template':c1,'C2_template':c2,'C2_event_opt':opt_curve},
           'optimization_C2':{'grid_optimum_20000':opt,'confirmed_60000':compact(opt_curve),'confirmed_peak_ci95':opt_curve['peak_ci'],
              'coarse_count':len(coarse),'refine_count':len(refine),'unique_count':len(results),
              'flat_2pct_grid_20000':{'nu':[min(r['nu'] for r in flat),max(r['nu'] for r in flat)],'zeta_d':[min(r['zeta_d'] for r in flat),max(r['zeta_d'] for r in flat)],'count':len(flat)}},
           'quasistatic_Q':{'C1':q1,'C2':q2},'wall_seconds':time.time()-start}
    dump('truth_C2.json',truth)
    with (OUT/'curves_C2.csv').open('w',newline='') as fh:
        w=csv.writer(fh);w.writerow(['source','case','t_s','q_var_m2','q_lo95_m2','q_hi95_m2','stroke_var_m2','stroke_lo95_m2','stroke_hi95_m2','Q_q_var_m2'])
        for case,r,q in [('C1_template',c1,q1),('C2_template',c2,q2),('C2_event_opt',opt_curve,[])]:
            for t in range(601):w.writerow(['L22.6 T01 template+CRC MC',case,t,r['q_var'][t],r['q_ci'][0][t],r['q_ci'][1][t],r['stroke_var'][t],r['stroke_ci'][0][t],r['stroke_ci'][1][t],q[t] if q else ''])
    with (OUT/'Q_curves.csv').open('w',newline='') as fh:
        w=csv.writer(fh);w.writerow(['source','t_s','Q_C1_q_var_m2','Q_C2_q_var_m2'])
        for t in range(601):w.writerow(['T01 template; stationary Lyapunov shortcut',t,q1[t],q2[t]])
    log('DONE',opt['nu'],opt['zeta_d'],opt_curve['peak_var'],truth['wall_seconds'])

if __name__=='__main__':main()
