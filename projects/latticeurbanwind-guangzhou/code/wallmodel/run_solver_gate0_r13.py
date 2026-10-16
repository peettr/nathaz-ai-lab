"""Run actual LUW kernel in three isolated OpenCL channel builds; no city simulation."""
import os, pathlib, subprocess, tarfile, shutil, json, time
root=pathlib.Path(os.environ.get('GATE0_ROOT','/content/luw_wall_gate0_r13'))
root.mkdir(exist_ok=True)
archive=pathlib.Path(os.environ.get('GATE0_ARCHIVE','/content/solver_gate0_r13.tar.gz'))
assert archive.exists()
results=[]
for name,model,force in [('head_path',False,False),('mirror_zero',True,False),('mirror_force',True,True)]:
    target=root/name
    assert not target.exists(), f'refusing overwrite {target}'
    target.mkdir()
    with tarfile.open(archive) as tar: tar.extractall(target,filter='data')
    source=target/'FluidX3D'
    defines=source/'src/defines.hpp'
    code=defines.read_text().replace('//#define WALL_GATE0','\n#define WALL_GATE0')
    if model: code=code.replace('//#define GROUND_WALL_MODEL','\n#define GROUND_WALL_MODEL')
    defines.write_text(code)
    if model and not force:
        kernel=source/'src/kernel.cpp'
        text=kernel.read_text()
        old='const float tau=rhon*sq(def_ground_kappa*um/logwall);'
        assert text.count(old)==1
        kernel.write_text(text.replace(old,'const float tau=0.0f*rhon*sq(def_ground_kappa*um/logwall);'))
    log=target/'build_and_run.log'
    with log.open('w') as output:
        start=time.monotonic()
        cp=subprocess.run(['make','Linux','-j4'],cwd=source,stdout=output,stderr=subprocess.STDOUT,timeout=300)
        output.flush()
        if cp.returncode==0:
            cp=subprocess.run(['bin/FluidX3D'],cwd=source,stdout=output,stderr=subprocess.STDOUT,timeout=180)
        row={'variant':name,'exit':cp.returncode,'wall_s':round(time.monotonic()-start,2),'log':str(log)}
        results.append(row)
        print(row,flush=True)
        if cp.returncode: break
(root/'results.json').write_text(json.dumps(results,indent=2))
print('GATE0_DONE',flush=True)
