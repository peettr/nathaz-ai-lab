"""Compile clean HEAD and model-disabled copy with the same test-only setup."""
import pathlib,tarfile,subprocess,time,json
root=pathlib.Path('/content/luw_wall_headparity');root.mkdir(exist_ok=False)
rows=[]
for name,archive in [('HEAD','/content/solver_gate0_HEAD_r13.tar.gz'),('switch_off','/content/solver_gate0_swap_warm_r13.tar.gz')]:
    target=root/name;target.mkdir()
    with tarfile.open(archive) as tar:tar.extractall(target,filter='data')
    source=target/'FluidX3D';defs=source/'src/defines.hpp'
    text=defs.read_text().replace('#define FP16C','//#define FP16C')
    if name=='HEAD':
        test_setup=(root/'switch_off/FluidX3D/src/setup.cpp').read_text() if (root/'switch_off/FluidX3D/src/setup.cpp').exists() else None
        # HEAD is processed first; extract gate fixture from the second archive without modifying it.
        with tarfile.open('/content/solver_gate0_swap_warm_r13.tar.gz') as t:
            member=t.extractfile('FluidX3D/src/setup.cpp');test_setup=member.read().decode()
        prefix=test_setup.split('#ifdef WALL_GATE0\nvoid main_setup()',1)[1].split('#else\nvoid main_setup()',1)[0]
        setup=source/'src/setup.cpp';original=setup.read_text();assert original.count('void main_setup()')==1
        original=original.replace('void main_setup()', '#ifdef WALL_GATE0\nvoid main_setup()'+prefix+'#else\nvoid main_setup()',1)+'\n#endif // WALL_GATE0\n'
        setup.write_text(original)
        text+='\n#define WALL_GATE0\n'
    else:text=text.replace('//#define WALL_GATE0','#define WALL_GATE0')
    defs.write_text(text)
    log=target/'build_and_run.log';start=time.monotonic()
    with log.open('w') as out:
        cp=subprocess.run(['make','Linux','-j4'],cwd=source,stdout=out,stderr=subprocess.STDOUT,timeout=300)
        if cp.returncode==0:cp=subprocess.run(['bin/FluidX3D'],cwd=source,stdout=out,stderr=subprocess.STDOUT,timeout=180)
    rows.append({'variant':name,'exit':cp.returncode,'wall_s':time.monotonic()-start,'log':str(log)})
    print(rows[-1],flush=True)
    if cp.returncode:break
(root/'results.json').write_text(json.dumps(rows,indent=2))
