#!/usr/bin/env python3
"""Freeze a T13 source overlay and adapt the verified T11 transport in a fresh root."""
import pathlib, shutil, hashlib, json, difflib, re, subprocess, datetime
BASE=pathlib.Path(__file__).resolve().parent
P=BASE.parent/'R21.4a_T11_inflow_boost/run2_20261117_234908'
T5=BASE.parent/'R21.4a_T5_caseE_WM_retry1/stage/FluidX3D_off/src'
R=BASE/('run_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
R.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(n,text): (R/n).write_text(text)
def change(s,old,new):
 assert s.count(old)==1,(old,s.count(old))
 return s.replace(old,new)
for n in ['stage_t5.tar.gz','archive.json','B2u_reference_points.json','comparison.json','t5_sampling.py','remote_worker_run2.py','dry_stub.py','machine.py']:
 shutil.copyfile(P/n,R/n)
old=(T5/'kernel.cpp').read_text()
line='\t\tw = 2.0f/(tau0+sqrt(sq(tau0)+0.76421222f*sgs_length_factor*sqrt(Q)/rhon)); // 0.76421222 = 18*sqrt(2)*(C*Delta)^2'
assert old.count(line)==1
new=change(old,line,')\n#ifdef SMAG_CS_010\n+R(\n'+line.replace('0.76421222f*sgs_length_factor','0.2553f*sgs_length_factor')+'\n)+\n#else\n+R(\n'+line+'\n)+\n#endif\nR(')
new='#include "defines.hpp"\n'+new
put('kernel_t13.cpp',new)
put('kernel.diff',''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='T5/kernel.cpp',tofile='T13/kernel.cpp')))
put('kernel_manifest.json',json.dumps({'base_sha256':sha(T5/'kernel.cpp'),'sha256':sha(R/'kernel_t13.cpp')},indent=2)+'\n')
# Keep the baseline package byte-identical and overlay only kernel.cpp.
for n in ['controller.py','remote_io.py','worker.py','injected_dry.py','analyze_t11.py']:
 s=(P/n).read_text()
 s=s.replace('t11','t13').replace('T11','T13')
 if n=='controller.py':
  s=change(s,"'setup_t13.cpp','setup_manifest.json'","'kernel_t13.cpp','kernel_manifest.json'")
  s=change(s,"PRODUCTS=('solver.log','actual_opencl.cl','points80.json','upstream_slice.npz','profile.json','exit.json')","PRODUCTS=('solver.log','actual_opencl.cl','points80.json','exit.json')")
  s=change(s,"if label==CASES[0]:names.add('build.log')","if label==CASES[0]:names.add('build.log')")
  a=s.index('    with np.load(o/f\'{label}_upstream_slice.npz\') as n:')
  b=s.index("    text=(o/f'{label}_solver.log')",a)
  s=s[:a]+s[b:]
  s=change(s,"    import numpy as np\n",'')
  s=change(s,"    if mode=='production' and ('NVIDIA A100-SXM4-40GB' not in text or '31000' not in text):raise ValueError('solver device/steps')","    if mode=='production' and ('NVIDIA A100-SXM4-40GB' not in text or '31000' not in text):raise ValueError('solver device/steps')\n    if mode=='production' and (re.search(r'(?i)\\bnan\\b',text) or 'CITY_STABILITY_MONITOR ALERT' in text):raise ValueError('stability log gate')")
  s=change(s,"frozen=json.loads((R/'PREFLIGHT_v2.ok').read_text());assert (set(PAYLOAD)-{PAYLOAD[-1]}|{'controller.py','machine.py'})<=frozen.keys()","frozen=json.loads((R/'PREFLIGHT.ok').read_text());assert (set(PAYLOAD)-{PAYLOAD[-1]}|{'controller.py','machine.py'})<=frozen.keys()")
  s=change(s,'if cut-time.time()<2*2520:','if cut-time.time()<2*2520:') if False else s
  s=change(s,"'--max-hours','3'","'--max-hours','3'")
 if n=='worker.py':
  s=change(s,'from remote_worker_run2 import vtk_map\nfrom t5_sampling import write_points\n','from remote_worker_run2 import vtk_map\nfrom t5_sampling import write_points\n')
  s=change(s,"PRODUCTS=('points80.json','upstream_slice.npz','profile.json','solver.log','actual_opencl.cl','exit.json')","PRODUCTS=('points80.json','solver.log','actual_opencl.cl','exit.json')")
  s=change(s,"BASE_SETUP='ce1a1a71bc34be8933d8494a3e7512481a0f3a958c08cb79c20fc31c1e5eeb90'","BASE_KERNEL='"+sha(T5/'kernel.cpp')+"'")
  a=s.index('def profile(');b=s.index('def main(',a);s=s[:a]+s[b:]
  s=change(s,"setup=src/'src/setup.cpp'","kernel=src/'src/kernel.cpp'")
  s=change(s,"assert sha(setup)==BASE_SETUP","assert sha(kernel)==BASE_KERNEL")
  s=change(s,"patch=c/'setup_t13.cpp';assert sha(patch)==json.loads((c/'setup_manifest.json').read_text())['sha256']\n  shutil.copyfile(patch,setup)","patch=c/'kernel_t13.cpp';assert sha(patch)==json.loads((c/'kernel_manifest.json').read_text())['sha256']\n  shutil.copyfile(patch,kernel)\n  defines=src/'src/defines.hpp'; d=defines.read_text(); assert 'SMAG_CS_010' not in d\n  defines.write_text(d+'\\n#define SMAG_CS_010\\n')")
  s=change(s,"   profile(v,obs,case,src,cfg,vtk[0],o)\n   for suffix in ('upstream_slice.npz','profile.json'):seal(o/(case+'_'+suffix))\n",'')
  s=change(s,"  obs=json.loads((c/'comparison.json').read_text());assert len(obs['rows'])==6\n",'')
 if n=='injected_dry.py':
  s=change(s,"'t13_budget.json'","'t13_budget.json'") if False else s
  s=re.sub(r"\n\s*assert len\(json.loads\(\(out/\(label\+'_profile.json'\)\).*?\n",'\n',s)
  s=re.sub(r"\n\s*assert \(out/\(label\+'_upstream_slice.npz'\)\).stat\(\).st_size>100",'',s)
 put(n,s)
put('PATH_PAYLOAD_MAP.md','PAYLOAD-only: stage_t5.tar.gz -> /content/stage_t5.tar.gz -> extracted stage; archive.json checks archive; kernel_t13.cpp and kernel_manifest.json overlay extracted src/kernel.cpp; B2u_reference_points.json supplies 80 points; remote_worker_run2.py and t5_sampling.py provide VTK decoding and point sampling; worker.py executes real build and solver; remote_io.py supplies launch, probe and ACK; t13_budget.json created from allocation clock. Outputs /content/t13/out/<case>_{points80.json,solver.log,actual_opencl.cl,exit.json} and same-name .sha256; build.log and per-case handoff; VTK stays remote. dry_stub.py is fixture-only, not PAYLOAD.\n')
print(R)
