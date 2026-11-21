#!/usr/bin/env python3
"""Colab-only, isolated production-path compile and short smoke."""
from pathlib import Path
import csv, hashlib, json, os, subprocess, tarfile, traceback
R=Path('/content'); OUT=R/'try13_main_smoke'; ROOT=R/'stage_t4'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 OUT.mkdir(exist_ok=False)
 archive=R/'try13_main_stage.tar.gz'; manifest=json.loads((R/'try13_main_archive.json').read_text())
 assert sha(archive)==manifest['archive_sha256']
 with tarfile.open(archive) as tar:
  for m in tar.getmembers():
   assert (m.name=='stage_t4' or m.name.startswith('stage_t4/')) and '..' not in Path(m.name).parts and (m.isfile() or m.isdir()),m.name
  assert not ROOT.exists()
  tar.extractall(R,filter='data')
 expected=json.loads((ROOT/'try13_source_manifest.json').read_text())
 for name,digest in expected.items():assert sha(ROOT/'FluidX3D_on/src'/name)==digest,name
 print('MAIN_SOURCE_VERIFIED',expected,flush=True)
 src=ROOT/'FluidX3D_on';env={**os.environ,'LUW_CAPTURE_CL':str(OUT/'actual_opencl.cl'),'LUW_GROUND_TAU_START':'0','LD_LIBRARY_PATH':str(src/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
 with (OUT/'build.log').open('x') as f:
  rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=900).returncode
 print('BUILD_EXIT',rc,flush=True)
 if rc:raise RuntimeError('build failed')
 base=ROOT/'smoke';conf=base/'conf.luwpf'; assert sha(conf)==json.loads((ROOT/'manifest.json').read_text())['smoke_conf_sha256']
 with (OUT/'solver.log').open('x') as f:
  rc=subprocess.run([str(src/'bin/FluidX3D'),str(conf)],cwd=base,env=env,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=1800).returncode
 print('SOLVER_EXIT',rc,flush=True)
 if rc:raise RuntimeError('solver failed')
 cl=OUT/'actual_opencl.cl';text=cl.read_text()
 for marker in ('ground_initialize_incoming','flat_ground_eligible','GROUND_WALL_MODEL','ground_tau_count'):
  assert marker in text,marker
 assert 'WALL_GATE0_ALL' not in text
 results=base/'RESULTS';tau=results/'wall_tau_actual.csv';stability=results/'city_stability.csv';eligible=results/'ground_eligibility.csv'
 for p in (tau,stability,eligible):assert p.is_file() and p.stat().st_size>100,p
 import shutil
 for p in (tau,stability,eligible):shutil.copyfile(p,OUT/p.name)
 with tau.open() as f: rows=list(csv.DictReader(f))
 valid=[r for r in rows if float(r['count'])>0]
 assert valid,'zero tau samples'
 with stability.open() as f:trace=list(csv.DictReader(f))
 with eligible.open() as f: e=list(csv.DictReader(f))
 assert len(e)==1 and int(e[0]['measured'])>0,e
 metrics={'solver_exit':rc,'valid_tau_columns':len(valid),'tau_over_rho_lattice_minmax':[min(float(r['tau_abs_over_rho_lattice']) for r in valid),max(float(r['tau_abs_over_rho_lattice']) for r in valid)],'ustar_mps_minmax':[min(float(r['ustar_mps']) for r in valid),max(float(r['ustar_mps']) for r in valid)],'mass_fluid_first_last':[trace[0]['mass_fluid'],trace[-1]['mass_fluid']],'monitor_rows':len(trace),'host_eligible':e[0],'actual_opencl_sha256':sha(cl),'source_sha256':expected}
 (OUT/'gate.json').write_text(json.dumps(metrics,indent=2)+'\n')
 print('MAIN_SMOKE_GATE',json.dumps(metrics),flush=True)
 (OUT/'run.done').write_text('complete\n')
if __name__=='__main__':
 try:main()
 except BaseException:
  OUT.mkdir(exist_ok=True)
  (OUT/'run.failed').write_text(traceback.format_exc())
  traceback.print_exc()
  raise
