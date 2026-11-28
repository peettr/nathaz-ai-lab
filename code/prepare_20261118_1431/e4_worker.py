#!/usr/bin/env python3
"""T15 worker: exact archive verification/build/solver/handoff for dry and production."""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, tarfile, time, traceback
R = pathlib.Path('/content')
NAMES = ('solver.log', 'exit.json', 'wall_tau_actual.csv', 'actual_opencl.cl')
CASES = ('dx1p0_s107', 'dx1p0_s108', 'dx1p0_s109')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576), b''): h.update(b)
    return h.hexdigest()
def seal(p):
    (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n')
    print('READY',p.name,sha(p),flush=True)
def run(c, stub):
    b=json.loads((c/'t15_budget.json').read_text()); mode=b['mode']; deadline=b['work_deadline']
    if bool(stub)!=(mode=='fixture') or (stub and c==R): raise ValueError('stub is fixture-only')
    o=c/'t15/out'; o.mkdir(parents=True,exist_ok=False)
    try:
        arc=c/'t15_stage.tar.gz'; man=json.loads((c/'t15_manifest.json').read_text())
        if sha(arc)!=man['archive_sha256']:raise ValueError('archive SHA mismatch')
        dest=c/'t15/stage'
        with tarfile.open(arc) as tf:
            for m in tf:
                p=pathlib.PurePosixPath(m.name)
                if p.parts[0]!='stage' or '..' in p.parts or not (m.isfile() or m.isdir()):raise ValueError('unsafe archive member')
            tf.extractall(c/'t15',filter='data')
        src=dest/'FluidX3D_on'
        for n,h in man['source_on'].items():
            if sha(src/'src'/n)!=h:raise ValueError('source mismatch '+n)
        with (o/'build.log').open('x') as log:
            rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=log,stderr=subprocess.STDOUT,timeout=900).returncode
        seal(o/'build.log')
        if rc:raise RuntimeError('build failed '+str(rc))
        exe=src/'bin/FluidX3D'
        if not exe.is_file():raise ValueError('no compiled solver')
        if stub:
            shutil.copyfile(stub,exe);exe.chmod(0o755);print('FIXTURE solver binary replaced after real build',flush=True)
        for case in CASES:
            if time.time()+ (0 if stub else 900)>=deadline:raise TimeoutError('budget before '+case)
            base=c/'t15'/('case_'+case);shutil.copytree(dest/case,base)
            cfg=base/'conf.luwpf'
            if sha(cfg)!=man['cases'][case]['conf_sha256']:raise ValueError('config SHA mismatch '+case)
            label='T15_'+case
            cl=o/(label+'_actual_opencl.cl')
            env={**os.environ,'LUW_CAPTURE_CL':str(cl),'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
            with (o/(label+'_solver.log')).open('x') as log:
                rc=subprocess.run([str(exe),str(cfg)],cwd=base,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300 if stub else min(1800,max(1,deadline-time.time()-240))).returncode
            seal(o/(label+'_solver.log'))
            x=o/(label+'_exit.json');x.write_text(json.dumps({'solver_exit':rc})+'\n');seal(x)
            if rc:raise RuntimeError('solver failed '+case)
            tau=base/'RESULTS/wall_tau_actual.csv'
            if not tau.is_file() or not tau.stat().st_size:raise RuntimeError('missing native wall tau '+case)
            shutil.copyfile(tau,o/(label+'_wall_tau_actual.csv'));seal(o/(label+'_wall_tau_actual.csv'))
            if not cl.is_file() or not cl.stat().st_size:raise RuntimeError('missing compiled OpenCL '+case)
            seal(cl)
            files=[label+'_'+n for n in NAMES]+(['build.log'] if case==CASES[0] else [])
            hashes={n:sha(o/n) for n in files}
            hand=o/(label+'_handoff.json');hand.write_text(json.dumps({'sha256':hashes,'mode':mode})+'\n');seal(hand)
            ack=o/(label+'.ack.json')
            while not ack.exists():
                if time.time()+2>=deadline:raise TimeoutError('ACK deadline '+case)
                time.sleep(.1 if stub else 2)
            if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch '+case)
            print('HOST_VERIFIED',case,flush=True)
        done=o/'run.done';done.write_text(json.dumps({'verified_cases':CASES,'mode':mode})+'\n');seal(done)
    except BaseException:
        p=o/'run.failed';p.write_text(traceback.format_exc());seal(p);raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--content',type=pathlib.Path,default=R);p.add_argument('--stub',type=pathlib.Path);a=p.parse_args()
    run(a.content.resolve(),a.stub.resolve() if a.stub else None)
