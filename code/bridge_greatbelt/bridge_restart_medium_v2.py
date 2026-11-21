#!/usr/bin/env python3
"""L41.5a: approved 19.84-s checkpoint paired short restart; no old roots written."""
import argparse, csv, hashlib, importlib.util, json, math, os, re, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np
from scipy.io import mmread
from scipy.sparse.linalg import norm

SOURCE=Path('/groups/kareem/[用户]/L29_6c1/S0_prod_20261116_v1')
PARENT=Path('/groups/kareem/[用户]/L41_5a_LINSYS/bridge_greatbelt')
PROV='L29.6c1 S0，CFD 线搭建；S0 未定版，网格收敛约 11-25 判定'
COORD={'x':'inflow +x, 10 m/s','y':'vertical/heave','z':'spanwise, empty, 2D','B_m':3.1,'span_m':0.1,'Ur':8,'time_axis':'native OpenFOAM timeIndex and inner correction; no stitching, deduplication or overlap'}
CAP=5_000_000_000

def need(ok,msg):
    if not ok: raise RuntimeError(msg)
def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def files(p):return sorted(x for x in p.rglob('*') if x.is_file())
def write_json(path, obj):
    with path.open('x') as f:json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False)
def phase(root, name):
    print('PHASE',name,flush=True); (root/('phase_'+name)).touch(exist_ok=False)
def usage(reserve=0):
    size=int(subprocess.check_output(['du','-sb',str(PARENT)],text=True).split()[0]); free=shutil.disk_usage(PARENT).free
    print('STORAGE',size,reserve,free,flush=True)
    need(size+reserve<=CAP and free>=reserve,(size,reserve,'5GB limit'));return size
