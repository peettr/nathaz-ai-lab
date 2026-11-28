#!/usr/bin/env python3
"""Seven macro-variant syntax and OpenCL text-generation checks (no solver)."""
from pathlib import Path
import hashlib, json, subprocess
root=Path(__file__).resolve().parent
src=root/'stage/FluidX3D_on/src'
variants={
 'periodic_bounce':(True,False,False,False),
 'periodic_t4':(True,True,False,False),
 'periodic_t15_k2':(True,True,True,False),
 'periodic_t15_k3':(True,True,True,True),
 'legacy_off':(False,False,False,False),
 'legacy_on':(False,True,True,False),
 'legacy_k3':(False,True,True,True),
}
results={}
for name,(periodic,ground,second,k3) in variants.items():
    d=root/'preflight_seven_v3'/name
    d.mkdir(parents=True,exist_ok=False)
    defines=(src/'defines.hpp').read_text()
    for macro,enabled in (('PERIODIC_ABL_GROUND',periodic),('GROUND_WALL_MODEL',ground),('SECOND_LAYER_WM',second)):
        on='#define '+macro+' '
        off='//#define '+macro+' '
        if enabled and off in defines:defines=defines.replace(off,on,1)
        if not enabled and on in defines:defines=defines.replace(on,off,1)
        assert any(line.startswith(on) for line in defines.splitlines())==enabled,(name,macro)
    (d/'defines.hpp').write_text(defines)
    for fn in ('kernel.cpp','kernel.hpp'):(d/fn).write_bytes((src/fn).read_bytes())
    if k3:
        k=(d/'kernel.cpp').read_text()
        old='log((1.5f+def_ground_z0_lattice)/def_ground_z0_lattice)'
        assert old in k
        k=k.replace(old,'log((2.5f+def_ground_z0_lattice)/def_ground_z0_lattice)')
        # Archived k3 branch additionally changes the matching-layer sample.
        old='if(first==0u || first+1u>=def_Nz) { new_stress[col]=0.0f;new_stress[xy+col]=0.0f;return; }\n    const ulong a=(ulong)col+(ulong)first*(ulong)xy, b=a+(ulong)xy;'
        assert old in k
        k=k.replace(old,'if(first==0u || first+2u>=def_Nz) { new_stress[col]=0.0f;new_stress[xy+col]=0.0f;return; }\n    const ulong a=(ulong)col+(ulong)first*(ulong)xy, b=a+2ul*(ulong)xy;')
        (d/'kernel.cpp').write_text(k)
    include=['-I'+str(d),'-I'+str(src),'-I'+str(src/'OpenCL/include'),'-I'+str(src/'X11/include')]
    cmds={
      'kernel_host':['g++','-std=c++17','-fsyntax-only',*include,str(d/'kernel.cpp')],
      # setup/lbm.cpp resolve defines.hpp relative to their source directory;
      # -D confirms guards but does NOT override the original defines.hpp.
      'setup_host':['g++','-std=c++17','-fsyntax-only',*include,str(src/'setup.cpp')],
      'lbm_host':['g++','-std=c++17','-fsyntax-only',*include,str(src/'lbm.cpp')],
      'emitter':['g++','-std=c++17','-O0',*include,str(d/'kernel.cpp'),str(root/'emit_kernel.cpp'),'-o',str(d/'emit')]
    }
    item={'macro_configuration':{'periodic':periodic,'ground':ground,'second':second,'k3_variant':k3},'limits':'setup/lbm.cpp include adjacent defines.hpp; their g++ checks use staged default macros, not variant macros. OpenCL C compiler unavailable.'}
    for label,cmd in cmds.items():
        p=subprocess.run(cmd,text=True,capture_output=True)
        (d/(label+'.log')).write_text('command='+repr(cmd)+'\n'+p.stdout+p.stderr+'\nexit='+str(p.returncode)+'\n')
        item[label+'_exit']=p.returncode
        if p.returncode:break
    if item.get('emitter_exit')==0:
        p=subprocess.run([str(d/'emit'),str(d/'generated.cl')],capture_output=True,text=True)
        (d/'generation.log').write_text(p.stdout+p.stderr+'\nexit='+str(p.returncode)+'\n')
        item['generation_exit']=p.returncode
        if p.returncode==0:item['generated_sha256']=hashlib.sha256((d/'generated.cl').read_bytes()).hexdigest()
    results[name]=item
    print(name,item,flush=True)
(root/'SEVEN_PREFLIGHT.json').write_text(json.dumps(results,indent=2)+'\n')
if any(item.get('generation_exit')!=0 for item in results.values()):raise SystemExit(1)
