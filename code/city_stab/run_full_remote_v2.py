"""Run on Colab A100 only; immutable three-case monitored city campaign."""
from pathlib import Path
import tarfile, subprocess, os, time, csv, json, shutil, traceback
R=Path('/content/luw_city_full_1015_v2'); R.mkdir(exist_ok=False)
def log(msg):
    with (R/'progress.log').open('a',buffering=1) as f:f.write(str(msg)+'\n')
    print(msg,flush=True)
def inspect(trace):
    if not trace.exists():return None
    with trace.open() as f:rows=list(csv.DictReader(f))
    if not rows:return None
    q=rows[-1];step=int(q['step']); u=float(q['max_u_lattice']); lo=float(q['min_rho']);hi=float(q['max_rho'])
    reason=None
    if u>0.3:reason=f'max_u={u} > .3 at {step}'
    if step>=3000 and (lo<.90 or hi>1.10):reason=f'rho=[{lo},{hi}] outside [.90,1.10] at {step}'
    if step>=4000:
        prev=next((r for r in rows if int(r['step'])==step-1000),None)
        if prev:
            rate=abs(float(q['mass_fluid'])/float(prev['mass_fluid'])-1)
            if rate>=.0005:reason=f'mass/1000={rate:.8g} >= .0005 at {step}'
    return {'step':step,'max_u':u,'rho':[lo,hi],'reason':reason,'mass':float(q['mass_fluid'])}
try:
    with tarfile.open('/content/city_monitor_inputs.tar.gz') as tar:tar.extractall(R/'base',filter='data')
    for tag,a in [('a0','0.0'),('a07','0.70'),('a10','1.0')]:
        root=R/tag;shutil.copytree(R/'base',root,ignore=shutil.ignore_patterns('bin','obj'))
        src=root/'FluidX3D';case=root/'case'; p=src/'src/defines.hpp';s=p.read_text()
        assert s.count('//#define GROUND_WALL_MODEL')==1 and s.count('//#define CITY_STABILITY_MONITOR')==1
        p.write_text(s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL').replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
        setup=src/'src/setup.cpp';s=setup.read_text()
        old='if(std::sqrt(max_u2)>3.0*3.9286416*u_scale || std::abs(drift)>0.001) print_error("city stability gate exceeded");'
        assert s.count(old)==1
        setup.write_text(s.replace(old,'// External run controller enforces city stability; open-domain mass is not conserved.').replace('(dom->flags.x[i]&TYPE_BO)==TYPE_S','(dom->flags.x[i]&0x03u)==TYPE_S'))
        with (root/'build.log').open('w') as f:build=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=700)
        log(f'{tag} BUILD={build.returncode}');assert build.returncode==0,(root/'build.log').read_text()[-2000:]
        env=os.environ.copy();env['LUW_GROUND_MIX_A']=a
        with (root/'solver.log').open('w',buffering=1) as f:
            proc=subprocess.Popen([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
            trace=case/'RESULTS/city_stability.csv'; seen=-1;failure=None;t0=time.time()
            while proc.poll() is None:
                time.sleep(10)
                info=inspect(trace)
                if info and info['step']!=seen:
                    seen=info['step'];(root/'monitor_latest.json').write_text(json.dumps(info));
                    if seen%1000==0:log(f'{tag} STEP={seen} max_u={info["max_u"]:.6f} rho={info["rho"]} mass={info["mass"]:.4f}')
                    if info['reason']:
                        failure=info['reason'];log(f'{tag} STABILITY_STOP '+failure);proc.terminate()
                        try:proc.wait(timeout=20)
                        except subprocess.TimeoutExpired:proc.kill()
                        break
                if time.time()-t0>3600:
                    failure='walltime 3600s';proc.terminate();log(f'{tag} TIMEOUT');break
            code=proc.wait()
        if trace.exists():shutil.copy2(trace,R/(tag+'_trace.csv'))
        (root/'solver.exit').write_text(str(code));log(f'{tag} SOLVE_EXIT={code} failure={failure} seconds={time.time()-t0:.2f}')
        if code!=0 or failure:break
        # One old extraction script, same frozen R10a point registration and scalar definition.
        (root/'solver_a.exit').write_text('exit=0\n');(root/'case_a').symlink_to(case,target_is_directory=True)
        shutil.copy2('/content/points_w_r7.json',root/'points_w_r7.json')
        script=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{root}')")
        (root/'extract_city.py').write_text(script)
        with (root/'extract.log').open('w') as f:e=subprocess.run(['python3',str(root/'extract_city.py')],cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=900)
        log(f'{tag} EXTRACT={e.returncode}');assert e.returncode==0,(root/'extract.log').read_text()[-3000:]
        rows=json.loads((root/'offset_samples_a_r10.json').read_text())['rows'];assert len(rows)==80
        shutil.copy2(root/'offset_samples_a_r10.json',R/(tag+'_samples.json'))
        (R/(tag+'.done')).write_text('ok')
except Exception:log('ERROR '+traceback.format_exc()[-4000:]);(R/'error.txt').write_text(traceback.format_exc())
finally:(R/'all.done').write_text('terminal\n')
