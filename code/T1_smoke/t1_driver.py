#!/usr/bin/env python3
"""Single submission, bounded LUW OpenCL H100 feasibility smoke."""
import hashlib, json, os, pathlib, re, shutil, subprocess, sys, tarfile, time
R = pathlib.Path(sys.argv[1]).resolve()
T = R / 'B2u_inputs.tar.gz'
assert T.is_file()
with tarfile.open(T) as tf:
    for m in tf.getmembers():
        p = (R / m.name).resolve()
        if not p.is_relative_to(R) or m.issym() or m.islnk():
            raise RuntimeError('unsafe tar member '+m.name)
    tf.extractall(R, filter='data')
base = R/'FluidX3D'
conf0=(R/'case/conf.luwpf').read_text()
assert conf0.count('run_nstep = 31000')==1 and conf0.count('n_gpu = [1, 1, 1]')==1
# Keep the actual physical deck except the smoke duration and disable the large VTK average.
conf0=conf0.replace('run_nstep = 31000','run_nstep = 2000').replace('purge_avg = 20000','purge_avg = 0')
assert 'run_nstep = 2000' in conf0
src=base/'src/defines.hpp'
def0=src.read_text()
assert def0.count('//#define CITY_STABILITY_MONITOR')==1
result={'input_tar_sha256':hashlib.sha256(T.read_bytes()).hexdigest(), 'variants':{}, 'started':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
def save(): (R/'result.json').write_text(json.dumps(result, indent=2))
def run(argv, cwd, out, timeout):
    t=time.monotonic()
    with open(out,'w') as f:
        try:
            p=subprocess.run(argv,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=timeout,env={**os.environ,'LD_LIBRARY_PATH':str(base/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')})
            return p.returncode, time.monotonic()-t
        except subprocess.TimeoutExpired:
            f.write('\nTIMEOUT\n');return 124,time.monotonic()-t
for count in (1,4):
    name=f'gpu{count}'
    d=R/name; d.mkdir(exist_ok=False)
    (d/'wind_bc').mkdir(); (d/'proj_temp').mkdir()
    shutil.copy(R/'case/wind_bc/profile.dat',d/'wind_bc/profile.dat')
    shutil.copy(R/'case/proj_temp/CaseE_PF.stl',d/'proj_temp/CaseE_PF.stl')
    c=conf0.replace('n_gpu = [1, 1, 1]',f'n_gpu = [{count}, 1, 1]')
    (d/'conf.luwpf').write_text(c)
    # Native city monitor uses a single subdomain. Four-card run uses solver progress only.
    src.write_text(def0.replace('//#define CITY_STABILITY_MONITOR',('#define CITY_STABILITY_MONITOR' if count==1 else '//#define CITY_STABILITY_MONITOR')))
    try:
        p=subprocess.run(['make','Linux','-j8'],cwd=base,stdout=open(d/'build.log','w'),stderr=subprocess.STDOUT,timeout=400,stdin=subprocess.DEVNULL)
        brc=p.returncode
    except subprocess.TimeoutExpired: brc=124
    if brc: result['variants'][name]={'build_exit':brc};save();break
    t=time.monotonic()
    rc,sec=run([str(base/'bin/FluidX3D'),str(d/'conf.luwpf')],d,d/'solver.log',950 if count==1 else 950)
    trace=d/'RESULTS/city_stability.csv'
    result['variants'][name]={'build_exit':brc,'solver_exit':rc,'wall_seconds':sec,'trace':str(trace) if trace.exists() else None,'trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest() if trace.exists() else None,'deck_sha256':hashlib.sha256(c.encode()).hexdigest()}
    save()
    if rc: break
result['finished']=time.strftime('%Y-%m-%dT%H:%M:%S%z');save()
print('RESULT',json.dumps(result),flush=True)
