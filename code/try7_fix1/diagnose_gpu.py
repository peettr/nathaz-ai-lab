#!/usr/bin/env python3
"""Synchronous paid-GPU diagnostic only; no production solves."""
import os, pathlib, hashlib, subprocess, tarfile, time, json, csv
R=pathlib.Path('/content'); out=R/'try7_fix1_diag';out.mkdir(exist_ok=False)
a=R/'try7_gate.tar.gz'
assert hashlib.sha256(a.read_bytes()).hexdigest()==os.environ['TRY7_ARCHIVE_SHA']
with tarfile.open(a) as t:
 for m in t.getmembers():
  assert (m.name=='FluidX3D_gate0' or m.name.startswith('FluidX3D_gate0/')) and '..' not in pathlib.Path(m.name).parts
  assert m.isdir() or m.isfile()
 t.extractall(out,filter='data')
src=out/'FluidX3D_gate0';man=json.loads((R/'try7_manifest.json').read_text())
for name,digest in man.items():
 p=src/'src'/name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,(name,'source mismatch')
print('SOURCE_VERIFIED',len(man),flush=True)
def run(argv,log,env=None):
 with (out/log).open('x') as f:
  p=subprocess.Popen(argv,cwd=src,stdout=f,stderr=subprocess.STDOUT,env=env)
  while p.poll() is None:
   print('HEARTBEAT',log,time.strftime('%H:%M:%S'),flush=True)
   time.sleep(20)
  print('EXIT',log,p.returncode,flush=True)
  assert p.returncode==0,(log,p.returncode)
run(['make','Linux','-j8'],'build.log')
binary=src/'bin/FluidX3D';env=dict(os.environ);env['LD_LIBRARY_PATH']=str(src/'src/OpenCL/lib')+':'+env.get('LD_LIBRARY_PATH','')
run([str(binary)],'wall.log',env)
source=R/'wall_gate0_opencl_source.cl';assert source.exists()
source.rename(out/'opencl_source.cl')
for old,new in [('wall_gate0.csv','wall_gate0.csv')]:
 (R/old).rename(out/new)
assert '#define WALL_GATE0_ALL' in (out/'opencl_source.cl').read_text()
run([str(binary)],'zero.log',{**env,'LUW_GATE_ZERO':'1'})
(R/'wall_gate0_zero.csv').rename(out/'wall_gate0_zero.csv')
with (out/'wall_gate0.csv').open() as f:rows=list(csv.DictReader(f))
with (out/'wall_gate0_zero.csv').open() as f:zeros=list(csv.DictReader(f))
for name,r in [('wall',rows),('zero',zeros)]:
 m=[float(x['mass']) for x in r];p=[float(x['px']) for x in r];fx=[float(x['wall_fx_sum']) for x in r]
 print('METRICS',name,'mass_rel_max',max(abs(x/m[0]-1) for x in m),'dpx',p[-1]-p[0],'sum_fx',sum(fx[1:]),'residual',(p[-1]-p[0])-sum(fx[1:]),flush=True)
print('DONE_DIAG',flush=True)
