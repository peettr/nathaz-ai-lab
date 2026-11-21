#!/usr/bin/env python3
"""Fail-closed static source, budget, and OpenCL checks; no solver execution."""
import hashlib,json,pathlib,subprocess,time
R=pathlib.Path(__file__).resolve().parent
P=R.parent/'continuation8b_20261119_0026'
F=['g++','-std=c++17','-pthread','-Isrc/OpenCL/include','-Wno-comment']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((R/'t15_manifest.json').read_text())
assert sha(R/'t15_stage.tar.gz')==m['archive_sha256']
for tree in ('off','on'):
 src=R/'stage'/('FluidX3D_'+tree)
 for n,h in m['sources'][tree].items():assert sha(src/'src'/n)==h
 log=R/f'gpp_{tree}_retry2.log'
 with log.open('x') as f:p=subprocess.run(F+['-fsyntax-only','src/kernel.cpp','src/lbm.cpp','src/setup.cpp'],cwd=src,stdout=f,stderr=subprocess.STDOUT)
 assert p.returncode==0,(tree,p.returncode)
 exe=R/('emit_retry2_'+tree)
 subprocess.run(F+['-Isrc',str(R/'emit_kernel.cpp'),'src/kernel.cpp','-o',str(exe)],cwd=src,check=True)
 out=R/f'{tree}_generated_retry2.cl';subprocess.run([str(exe),str(out)],check=True)
 generated=out.read_bytes()
 old=(P/f'{tree}_new_kernel_container.cl').read_bytes()
 assert generated==old,(tree,'generated OpenCL differs from frozen continuation8b')
 print('OPENCL_BYTE_EQUAL',tree,'new',sha(out),'old',sha(P/f'{tree}_new_kernel_container.cl'),'bytes',len(generated),flush=True)
 # The freeze includes four variants; syntax check only production off/on generated containers.
 c=R/'clang_local/usr/bin/clang-14'
 if c.exists():
  import os
  env={**os.environ,'LD_LIBRARY_PATH':str(R/'clang_local/usr/lib/llvm-14/lib')+':'+str(R/'clang_local/usr/lib/x86_64-linux-gnu')}
  cp=subprocess.run([str(c),'-x','cl','-cl-std=CL1.2','-fsyntax-only','-Wno-macro-redefined',str(R/f'{tree}_generated.cl')],env=env,capture_output=True,text=True)
  (R/f'clang_{tree}.log').write_text(cp.stdout+cp.stderr+f'\nexit={cp.returncode}\n')
  assert cp.returncode==0,(tree,cp.stderr[-1000:])
for seed in (107,108,109):
 n='dx1p0_s'+str(seed)
 assert sha(R/'stage'/n/'conf.luwpf')==m['cases'][n]
# conservative host-side cut, before a real allocation and again after native compilation.
rate=5.4;cap=6.75;cut_s=cap*3600/rate-180
solve=sum((1228.8467848300934,1221.9939720630646,1223.5972926616669))
compilation_and_upload_s=100;per_case_handoff_s=120;last_stop_s=100
margin=cut_s-solve-compilation_and_upload_s-3*per_case_handoff_s-last_stop_s
assert margin>0,margin
print('BUDGET_CUT_SECONDS',cut_s,'MEASURED_SOLVE_SECONDS',solve,'COMPILATION_UPLOAD_RESERVE',compilation_and_upload_s,'HANDOFF_RESERVE',3*per_case_handoff_s,'STOP_RESERVE',last_stop_s,'MARGIN_SECONDS',margin,flush=True)
print('STATIC_PREFLIGHT_PASS',flush=True)
