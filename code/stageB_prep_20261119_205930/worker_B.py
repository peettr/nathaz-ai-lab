#!/usr/bin/env python3
"""T17 B ordered real-worker pipeline. Solver only stubbed in local dry run.
Production source must implement T17_B_OUTPUT contract before GPU authorization.
"""
import argparse, hashlib, json, os, pathlib, shutil, subprocess, tarfile, time, traceback
from assert_T17 import evaluate, seed_metrics
GROUPS=('bounce','t4','t15'); SEEDS=('1','2')
RATE=5.4

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def seal(p):
    (p.parent/(p.name+'.sha256')).write_text(sha(p)+'\n')
    print('READY',p.name,sha(p),flush=True)

def enough(deadline,remaining_seconds,teardown=90):
    margin=deadline-time.time()-remaining_seconds-teardown
    print('PRODUCTION_CUT_MARGIN',round(margin,3),'remaining_required_s',round(remaining_seconds,3),flush=True)
    if margin<=0:raise TimeoutError('next case cannot fit budget')
    return margin

def call(exe,src,output,group,seed,phase,steps,timeout,fixture):
    env={**os.environ,'T17_B_OUTPUT':str(output),'T17_B_PHASE':phase,'T17_B_GROUP':group,
         'T17_B_SEED':seed,'T17_B_STEPS':str(steps),
         'LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
    if not fixture:env['T17_STAGE_A_ALLOW']='1'
    with output.with_suffix('.solver.log').open('x') as f:
        rc=subprocess.run([str(exe)],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
    log=output.with_suffix('.solver.log');seal(log)
    if rc:raise RuntimeError('solver '+phase+' '+group+seed+' rc='+str(rc))
    if not output.is_file():raise RuntimeError('missing native statistical producer '+str(output))
    seal(output)
    return json.loads(output.read_text())

def execute(c,stub=None):
    fixture=stub is not None
    budget=json.loads((c/'t17b_budget.json').read_text())
    if budget['mode']!=('fixture' if fixture else 'production'):raise ValueError('fixture mode mismatch')
    deadline=budget['work_deadline'];spec=json.loads((c/'t17b_manifest.json').read_text())
    arc=c/'t17b_stage.tar.gz'
    if sha(arc)!=spec['archive_sha256']:raise ValueError('stage hash mismatch')
    root=c/'t17b';root.mkdir(exist_ok=False);o=root/'out';o.mkdir()
    try:
        with tarfile.open(arc) as t:
            for m in t:
                p=pathlib.PurePosixPath(m.name)
                if not p.parts or p.parts[0]!='pack_stage' or '..' in p.parts or not(m.isdir() or m.isfile()):
                    raise ValueError('unsafe archive path')
            t.extractall(root,filter='data')
        # Three compiled groups, two paired seeds each, same executable per group.
        exes={};stage=root/'pack_stage'
        for g in GROUPS:
            src=stage/spec['variant_names'][g]
            for f,h in spec['variants'][spec['variant_names'][g]].items():
                if sha(src/'src'/f)!=h:raise ValueError('source hash '+g+'/'+f)
            log=o/(g+'_build.log')
            with log.open('x') as out:
                rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=out,stderr=subprocess.STDOUT,timeout=500).returncode
            seal(log)
            if rc:raise RuntimeError('build failed '+g)
            exe=src/'bin/FluidX3D'
            if not exe.is_file():raise RuntimeError('no binary '+g)
            if fixture:shutil.copyfile(stub,exe);exe.chmod(0o755)
            exes[g]=(exe,src)
        verified=[]
        for g in GROUPS:
            for seed in SEEDS:
                label=g+'_s'+seed;exe,src=exes[g]
                steps_per_T=budget['steps_per_T'];speed=budget['steps_per_second'][g]
                # V0: 5T initially, then at most three 1T increments; 2T statistics after equilibrium.
                # Reserve WORST CASE of remaining cases and this case including 3T extensions.
                remaining=[(x,y) for x in GROUPS for y in SEEDS if (x,y) not in verified]
                worst=sum((10*steps_per_T/budget['steps_per_second'][x]+budget['per_case_overhead_s']) for x,y in remaining)
                enough(deadline,worst)
                attempts=[];equilibrated=False
                for extension in range(4):
                    equil_steps=(5 if extension==0 else 1)*steps_per_T
                    path=o/(label+'_v0_'+str(extension)+'.json')
                    raw=call(exe,src,path,g,seed,'equilibrium',equil_steps,
                             min(3600,max(1,deadline-time.time()-90)),fixture)
                    pair=raw['last_T_two_half_windows'];attempts.append(pair)
                    from assert_T17 import spread
                    if all(spread(pair[0][key],pair[1][key])<=.02 for key in ('momentum','tau_x','ustar')):
                        equilibrated=True;break
                if not equilibrated:
                    # Complete the predeclared 2T window only to preserve a common
                    # raw record; seed_metrics gives NOT EVALUATED to science if V0 fails.
                    print('V0_UNBALANCED_SCIENCE_NOT_EVALUATED',label,flush=True)
                stat=o/(label+'_statistics.json')
                raw=call(exe,src,stat,g,seed,'statistics',2*steps_per_T,
                         min(3600,max(1,deadline-time.time()-90)),fixture)
                case={'v0_attempts':attempts,**raw}
                seed_metrics(case)  # validates contract; scientific judgement after all six.
                path=o/(label+'_case.json');path.write_text(json.dumps(case)+'\n');seal(path)
                files=[p for p in o.iterdir() if p.name.startswith(label+'_') and p.is_file() and not p.name.endswith('.sha256')]
                hashes={p.name:sha(p) for p in files}
                hand=o/(label+'_handoff.json');hand.write_text(json.dumps({'sha256':hashes})+'\n');seal(hand)
                ack=o/(label+'.ack.json')
                while not ack.exists():
                    if time.time()+10>deadline:raise TimeoutError('missing host ACK '+label)
                    time.sleep(.1 if fixture else 2)
                if json.loads(ack.read_text())!=hashes:raise RuntimeError('bad ACK '+label)
                print('HOST_VERIFIED',label,flush=True);verified.append((g,seed))
        assembled={'schema':'T17-B-v1','cases':{g:{s:json.loads((o/(g+'_s'+s+'_case.json')).read_text()) for s in SEEDS} for g in GROUPS}}
        (o/'input_all.json').write_text(json.dumps(assembled)+'\n');seal(o/'input_all.json')
        result=evaluate(assembled)
        (o/'T17_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');seal(o/'T17_result.json')
        (o/'run.done').write_text(json.dumps({'verified':verified})+'\n');seal(o/'run.done')
    except BaseException:
        (o/'run.failed').write_text(traceback.format_exc());seal(o/'run.failed');raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--content',type=pathlib.Path,default=pathlib.Path('/content'));p.add_argument('--stub',type=pathlib.Path)
    a=p.parse_args();execute(a.content.resolve(),a.stub.resolve() if a.stub else None)
