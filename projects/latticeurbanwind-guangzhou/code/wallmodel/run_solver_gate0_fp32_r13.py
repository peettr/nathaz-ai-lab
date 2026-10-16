"""Isolated solver gate diagnostics: FP32, both-wall slip, constant known test force."""
import os,pathlib,subprocess,tarfile,json,time
archive=pathlib.Path(os.environ.get('GATE0_ARCHIVE','/content/solver_gate0_swap_top_r13.tar.gz'))
root=pathlib.Path(os.environ.get('GATE0_ROOT','/content/luw_wall_gate0_fp32'));root.mkdir(exist_ok=False)
rows=[]
variants=[('head_path',False,False),('mirror_zero',True,False),('mirror_constforce',True,True)]
if os.environ.get('GATE0_PROBE')=='1':variants=[('mirror_probe',True,True)]
for name,model,force in variants:
    target=root/name;target.mkdir()
    with tarfile.open(archive) as tar: tar.extractall(target,filter='data')
    source=target/'FluidX3D';defines=source/'src/defines.hpp'
    text=defines.read_text().replace('#define FP16C','//#define FP16C')
    text=text.replace('//#define WALL_GATE0','#define WALL_GATE0')
    if model:text=text.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL')
    defines.write_text(text)
    if os.environ.get('GATE0_DYNAMIC')!='1':
        kernel=source/'src/kernel.cpp'
        text=kernel.read_text()
        old='const float tau=rhon*sq(def_ground_kappa*um/logwall);'
        assert text.count(old)==1
        text=text.replace(old,'const float tau='+('0.00005f' if force else '0.0f')+'; // gate-only fixed wall forcing')
        kernel.write_text(text)
    elif model and not force:
        kernel=source/'src/kernel.cpp';text=kernel.read_text()
        old='const float tau=rhon*sq(def_ground_kappa*um/logwall);';assert text.count(old)==1
        kernel.write_text(text.replace(old,'const float tau=0.0f; // gate-only zero force'))
    if os.environ.get('GATE0_PROBE')=='1' and model:
        kernel=source/'src/kernel.cpp';text=kernel.read_text()
        old='ground_force[n]=applied_ground_fx;';assert text.count(old)==1
        kernel.write_text(text.replace(old,'ground_force[n]=ground_first_fluid ? 1234.0f : 0.0f;'))
    log=target/'build_and_run.log';start=time.monotonic()
    with log.open('w') as out:
        cp=subprocess.run(['make','Linux','-j4'],cwd=source,stdout=out,stderr=subprocess.STDOUT,timeout=300)
        if cp.returncode==0: cp=subprocess.run(['bin/FluidX3D'],cwd=source,stdout=out,stderr=subprocess.STDOUT,timeout=180)
    rows.append({'variant':name,'exit':cp.returncode,'wall_s':time.monotonic()-start,'log':str(log)})
    print(rows[-1],flush=True)
    if cp.returncode:break
(root/'results.json').write_text(json.dumps(rows,indent=2))
