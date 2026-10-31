"""Colab-only one-case Case E isolation runner; never run on 工作站."""
from pathlib import Path
import csv, json, os, shutil, subprocess, tarfile, time, traceback
TAG=Path('/content/variant.txt').read_text().strip()
assert TAG in ('r1_fp32_off','r2_fp16c_wall')
R=Path('/content/luw_iso_'+TAG+'_1015'); R.mkdir(exist_ok=False)
def log(s):
    with (R/'progress.log').open('a',buffering=1) as f:f.write(str(s)+'\n')
    print(s,flush=True)
def inspect(path):
    if not path.exists():return None
    with path.open() as f:rows=list(csv.DictReader(f))
    if not rows:return None
    q=rows[-1];n=int(q['step']);v=float(q['max_u_lattice']);lo=float(q['min_rho']);hi=float(q['max_rho'])
    reason=None
    if q['first_nonfinite_xyz_component']:reason='nonfinite '+q['first_nonfinite_xyz_component']
    elif v>0.3:reason='speed > .3'
    elif n>=3000 and (lo<.90 or hi>1.10):reason='rho outside [.90,1.10]'
    return {'step':n,'max_u':v,'lo':lo,'hi':hi,'mass':float(q['mass_fluid']),'reason':reason}
try:
    with tarfile.open('/content/city_isolate_inputs_v2.tar.gz') as tar:tar.extractall(R,filter='data')
    p=R/'FluidX3D/src/defines.hpp';s=p.read_text()
    assert s.count('//#define CITY_STABILITY_MONITOR')==1
    s=s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR')
    if TAG=='r2_fp16c_wall':
        assert s.count('//#define GROUND_WALL_MODEL')==1 and s.count('//#define FP16C')==1
        s=s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL').replace('//#define FP16C','#define FP16C')
    p.write_text(s)
    with (R/'build.log').open('w') as f:res=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
    log('BUILD '+str(res.returncode));assert res.returncode==0,(R/'build.log').read_text()[-3000:]
    env=os.environ.copy()
    if TAG=='r2_fp16c_wall':env['LUW_GROUND_MIX_A']='0.0'
    case=R/'case';trace=case/'RESULTS/city_stability.csv'
    with (R/'solver.log').open('w',buffering=1) as f:
        proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
        seen=-1;reason=None;t0=time.time()
        while proc.poll() is None:
            time.sleep(6)
            row=inspect(trace)
            if row and row['step']!=seen:
                seen=row['step']; (R/'latest.json').write_text(json.dumps(row))
                if seen%1000==0:log(f'STEP {seen} max_u={row["max_u"]:.6f} rho=[{row["lo"]:.6f},{row["hi"]:.6f}] mass={row["mass"]:.6f}')
                if row['reason']:
                    reason=row['reason'];log('STABILITY_STOP '+reason+' step='+str(seen));proc.terminate()
                    try:proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:proc.kill()
                    break
            if time.time()-t0>3600:
                reason='walltime';proc.terminate();log('TIMEOUT');break
        code=proc.wait()
    (R/'solver.exit').write_text(str(code)+'\n');log(f'SOLVE_EXIT {code} reason={reason} seconds={time.time()-t0:.1f}')
    if code==0 and reason is None:
        (R/'solver_a.exit').write_text('exit=0\n');(R/'case_a').symlink_to(case,target_is_directory=True)
        shutil.copy2('/content/points_w_r7.json',R/'points_w_r7.json')
        script=Path('/content/extract_a_r10.py').read_text().replace("Path('/content/luw-aij-r10')",f"Path('{R}')")
        (R/'extract_city.py').write_text(script)
        with (R/'extract.log').open('w') as f:e=subprocess.run(['python3',str(R/'extract_city.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,timeout=900)
        log('EXTRACT '+str(e.returncode));assert e.returncode==0,(R/'extract.log').read_text()[-3000:]
        rows=json.loads((R/'offset_samples_a_r10.json').read_text())['rows'];assert len(rows)==80
        log('POINTS 80')
except Exception:
    log('ERROR '+traceback.format_exc()[-4000:]);(R/'error.txt').write_text(traceback.format_exc())
finally:(R/'all.done').write_text('terminal\n')
