#!/usr/bin/env python3
import csv, hashlib, json, math, os, re, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np
from scipy.io._mmio import mmread
from scipy.sparse.linalg import norm

PROVENANCE = 'L29.6c1 S0，CFD 线搭建；S0 未定版，网格收敛约 11-25 判定'
COORDS = {'x':'inflow +x', 'y':'vertical, heave along y', 'z':'spanwise (frontAndBack empty, 2D)', 'U_m_s':10.0, 'B_m':3.1, 'span_m':0.1, 'Ur':8, 'time_axis':'native OpenFOAM time directories; not stitched'}
PARENT_LIMIT = 5_000_000_000
NUM=r'[+\-0-9.eE]+'
TIME=re.compile(r'^Time = ('+NUM+r')s?$')
EXEC=re.compile(r'^ExecutionTime\s*=')
PRESS=re.compile(r'^(\S+):\s+Solving for p,\s+Initial residual = (\S+),\s+Final residual = (\S+),\s+No Iterations (\d+)\s*$')
MARK=re.compile(r'^LINSYS_BEGIN (\d+) (\d+) (p(?:Final)?)$')

def require(ok,msg):
    if not ok: raise RuntimeError(msg)

def out_json(path, obj):
    with path.open('x') as f: json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False)

def out_csv(path, rows):
    require(rows,'empty table')
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def static(c):
    text=(c/'system/controlDict').read_text(); fv=(c/'system/fvSolution').read_text()
    for key,val in {'application':'pimpleFoam','maxCo':'1','adjustTimeStep':'yes'}.items():
        require(re.search(r'\b'+key+r'\s+'+val+r'\s*;',text),key)
    for key,val in {'nOuterCorrectors':2,'nCorrectors':2,'nNonOrthogonalCorrectors':1}.items():
        require(re.search(r'\b'+key+r'\s+'+str(val)+r'\s*;',fv),key)
    cfg=json.loads((c/'case.json').read_text());require(cfg['settings']=='01n_B' and cfg['dof']=='heave','heave/B')
    return cfg

def space(root,reserve=0):
    size=int(subprocess.check_output(['du','-sb',str(root.parent)],text=True).split()[0]); free=shutil.disk_usage(root).free
    print('space parent_bytes',size,'reserve',reserve,'free',free,flush=True)
    require(size+reserve<=PARENT_LIMIT and free>=reserve,'5 GB/shared free storage gate')
    return size

def conf(case, **values):
    p=case/'system/controlDict'; txt=p.read_text()
    parts=re.split(r'(?m)^(?=\s*functions\s*\{)',txt,maxsplit=1)
    txt=parts[0]
    for k,v in values.items():
        txt,n=re.subn(r'\b'+k+r'\s+[^;]+;',f'{k} {v};',txt)
        require(n==1,('control entry',k,n))
    p.write_text(''.join([txt,*parts[1:]]))

def boundary(path):
    s=re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(),flags=re.S)
    s=s.split('}',1)[1]; header=re.match(r'\s*(\d+)\s*\(',s)
    require(header is not None,'boundary header')
    patches={}
    for name,body in re.findall(r'([^\s{}()]+)\s*\{([^{}]*)\}',s):
        match=re.search(r'\btype\s+([^;\s]+)\s*;',body)
        require(match is not None and name not in patches,('bad patch',name))
        patches[name]=match[1]
    require(len(patches)==int(header[1]) and bool(patches),'boundary count mismatch')
    return patches

def mesh_count(path):
    with path.open() as f:
        for line in f:
            if re.fullmatch(r'\s*\d+\s*',line):return int(line)
    raise ValueError(path)

def points(path):
    s=re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(),flags=re.S).split('}',1)[1]; m=re.match(r'\s*(\d+)\s*\(',s)
    require(m is not None,('points header',path)); z=np.fromstring(re.sub(r'[()]',' ',s[m.end():].strip().removesuffix(';')),sep=' ').reshape(-1,3)
    require(len(z)==int(m[1]) and np.isfinite(z).all(),('points',path));return z

def sh(case, cmd, log, limit):
    with log.open('x') as f:
        subprocess.run(cmd,cwd=case,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=limit)

def status(root,phase):
    print('PHASE',phase,flush=True)
    (root/f'phase_{phase}').touch(exist_ok=False)