def module(grade,root):
    spec=importlib.util.spec_from_file_location('bridge_original',root/f'bridge_{grade}.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def logrun(case, binary, log, env, limit):
    with log.open('x') as out:
        p=subprocess.run(['timeout','--kill-after=10s',str(limit),binary,'-noFunctionObjects'],cwd=case,env=env,stdout=out,stderr=subprocess.STDOUT)
    need(p.returncode==0,(binary,case,p.returncode));need('End' in log.read_text().splitlines(),('missing End',log))
def conf(m,case,**kwargs):m.conf(case,**kwargs)
def run(root, grade, binary):
    need(root==PARENT/'medium_r2' and grade=='medium','root/grade mismatch')
    m=module(grade,root); usage(350_000_000)
    phase(root,'stage')
    case=root/'advance'; shutil.copytree(root/'frozen/heave',case)
    cfg=m.static(case); need(cfg['settings']=='01n_B' and cfg['dof']=='heave','heave B'); need(cfg['Ur']==8,'Ur')
    m.sh(case,['blockMesh'],root/'log.blockMesh',300)
    boundary=m.boundary(case/'constant/polyMesh/boundary')
    allowed={'wall','patch','empty','symmetryPlane','symmetry','wedge','cyclic'}
    need(set(boundary.values())<=allowed,('unsupported patch',boundary))
    write_json(root/'boundary_restart.json',{'patches':boundary,'sha256':sha(case/'constant/polyMesh/boundary')})
    # Use only the separately staged, source-hash-verified 19.84 directory.
    source=root/'checkpoint_source/19.84'; need(source.is_dir(),'staged checkpoint missing')
    source_list=files(source); need(source_list and all(p.is_file() for p in source_list),'checkpoint empty')
    before={str(p.relative_to(source)):sha(p) for p in source_list}
    cp=case/'19.84'; shutil.copytree(source,cp)
    after={str(p.relative_to(cp)):sha(p) for p in files(cp)}
    need(before==after,'checkpoint transfer SHA mismatch')
    for field in ('U','p','k','omega','nut','uniform/time','polyMesh/points'):
        need((cp/field).is_file(),('missing checkpoint field',field))
    # Compare point topology and count without replacing the frozen constant mesh.
    orig=m.points(case/'constant/polyMesh/points'); moved=m.points(cp/'polyMesh/points')
    need(orig.shape==moved.shape,'checkpoint points do not match rebuilt mesh')
    poly=case/'constant/polyMesh'; ncell=m.mesh_count(poly/'owner')
    need(ncell>0 and len(orig)>0,'empty mesh')
    last_motion=float(re.findall(r'^\(([\d.]+) \(\(', (case/'constant/motion.dat').read_text(),re.M)[-1])
    need(last_motion>19.84+0.01,('motion.dat does not cover continuation',last_motion))
    write_json(root/'checkpoint_verify.json',{'provenance':PROV,'grade':grade,'source':'L29_6c1 S0 '+grade+'/heave/19.84','file_sha256':before,'destination_verified':len(before),'mesh_cells':ncell,'point_count':len(orig),'point_displacement_from_reference_max_m':float(np.linalg.norm(moved-orig,axis=1).max()),'motion_dat_last_s':last_motion,'motion_dat_sha256':sha(case/'constant/motion.dat'),'coordinates':COORD})
    usage(2_400_000_000 if grade=='medium' else 1_100_000_000)
    idxmatch=re.search(r'\bindex\s+(\d+)\s*;', (cp/'uniform/time').read_text());need(idxmatch is not None,'missing timeIndex'); idx=int(idxmatch[1])
    # One non-dump step checks continuity. Write just that step and branch from it.
    conf(m,case,startFrom='latestTime',stopAt='nextWrite',endTime='20.0',writeControl='timeStep',writeInterval=idx+1,purgeWrite=0,writePrecision=16)
    phase(root,'one_step');env=os.environ.copy();env.update(LINSYS_DUMP='0',LINSYS_ROOT=str(case))
    logrun(case,'pimpleFoam',root/'log.one_step',env,1200)
    steps=sorted((p for p in case.iterdir() if p.is_dir() and re.fullmatch(m.NUM,p.name) and float(p.name)>19.84),key=lambda p:float(p.name))
    need(len(steps)==1,('expected one restarted step',steps)); check=steps[0]
    need((check/'polyMesh/points').is_file(),'first step mesh not written')
    # Check physical restart continuity at first pressure solve; no claim of exact S0 trajectory.
    first_log=root/'log.one_step'; need('Solving for p' in first_log.read_text(),'one step pressure absent')
    write_json(root/'one_step.json',{'start':'19.84','end':check.name,'start_index':idx,'end_index':idx+1,'start_points_sha256':sha(cp/'polyMesh/points'),'end_points_sha256':sha(check/'polyMesh/points')})
    usage(1_600_000_000 if grade=='medium' else 700_000_000)
    # Three full steps, eight corrections each; deliver first 20 unique solves.
    branches={}
    for label in ('control','dump'):
        c=root/label;c.mkdir()
        for fld in ('system','constant','0'):shutil.copytree(case/fld,c/fld)
        shutil.copytree(check,c/check.name)
        conf(m,c,startFrom='latestTime',stopAt='nextWrite',endTime='20.0',writeControl='timeStep',writeInterval=idx+4,purgeWrite=0,writePrecision=16)
        branches[label]=c
    write_json(root/'run_config_restart.json',{'provenance':PROV,'check_time':check.name,'start_index':idx+1,'binary_sha256':sha(Path(binary)),'control_dict_sha256':{k:sha(v/'system/controlDict') for k,v in branches.items()},'coordinates':COORD})
    (branches['dump']/'Solving').mkdir();phase(root,'paired')
    tc,wc=m.solve(branches['control'],binary,False,1800); usage(1_300_000_000 if grade=='medium' else 600_000_000)
    td,wd=m.solve(branches['dump'],binary,True,1800)
    need(list(map(float,tc))==list(map(float,td)),('not paired',tc,td))
    with (root/('overhead_'+grade+'_restart.csv')).open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['step','time','control_wall_s','dump_wall_s','delta_s','increment_ratio','total_ratio','first_includes_startup']);writer.writeheader()
        for j,(t,c,d) in enumerate(zip(td,wc,wd),1):writer.writerow(dict(step=j,time=t,control_wall_s=c,dump_wall_s=d,delta_s=d-c,increment_ratio=(d-c)/c,total_ratio=d/c,first_includes_startup=(j==1)))
    final,=(p for p in branches['dump'].glob('*/polyMesh/points') if re.fullmatch(m.NUM,p.parent.parent.name) and math.isclose(float(p.parent.parent.name),float(td[-1]),abs_tol=1e-10))
    pp=m.points(check/'polyMesh/points');qq=m.points(final);need(pp.shape==qq.shape,'point indexing');dis=np.linalg.norm(pp-qq,axis=1)
    write_json(root/'movement_restart.json',{'start_time':check.name,'end_time':td[-1],'moving_points':int(np.count_nonzero(dis)),'max_displacement_m':float(dis.max()),'start_sha256':sha(check/'polyMesh/points'),'end_sha256':sha(final),'coordinates':COORD})
    phase(root,'q1');rows=m.audit(root,branches['dump'],td,idx+1)
    # Existing audit produces 20 entries with correction metadata; append provenance via sidecar.
    need(len(rows)==20,'Q1 count')
    write_json(root/'q1_restart_summary.json',{'count':20,'passed':sum(bool(r['q1_pass']) for r in rows),'max_initial_relative_error':max(r['initial_relative_error'] for r in rows),'max_final_relative_error':max(r['final_relative_error'] for r in rows),'max_symmetry_ratio':max(r['symmetry_ratio'] for r in rows),'all_minus_A_diagonal_positive':all(r['minus_A_diag_all_positive'] for r in rows),'coordinates':COORD,'provenance':PROV})
    usage()
    with (root/'OUTPUTS_restart.sha256').open('x') as f:
        chosen=files(root/'Solving')+[p for p in root.iterdir() if p.is_file() and p.name not in {'OUTPUTS_restart.sha256','job_restart.sh'}]+[branches['control']/'log.solve',branches['dump']/'log.solve',check/'polyMesh/points',final]
        for p in sorted(set(chosen)):f.write(f'{sha(p)}  {p.relative_to(root)}\n')
    phase(root,'complete');return 0 if all(r['q1_pass'] for r in rows) and dis.max()>0 else 2

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('grade',choices=('coarse','medium'));ap.add_argument('root');ap.add_argument('binary');a=ap.parse_args();sys.exit(run(Path(a.root).resolve(),a.grade,a.binary))
