"""C2 event-peak optimization extension, CRC only; frozen seed and core."""
import json, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import truth_core as core

OUT=Path(__file__).resolve().parent
core.wind=lambda t:10+20*np.exp(-((t-300)/10)**2)
core.N=20000

def evaluate(p):
    return core.mc(*p,n=20000)

def main():
    start=time.time()
    nus=[round(.95+.01*i,8) for i in range(12)]
    zs=[round(.002+.002*i,8) for i in range(15)]
    original={(a,b) for a in nus for b in zs}
    results={}
    def batch(points):
        with ProcessPoolExecutor(max_workers=14) as pool:
            future={pool.submit(evaluate,p):p for p in sorted(points-set(results))}
            for f in as_completed(future):
                p=future[f]; r=f.result(); results[p]=r
                with (OUT/'grid_opt_ext.jsonl').open('a') as fh: fh.write(json.dumps(r)+'\n')
                print('grid',len(results),p,r['peak_var'],flush=True)
    batch(original)
    best=min(results,key=lambda p:results[p]['peak_var'])
    initial_best=best
    edges=[label for flag,label in ((best[0]==nus[0],'nu_lower'),(best[0]==nus[-1],'nu_upper'),(best[1]==zs[0],'zeta_lower'),(best[1]==zs[-1],'zeta_upper')) if flag]
    added=set()
    if edges:
        # One outward extension only, keeping damping strictly positive.
        if 'nu_lower' in edges: added.update((a,b) for a in [.92,.93,.94] for b in zs)
        if 'nu_upper' in edges: added.update((a,b) for a in [1.07,1.08,1.09] for b in zs)
        if 'zeta_lower' in edges: added.update((a,b) for a in nus for b in [.0005,.001,.0015])
        if 'zeta_upper' in edges: added.update((a,b) for a in nus for b in [.032,.034,.036])
        batch(added)
    best=min(results,key=lambda p:results[p]['peak_var'])
    print('N20000 optimum',best,results[best]['peak_var'],'extension',edges,flush=True)
    confirmed=core.mc(*best,n=60000,save=True)
    compact={k:v for k,v in confirmed.items() if k not in ('q_var','stroke_var','q_ci','stroke_ci')}
    all_nus=sorted({p[0] for p in results}); all_zs=sorted({p[1] for p in results})
    final_edges=[label for flag,label in ((best[0]==all_nus[0],'nu_lower'),(best[0]==all_nus[-1],'nu_upper'),(best[1]==all_zs[0],'zeta_lower'),(best[1]==all_zs[-1],'zeta_upper')) if flag]
    flat=[r for r in results.values() if r['peak_var']<=results[best]['peak_var']*1.02]
    obj={'source':'T01 template; C2 tau=10 s; CRC Monte Carlo common seed', 'dt':core.DT,'seed':core.SEED,
         'grid_n':20000,'confirm_n':60000,'initial_bounds':{'nu':[nus[0],nus[-1]],'zeta_d':[zs[0],zs[-1]]},
         'grid_count_initial':len(original),'initial_best':results[initial_best], 'initial_boundary':edges,
         'extension_count':len(added-original),'total_evaluated':len(results), 'final_grid_best':results[best],
         'final_boundary':final_edges,'confirmed_60000':compact,
         'flat_2pct_grid':{'count':len(flat),'nu':[min(r['nu'] for r in flat),max(r['nu'] for r in flat)],
                            'zeta_d':[min(r['zeta_d'] for r in flat),max(r['zeta_d'] for r in flat)]},
         'wall_seconds':time.time()-start,
         'grid':sorted(results.values(),key=lambda r:(r['nu'],r['zeta_d']))}
    (OUT/'opt_ext.json').write_text(json.dumps(obj,indent=2)+'\n')
    print('DONE',best,compact['peak_var'],compact['peak_ci'],'boundary',final_edges,flush=True)

if __name__=='__main__':main()