def period_gate(case, root, period, end):
    files=list((case/'postProcessing/forces').glob('*/force.dat'))
    require(len(files)==1,('native forces',files))
    data=np.loadtxt(files[0],ndmin=2); t=data[:,0]; xy=data[:,1:3]
    require(data.shape[1]==10 and np.isfinite(data).all() and np.all(np.diff(t)>0),'forces schema')
    require(t[0]<=end-2*period and t[-1]>=end-1e-8,'insufficient force coverage')
    grid=(np.arange(256)+0.5)*period/256
    force=np.stack([np.stack([np.interp(end-k*period+grid,t,col) for col in xy.T]) for k in (2,1)])
    rms=np.sqrt(np.mean(np.diff(force,axis=0)[0]**2,axis=1)); scale=np.sqrt(np.mean(force[1]**2,axis=1)); ratio=rms/np.maximum(scale,1e-30)
    result=dict(provenance=PROVENANCE,start_s=end,period_s=period,windows_s=[[end-2*period,end-period],[end-period,end]],force_phase_rms_relative=ratio.tolist(),criterion=0.10,passed=bool(np.all(ratio<=.10)))
    out_json(root/'period_gate.json',result)
    require(result['passed'],('cycle agreement not established',result))

def solve(case, binpath, on, limit):
    env=os.environ.copy(); env.update(LINSYS_DUMP=str(int(on)),LINSYS_ROOT=str(case)); times=[]; stamps=[]; ended=False
    # OF Info is flushed at its endl records; capture monotonic wall time at the completed-step lines.
    with (case/'log.solve').open('x') as f:
        start=time.monotonic()
        # timeout is external so a blocked pipe cannot defeat the phase limit.
        with subprocess.Popen(['timeout','--kill-after=10s',str(limit),'stdbuf','-oL',binpath,'-noFunctionObjects'],cwd=case,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1) as p:
            for line in p.stdout:
                stamp=time.monotonic();f.write(line)
                l=line.strip()
                if m:=TIME.fullmatch(l): times.append(m[1])
                if EXEC.match(l): stamps.append(stamp-start)
                if l=='End': ended=True
            rc=p.wait()
        require(rc==0 and ended and len(times)==len(stamps)==3,(case,rc,times,stamps))
    return times,np.diff([0.0,*stamps]).tolist()

def rel(x,y): return abs(x-y)/abs(y) if y else (0.0 if x==0 else math.inf)

