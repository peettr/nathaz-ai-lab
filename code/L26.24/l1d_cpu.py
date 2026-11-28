"""L1d full held-out CG, five repeats and B2 same-kernel IC positive control."""
import csv,json,os,re,sys,time,traceback
from pathlib import Path
from statistics import median
import numpy as np
from scipy.sparse import load_npz,tril
sys.path.insert(0,str(Path(__file__).resolve().parent))
import l1b_cpu as prior
ROOT=Path('/groups/kareem/[用户]/L26_24_LINSYS_20261115_L1/L1d')
OUT=ROOT/'cpu/out'
def run(dry=False):
    if dry:
        from scipy.sparse import csr_matrix
        A=csr_matrix([[4.,-1.],[-1.,4.]])
        L=tril(A).tocsr();v=np.empty_like(L.data)
        assert prior.lib.ic0_factor(2,L.indptr,L.indices,np.ascontiguousarray(L.data),v)==0
        L.data=v;n,r,st=prior.solve(A,np.ones(2),np.zeros(2),2,.1,L)
        assert st=='converged';print('L1D_CPU_DRY_PASS',n,r);return
    assert all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    gate=json.loads((ROOT/'gate/out/gate.json').read_text());assert gate['pass']
    report=json.loads((ROOT/'infer/out/manifest.json').read_text());assert report['status']=='complete' and len(report['factors'])==20
    entries={e['system']:e for e in report['factors']};assert len(entries)==20
    dirs=sorted(prior.SOURCE.glob('PresCorr-*'),key=lambda d:tuple(map(int,re.findall(r'\d+',d.name))))
    assert len(dirs)==20 and set(entries)=={d.name for d in dirs}
    OUT.mkdir(parents=True,exist_ok=False)
    fields=['system','segment','target','rep','scale','initial_residual','target_residual','inference_seconds','cg_seconds','total_seconds','iterations','achieved_residual','status','factor_nnz','cpu_model','threads']
    allrows=[];ic=[]
    with (OUT/'l1_timing.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for d in dirs:
            A,b,x0,meta,norm,initial=prior.load_system(d)
            entry=entries[d.name];s=float(entry['scale'])
            facroot=(ROOT/'gpu/out') if d.name==gate['system'] else (ROOT/'infer/out')
            L=load_npz(facroot/entry['factor_file']).tocsr().astype(np.float64)
            assert np.isfinite(L.data).all() and (L.diagonal()>0).all() and A.shape==L.shape
            L.data/=np.sqrt(s) # IC kernel applies inverse of Lorig Lorig.T = LL.T/s.
            for target in ('Ta','Tb'):
                tol=(max(1e-6,.05*initial) if not meta['is_final'] else 1e-6) if target=='Ta' else 1e-8
                for rep in range(5):
                    start=time.perf_counter();it,r,status=prior.solve(A,b,x0,norm,tol,L);elapsed=time.perf_counter()-start
                    infer=entry['inference_seconds_reps'][rep]
                    row=dict(system=d.name,segment='later',target=target,rep=rep,scale=s,initial_residual=initial,target_residual=tol,inference_seconds=infer,cg_seconds=elapsed,total_seconds=infer+elapsed,iterations=it,achieved_residual=r,status=status,factor_nnz=L.nnz,cpu_model=next((v.split(':',1)[1].strip() for v in Path('/proc/cpuinfo').read_text().splitlines() if v.startswith('model name')),'unknown'),threads=1)
                    writer.writerow(row);f.flush();allrows.append(row)
                    print('L1D',d.name,target,rep,it,status,elapsed,flush=True)
                    if status not in ('converged','initial_meets_target'):
                        # Preserve partial CSV and diagnostic instead of spending the whole allocation on failed CG.
                        with (OUT/'stop.json').open('x') as o:json.dump({'system':d.name,'target':target,'rep':rep,'iterations':it,'residual':r,'reason':'not converged'},o,indent=2)
                        return
                Li=tril(A,format='csr');Li.sort_indices();v=np.empty_like(Li.data)
                rc=prior.lib.ic0_factor(A.shape[0],Li.indptr,Li.indices,np.ascontiguousarray(Li.data),v)
                assert rc==0,(d.name,rc)
                Li.data=v;it,r,st=prior.solve(A,b,x0,norm,tol,Li)
                baseline=json.loads((prior.B2/f'later_{d.name}_{target}.json').read_text())
                b2it=[int(x['iterations']) for x in baseline['results']]
                ic.append({'system':d.name,'target':target,'ic_iterations':it,'b2_iterations':b2it,'identical':all(it==x for x in b2it),'residual':r,'status':st})
    with (OUT/'l1_ic_crosscheck.json').open('x') as f:json.dump({'rows':ic,'all_identical':all(x['identical'] for x in ic)},f,indent=2)
    assert len(allrows)==200 and len(ic)==40
    summary={'source':'D1b later 20 immutable systems','targets':{},'count':len(allrows),'ic_same_code_all_identical':all(x['identical'] for x in ic),'scale_definition':'1/mean(diag(-A)); factor application s L^-T L^-1','gate':gate}
    for target in ('Ta','Tb'):
        groups=[[float(r['total_seconds']) for r in allrows if r['system']==d.name and r['target']==target] for d in dirs]
        assert all(len(g)==5 for g in groups)
        values=np.array([median(g) for g in groups]);med=float(np.median(values))
        q25,q75=map(float,np.quantile(values,[.25,.75]))
        rows=[r for r in allrows if r['target']==target]
        summary['targets'][target]={'systems':20,'median_seconds':med,'q25_seconds':q25,'q75_seconds':q75,'iqr_seconds':q75-q25,'converged':sum(r['status'] in ('converged','initial_meets_target') for r in rows),'threshold_seconds':.0241 if target=='Ta' else .222}
    summary['Ta_vs_B1_threshold_seconds']=5.44
    summary['Ta_le_B1_threshold']=summary['targets']['Ta']['median_seconds']<=5.44
    summary['Ta_le_B0_threshold']=summary['targets']['Ta']['median_seconds']<=.0241
    summary['Tb_ge_abandon_threshold']=summary['targets']['Tb']['median_seconds']>=.222
    with (OUT/'l1_summary.json').open('x') as f:json.dump(summary,f,indent=2,allow_nan=False)
    print('L1D_COMPLETE',json.dumps(summary['targets']),flush=True)
if __name__=='__main__':
    try:run('--dry-run' in sys.argv)
    except BaseException:
        OUT.mkdir(parents=True,exist_ok=True);(OUT/'error.txt').write_text(traceback.format_exc());raise
