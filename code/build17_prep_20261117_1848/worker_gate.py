#!/usr/bin/env python3
"""Build17 archived v11 city campaign; no A-stage rerun."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, tarfile, time, traceback
import numpy as np
from remote_worker_run2 import vtk_map
from t5_sampling import write_points

CASES=('E_s101_off','E_s101_on','E_s102_on')
PRODUCTS=('solver.log','actual_opencl.cl','points80.json','fluid_mask.json','exit.json')
OFF_SHA='6b57372b53206a9af04069bf25c0f756f77e78ef92d86d658a1495c863f4b279'
V11='13bc199a005cfdf99cb7e81de79382676fcc4c2479e6abcc35ff4ef9296be9aa'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def seal(p):
    h=sha(p); side=p.with_name(p.name+'.sha256'); tmp=side.with_suffix('.pending')
    tmp.write_text(h+'\n');tmp.replace(side)
    print('READY',p.name,h,flush=True)
    return h

def record(p,x):
    p.write_text(json.dumps(x,indent=2)+'\n');return seal(p)

def unpack(p,d,root):
    with tarfile.open(p) as t:
        for m in t.getmembers():
            if not ((m.name==root or m.name.startswith(root+'/')) and '..' not in pathlib.PurePosixPath(m.name).parts and (m.isfile() or m.isdir())):raise ValueError(m.name)
        t.extractall(d,filter='data')

def mask(v):
    h=hashlib.sha256();solid=0
    for slab in v['fields']['fluid']:
        if not np.all((slab==0)|(slab==1)):raise ValueError('nonbinary fluid field')
        b=slab.astype(np.uint8);h.update(b.tobytes(order='C'));solid+=b.size-int(b.sum())
    return dict(dims=v['dims'],origin=v['origin'],spacing=v['spacing'],solid_cells=solid,total_cells=int(np.prod(v['dims'])),mask_sha256=h.hexdigest(),encoding='one uint8 per cell; 0 solid, 1 fluid; x fastest, then y then z')

def main(content,stub=None):
    root=content/'t9b17';root.mkdir();o=root/'out';o.mkdir()
    try:
        b=json.loads((content/'t9b17_budget.json').read_text());deadline=float(b['work_deadline']); target=OFF_SHA
        if stub is not None:
            if content==pathlib.Path('/content') or b.get('mode')!='local-fixture':raise RuntimeError('local test hook forbidden')
            target=b['fixture_off_sha']
        elif b.get('mode')!='production':raise RuntimeError('production budget required')
        print('MODE',b['mode'],'target',target,flush=True)
        def guard(seconds,stage):
            if time.time()+seconds>=deadline:raise TimeoutError('budget stop before '+stage)
        def run(args,cwd,log,env,limit):
            guard(0,log.name);start=time.time();rc=None
            try:
                with log.open('x') as f:
                    rc=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=min(limit,deadline-time.time())).returncode
            finally:
                if log.exists():seal(log)
                if log.name.endswith('_solver.log'):
                    record(log.with_name(log.name.replace('_solver.log','_exit.json')),dict(solver_exit=rc,elapsed_s=time.time()-start))
            if rc!=0:raise RuntimeError(f'{log.name}: exit {rc}')
        arc=content/'t9b12_source.tar.gz'; man=json.loads((content/'t9b12_manifest.json').read_text())
        if sha(arc)!=V11 or man['archive_sha256']!=V11:raise ValueError('v11 archive SHA')
        unpack(arc,root,'FluidX3D_facade_v11');src=root/'FluidX3D_facade_v11'
        for n,h in man['members'].items():
            if sha(src/n)!=h:raise ValueError('v11 member '+n)
        deck=content/'stage_t5.tar.gz';dm=json.loads((content/'archive.json').read_text())
        if sha(deck)!=dm['sha256']:raise ValueError('T5 archive SHA')
        unpack(deck,root,'stage')
        ref=json.loads((content/'B2u_reference_points.json').read_text())
        if ref['uref']!=3.9286416 or len(ref['rows'])!=80 or {int(p['id']) for p in ref['rows']}!=set(range(1,81)):raise ValueError('T5 reference')
        built={}; pm={}; masks={}
        for idx,label in enumerate(CASES):
            state=label.rsplit('_',1)[-1]
            guard((0 if stub else 2520 if state not in built else 2420),label)
            case=root/'stage/cases'/label; conf=case/'conf.luwpf'; seed=102 if idx==2 else 101
            text=conf.read_text()
            if any(text.splitlines().count(s)!=1 for s in ('run_nstep = 31000','purge_avg = 20000','purge_avg_stride = 40',f'vk_inlet_seed = {seed}')):raise ValueError('T5 deck '+label)
            if state not in built:
                cpu=root/('city_'+state);shutil.copytree(src,cpu)
                if state=='on':
                    path=cpu/'src/defines.hpp';x=path.read_text();needle='//#define FACADE_FREE_SLIP // T9b-build default OFF'
                    if x.count(needle)!=1:raise ValueError('facade toggle anchor')
                    path.write_text(x.replace(needle,'#define FACADE_FREE_SLIP // T9b-build ON'))
                run(['make','Linux','-j8'],cpu,o/f'build_{state}.log',None,1200)
                exe=cpu/'bin/FluidX3D'
                if not exe.is_file() or not os.access(exe,os.X_OK):raise RuntimeError('build produced no executable')
                if stub:shutil.copyfile(stub,exe);print('LOCAL_ONLY substituted built solver',exe,flush=True)
                built[state]=cpu
            cpu=built[state]; cl=o/f'{label}_actual_opencl.cl'
            env={k:v for k,v in os.environ.items() if k not in ('LUW_EXPORT_FLAGS','LUW_FLAGS_ONLY','T9B_GATE_OUTPUT','T9B_GATE_SHAPE','T9B_WALL_Y')}
            env.update(LD_LIBRARY_PATH=str(cpu/'src/OpenCL/lib')+':'+env.get('LD_LIBRARY_PATH',''),LUW_CAPTURE_CL=str(cl),LUW_GROUND_MIX_A='0')
            print('START',label,'remaining_s',round(deadline-time.time()),flush=True)
            try:run([str(cpu/'bin/FluidX3D'),str(conf)],case,o/f'{label}_solver.log',env,4200)
            finally:
                if cl.is_file() and cl.stat().st_size:seal(cl)
            if not (cl.is_file() and cl.stat().st_size):raise RuntimeError('no actual OpenCL '+label)
            vtk=list((case/'RESULTS/vtk').glob('*_avg-*.vtk'))
            if len(vtk)!=1:raise RuntimeError((label,vtk))
            v=vtk_map(vtk[0]);dims,origin=((500,500,4),(0.,0.,0.)) if stub else ((500,500,270),(0.,0.,-20.))
            if (v['dims'],v['origin'],v['spacing'])!=(dims,origin,(1.,1.,1.)):raise ValueError('VTK grid contract '+label)
            masks[label]=mask(v);record(o/f'{label}_fluid_mask.json',masks[label]); points=write_points(o,label,ref,v,vtk,sha)
            ph=seal(points);pm[label]=json.loads(points.read_text())
            extra=[];passed=True
            if idx==0:
                record(o/'gate1.json',dict(passed=ph==target,actual=ph,target=target,mode=b['mode']));extra=['gate1.json'];passed=ph==target
            elif idx==1:
                a,z=CASES[:2]; geom=masks[a]==masks[z]
                aa={x['id']:x for x in pm[a]['rows']};zz={x['id']:x for x in pm[z]['rows']}
                if aa.keys()!=zz.keys() or not all((aa[i]['obs'],aa[i]['xyz_m'])==(zz[i]['obs'],zz[i]['xyz_m']) for i in aa):raise RuntimeError('pair registration mismatch')
                ids=sorted(i for i in aa if aa[i]['Su']!=zz[i]['Su'])
                record(o/'gate3.json',dict(passed=geom,off=masks[a],on=masks[z],mode=b['mode']))
                record(o/'points80_difference.json',dict(passed=bool(ids),different_ids=ids,count=len(ids),max_abs_delta_Su=max(abs(aa[i]['Su']-zz[i]['Su']) for i in aa),mode=b['mode']))
                extra=['gate3.json','points80_difference.json'];passed=geom and bool(ids)
            names=[f'{label}_{x}' for x in PRODUCTS]+extra
            if idx<2:names.append(f'build_{state}.log')
            expected={n:(o/(n+'.sha256')).read_text().strip() for n in names}
            record(o/f'{label}_handoff.json',dict(sha256=expected,passed=passed));ack=o/f'{label}.ack.json'
            while not ack.exists():guard(0,label+' ACK');time.sleep(.25 if stub else 2)
            if json.loads(ack.read_text())!=expected:raise RuntimeError('host ACK mismatch '+label)
            print('HOST_VERIFIED',label,flush=True)
            if not passed:raise RuntimeError('city gate failed at '+label)
        record(o/'run.done',dict(mode=b['mode'],verified_cases=list(CASES)));print('ALL_DONE',flush=True)
    except BaseException:
        path=o/'run.failed';path.write_text(traceback.format_exc());seal(path);raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--content',type=pathlib.Path,default=pathlib.Path('/content'));p.add_argument('--stub',type=pathlib.Path)
    a=p.parse_args();main(a.content.resolve(),a.stub.resolve() if a.stub else None)