def audit(root, dump, times, start_idx):
    pending=None; records={}; group=-1
    for line in (dump/'log.solve').read_text().splitlines():
        s=line.strip()
        if TIME.fullmatch(s): group+=1
        if m:=MARK.fullmatch(s):
            require(pending is None,'overlapping markers');pending=(group,int(m[1]),int(m[2]),m[3])
        if m:=PRESS.fullmatch(s):
            require(pending is not None and pending not in records,'missing/duplicate marker');records[pending]=m.groups();pending=None
    require(pending is None and len(records)==24,'expected 24 solves from three full steps under B')
    keys=sorted(records)
    require([(g,i,j) for g,i,j,_ in keys]==[(g,start_idx+g+1,j) for g in range(3) for j in range(1,9)],'correction indexing')
    matrix_dirs={p.name for p in (dump/'Solving').iterdir()}
    require(matrix_dirs=={f'PresCorr-{i}-{j}' for _,i,j,_ in keys},'export dir set mismatch')
    collection=root/'Solving';collection.mkdir(); rows=[]
    for g,i,j,entry in keys[:20]:
        name=f'PresCorr-{i}-{j}'; d=dump/'Solving'/name; m=json.loads((d/'meta.json').read_text())
        solver,r0,rf,it=records[g,i,j,entry]; r0,rf,it=float(r0),float(rf),int(it)
        require(solver.endswith('PCG'),'unexpected pressure solver '+solver)
        require((int(m['step']),int(m['correction']),m['solver_entry'],m['is_final'],int(m['iterations']))==(i,j,entry,entry=='pFinal',it),'meta/log identity')
        require(math.isclose(float(m['time']),float(times[g]),rel_tol=1e-11,abs_tol=1e-11),'meta/log time')
        require(rel(m['initial_residual'],r0)<=1e-5 and rel(m['final_residual'],rf)<=1e-5,'meta/log rounding')
        a=mmread(d/'A.mtx.gz').tocsr();a.sum_duplicates()
        b,x0,xf=(np.load(d/(f+'.npy'),allow_pickle=False) for f in ('b','x_initial','x_openfoam'))
        require(a.shape==(b.size,b.size) and b.shape==x0.shape==xf.shape==(b.size,) and all(np.isfinite(x).all() for x in (a.data,b,x0,xf)),name)
        ax=a@x0; ref=[邮箱](x0,x0.mean()); nf=float(np.abs(ax-ref).sum()+np.abs(b-ref).sum()+1e-20)
        r0a=float(np.abs(b-ax).sum()/nf); rfa=float(np.abs(b-a@xf).sum()/nf); e0,ef=rel(r0a,r0),rel(rfa,rf)
        sym=float(norm(a-a.T)/norm(a)); passed=max(e0,ef)<=.01
        rows.append(dict(provenance=PROVENANCE,system=name,time=m['time'],step=i,correction=j,solver=solver,solver_entry=entry,is_final=m['is_final'],mesh_moving=m['mesh_moving'],n=b.size,nnz=a.nnz,initial_log=r0,final_log=rf,initial_recomputed=r0a,final_recomputed=rfa,initial_relative_error=e0,final_relative_error=ef,iterations=it,symmetry_ratio=sym,minus_A_diag_all_positive=bool(np.all(a.diagonal()<0)),q1_pass=passed))
        dst=collection/name; dst.mkdir()
        for f in ('A.mtx.gz','b.npy','x_initial.npy','x_openfoam.npy'): os.link(d/f,dst/f)
        m.update(provenance=PROVENANCE, mesh_grade='coarse', coordinate_convention=COORDS);out_json(dst/'meta.json',m)
    out_csv(root/'q1_coarse.csv',rows)
    return rows

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def run(root, binpath):
    phase_start=time.monotonic(); case=root/'advance'; shutil.copytree(root/'frozen/heave',case)
    cfg=static(case); require(all(cfg[k]==COORDS[k] for k in ('B_m','span_m','U_m_s','Ur')),'coordinate reference metadata'); period=1/float(cfg['f_Hz']); end=4*period
    space(root,600_000_000);status(root,'mesh')
    sh(case,['blockMesh'],root/'log.blockMesh',600)
    bpath=case/'constant/polyMesh/boundary'; patches=boundary(bpath)
    allowed={'wall','patch','empty','symmetryPlane','symmetry','wedge','cyclic'}
    out_json(root/'boundary_coarse.json',dict(provenance=PROVENANCE,patches=patches,sha256=sha(bpath),unsupported=sorted(set(patches.values())-allowed)))
    require(set(patches.values())<=allowed,('unsupported patch',patches))
    poly=case/'constant/polyMesh'; owner=mesh_count(poly/'owner'); nbr=mesh_count(poly/'neighbour'); n=200000
    # Reserve conservative textual export upper bound incl. temporary 4 surplus systems plus field checkpoints.
    reserve=24*(64*(n+2*owner)+24*n+65536)+800_000_000
    space(root,reserve); status(root,'advance')
    conf(case,endTime=f'{end:.12g}',purgeWrite=2,writePrecision=16)
    sh(case,['pimpleFoam'],root/'log.advance',3*3600+40*60)
    text=(root/'log.advance').read_text(); ts=[m[1] for l in text.splitlines() if (m:=TIME.fullmatch(l.strip()))]
    require(ts and 'End' in text.splitlines() and math.isclose(float(ts[-1]),end,abs_tol=1e-8),'advance incomplete')
    period_gate(case,root,period,end)
    cp,=(p for p in case.iterdir() if p.is_dir() and re.fullmatch(NUM,p.name) and abs(float(p.name)-end)<1e-8)
    for f in ('U','p','k','omega','nut','uniform/time','polyMesh/points'): require((cp/f).is_file(),('checkpoint missing',f))
    m=re.search(r'\bindex\s+(\d+)\s*;', (cp/'uniform/time').read_text()); require(m is not None,'timeIndex missing'); idx=int(m[1]);
    space(root,reserve)
    branches={}
    for name in ('control','dump'):
        c=root/name; c.mkdir()
        for fld in ('system','constant','0'): shutil.copytree(case/fld,c/fld)
        shutil.copytree(cp,c/cp.name)
        # The next positive multiple of idx+3 occurs exactly three steps beyond the saved time index.
        conf(c,startFrom='latestTime',stopAt='nextWrite',endTime=f'{end+period:.12g}',writeControl='timeStep',writeInterval=idx+3,purgeWrite=0)
        branches[name]=c
    out_json(root/'run_config_coarse.json',dict(provenance=PROVENANCE,checkpoint=cp.name,start_index=idx,checkpoint_hashes={str(p.relative_to(cp)):sha(p) for p in cp.rglob('*') if p.is_file()},control_sha256=sha(branches['control']/'system/controlDict'),dump_sha256=sha(branches['dump']/'system/controlDict'),binary_sha256=sha(Path(binpath))))
    (branches['dump']/'Solving').mkdir();status(root,'pair')
    tc,wc=solve(branches['control'],binpath,False,600); td,wd=solve(branches['dump'],binpath,True,900)
    require(list(map(float,tc))==list(map(float,td)),('unpaired times',tc,td))
    control_counts=sum(bool(PRESS.fullmatch(l.strip())) for l in (branches['control']/'log.solve').read_text().splitlines());require(control_counts==24,('control pressure count',control_counts))
    out_csv(root/'overhead_coarse.csv',[dict(provenance=PROVENANCE,step=i,time=t,control_wall_s=c,dump_wall_s=d,delta_s=d-c,increment_ratio=(d-c)/c,total_ratio=d/c,raw_dump_count=8,delivered_count=8 if i<3 else 4,first_includes_startup=(i==1)) for i,(t,c,d) in enumerate(zip(td,wc,wd),1)])
    final,=(p for p in branches['dump'].glob('*/polyMesh/points') if re.fullmatch(NUM,p.parent.parent.name) and math.isclose(float(p.parent.parent.name),float(td[-1]),abs_tol=1e-10))
    p0=points(cp/'polyMesh/points'); p1=points(final);require(p0.shape==p1.shape,'point indexing'); delta=np.linalg.norm(p1-p0,axis=1)
    movement=dict(start_time=cp.name,end_time=td[-1],points=len(delta),moving_points=int(np.count_nonzero(delta)),max_displacement_m=float(delta.max()),start_points_sha256=sha(cp/'polyMesh/points'),end_points_sha256=sha(final));out_json(root/'movement_coarse.json',movement)
    status(root,'q1');rows=audit(root,branches['dump'],td,idx)
    summary=dict(provenance=PROVENANCE,count=len(rows),pass_count=sum(r['q1_pass'] for r in rows),max_initial_relative_error=max(r['initial_relative_error'] for r in rows),max_final_relative_error=max(r['final_relative_error'] for r in rows),max_symmetry=max(r['symmetry_ratio'] for r in rows),minus_A_diag_all_positive=all(r['minus_A_diag_all_positive'] for r in rows),motion=movement,raw_count=24,elapsed_s=time.monotonic()-phase_start)
    require(all(math.isfinite(v) for v in (summary['max_initial_relative_error'],summary['max_final_relative_error'])),'non-finite relative error')
    out_json(root/'q1_coarse_summary.json',summary)
    out_json(root/'manifest_context_coarse.json',dict(provenance=PROVENANCE,mesh_grade='coarse',coordinate_convention=COORDS,medium_reference_Ur=8,medium_reference='medium frozen heave/case.json',outputs_sha256='OUTPUTS_coarse.sha256',selected_systems=[r['system'] for r in rows]))
    with (root/'OUTPUTS_coarse.sha256').open('x') as f:
        paths=list((root/'Solving').rglob('*'))+list(root.glob('*_coarse.*'))+[root/'period_gate.json',root/'log.blockMesh',root/'log.advance',branches['control']/'log.solve',branches['dump']/'log.solve',cp/'polyMesh/points',final]
        for p in sorted(set(paths)):
            if p.is_file() and p.name not in {'OUTPUTS_coarse.sha256','job_coarse.sh'}: f.write(f'{sha(p)}  {p.relative_to(root)}\n')
    space(root);status(root,'complete');return 0 if summary['pass_count']==20 and movement['max_displacement_m']>0 else 2

if __name__=='__main__':
    if sys.argv[1]=='static': print('heave/B dictionary preflight:',static(Path(sys.argv[2]))['settings'])
    else: sys.exit(run(Path(sys.argv[2]),sys.argv[3]))
