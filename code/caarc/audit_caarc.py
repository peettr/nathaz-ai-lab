import csv, json, re, sys, math
from pathlib import Path
import numpy as np
from scipy.io._mmio import mmread
from scipy.sparse.linalg import norm

MARK=re.compile(r'LINSYS_BEGIN (\d+) (\d+) (\S+)')
SOLVE=re.compile(r'(\S+):\s+Solving for p,\s+Initial residual = (\S+),\s+Final residual = (\S+),\s+No Iterations (\d+)')
TIME=re.compile(r'Time = (\S+)')
CLOCK=re.compile(r'ExecutionTime = (\S+) s\s+ClockTime = (\S+) s')
GATE=.01
N=2591745

def readlog(path, markers):
    ts=[]; rs=[]; clk=[]; pending=None; ended=False
    for raw in path.read_text().splitlines():
        line=raw.strip()
        if m:=TIME.fullmatch(line): ts.append(m[1])
        if m:=CLOCK.match(line): clk.append((ts[-1],float(m[2])))
        if m:=MARK.fullmatch(line):
            assert pending is None and markers
            pending=m.groups()
        if m:=SOLVE.fullmatch(line):
            assert bool(pending)==markers
            rs.append((ts[-1],pending,m.groups(),line)); pending=None
        if line=='End': ended=True
    assert ended and pending is None and list(map(float,ts))==list(range(3001,3021)), (path,ts)
    assert len(clk)==len(rs)==20 and [r[0] for r in rs]==ts and [x[0] for x in clk]==ts
    return rs,clk

def rel(a,b):
    return abs(a-b)/abs(b) if b else (0 if not a else math.inf)

def save(out, rows):
    with out.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def audit(root):
    ds,dc=readlog(root/'log.dump',True); cs,cc=readlog(root/'log.control',False)
    systems=['PresCorr-'+'-'.join(r[1][:2]) for r in ds]
    assert len(set(systems))==20 and set(systems)=={p.name for p in (root/'dump/Solving').iterdir()}
    out=[]; timing=[]; prev_d=prev_c=0
    for i, ((t,(step,cor,key),(solver,r0,rf,it),receipt),sysname) in enumerate(zip(ds,systems)):
        d=root/'dump/Solving'/sysname
        m=json.loads((d/'meta.json').read_text()); nbytes=sum(p.stat().st_size for p in d.iterdir())
        r0,rf,it=float(r0),float(rf),int(it)
        assert m['is_final'] is None and m['step']==m['simple_iteration']==int(step) and m['correction']==int(cor)==1
        assert float(m['time'])==float(t) and m['solver_entry']==key=='p' and solver=='GAMG' and m['iterations']==it
        paired_equal=(r0,rf,it)==(float(cs[i][2][1]),float(cs[i][2][2]),int(cs[i][2][3]))
        assert rel(m['initial_residual'],r0)<=1e-5 and rel(m['final_residual'],rf)<=1e-5
        a=mmread(d/'A.mtx.gz').tocsr(); a.sum_duplicates()
        b,x0,xf=(np.load(d/(k+'.npy'),allow_pickle=False) for k in ('b','x_initial','x_openfoam'))
        assert a.shape==(N,N) and b.shape==x0.shape==xf.shape==(N,) and all(np.isfinite(x).all() for x in (a.data,b,x0,xf))
        ax=a@x0; ref=[邮箱](x0,x0.mean()); nf=float(np.abs(ax-ref).sum()+np.abs(b-ref).sum()+1e-20)
        ri=float(np.abs(b-ax).sum()/nf); fin=float(np.abs(b-a@xf).sum()/nf)
        ei,ef=rel(ri,r0),rel(fin,rf)
        out.append(dict(system=sysname,time=t,timeIndex=step,correction=cor,solver_entry=key,initial_log=r0,final_log=rf,initial_meta=m['initial_residual'],final_meta=m['final_residual'],initial_recomputed=ri,final_recomputed=fin,initial_relative_error=ei,final_relative_error=ef,iterations=it,openfoam_receipt=receipt,normFactor=nf,nnz=a.nnz,bytes=nbytes,symmetric=m['symmetric'],symmetry_ratio=float(norm(a-a.T)/norm(a)),negative_A_diag_all_positive=bool(np.all(a.diagonal()<0)),q1_pass=ei<=GATE and ef<=GATE))
        td,tc=dc[i][1]-prev_d,cc[i][1]-prev_c; prev_d,prev_c=dc[i][1],cc[i][1]
        assert min(td,tc)>0
        timing.append(dict(time=t,dump_s=td,control_s=tc,delta_s=td-tc,increment_ratio=(td-tc)/tc,total_ratio=td/tc,includes_startup=(i==0),paired_pressure_receipt_equal=paired_equal))
        del a,b,x0,xf,ax,ref
    save(root/'q1_caarc.csv',out); save(root/'overhead_caarc.csv',timing)
    summary=dict(passed=sum(r['q1_pass'] for r in out),total=len(out),first_system=out[0]['system'],first_system_bytes=out[0]['bytes'],all_system_bytes=sum(r['bytes'] for r in out),max_initial_relative_error=max(r['initial_relative_error'] for r in out),max_final_relative_error=max(r['final_relative_error'] for r in out),max_symmetry_ratio=max(r['symmetry_ratio'] for r in out),all_negative_A_diag_positive=all(r['negative_A_diag_all_positive'] for r in out),measurement='OpenFOAM cumulative ClockTime differences (seconds), first step includes startup',delta_s=prev_d-prev_c,increment_ratio=(prev_d-prev_c)/prev_c,total_ratio=prev_d/prev_c)
    (root/'summary_caarc.json').write_text(json.dumps(summary,indent=2)+'\n'); print(summary,flush=True)
    return 0 if summary['passed']==20 else 2

if __name__=='__main__': sys.exit(audit(Path(sys.argv[1])))
