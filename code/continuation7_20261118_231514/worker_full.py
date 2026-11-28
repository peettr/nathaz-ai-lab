#!/usr/bin/env python3
"""Fail-closed T15 continuation: compile every variant -> E3 -> three seeds -> k3."""
import argparse,csv,gzip,hashlib,json,os,pathlib,shutil,subprocess,tarfile,time,traceback
import numpy as np
from remote_worker_run2 import vtk_map
CASES=(('E3_native','e3',107),)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seal(p):
 h=sha(p);(p.parent/(p.name+'.sha256')).write_text(h+'\n');print('READY',p.name,h,flush=True)
def run(content,stub):
 budget=json.loads((content/'t15_budget.json').read_text());fixture=budget['mode']=='fixture';deadline=budget['work_deadline']
 if bool(stub)!=fixture or (fixture and content==pathlib.Path('/content')):raise ValueError('stub only in isolated fixture')
 arc=content/'t15_stage.tar.gz';man=json.loads((content/'t15_manifest.json').read_text())
 if sha(arc)!=man['archive_sha256']:raise ValueError('archive SHA mismatch')
 o=content/'t15/out';o.mkdir(parents=True,exist_ok=False)
 try:
  with tarfile.open(arc) as t:
   for m in t:
    p=pathlib.PurePosixPath(m.name)
    if not p.parts or p.parts[0]!='stage' or '..' in p.parts or not(m.isfile() or m.isdir()):raise ValueError('unsafe archive member')
   t.extractall(content/'t15',filter='data')
  stage=content/'t15/stage';exes={}
  for tree in ('off','e3','on','k3'):
   src=stage/('FluidX3D_'+tree)
   for n,h in man['sources'][tree].items():
    if sha(src/'src'/n)!=h:raise ValueError('source mismatch '+tree+'/'+n)
   build=o/(tree+'_build.log')
   with build.open('x') as f:rc=subprocess.run(['make','Linux','-j8'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=900).returncode
   seal(build)
   if rc:raise RuntimeError('build failed '+tree)
   exe=src/'bin/FluidX3D'
   if not exe.is_file():raise ValueError('solver absent '+tree)
   if stub:shutil.copyfile(stub,exe);exe.chmod(0o755)
   exes[tree]=exe
  # Each real solver constructs its actual GPU program then exits before step zero.
  # The fixture can only verify the ordering and handoff, not native GPU compilation.
  for tree in ('off','on','e3','k3'):
   cfg=content/'t15'/('precompile_'+tree);shutil.copytree(stage/'dx1p0_s107',cfg)
   log=o/(tree+'_gpu_compile.log')
   env={**os.environ,'LUW_COMPILE_ONLY':'1','LD_LIBRARY_PATH':str(stage/('FluidX3D_'+tree)/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
   with log.open('x') as f:rc=subprocess.run([str(exes[tree]),str(cfg/'conf.luwpf')],cwd=cfg,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180 if fixture else min(900,max(1,deadline-time.time()-240))).returncode
   seal(log)
   if rc or (not fixture and ('T15 COMPILE_ONLY PASS '+tree) not in log.read_text(errors='replace')):
    raise RuntimeError('GPU compile gate failed '+tree)
  for label,tree,seed in CASES:
   remaining=deadline-time.time();reserve=360
   print('E3_BUDGET remaining_s',remaining,'reserve_s',reserve,'margin_s',remaining-reserve,flush=True)
   if remaining<=reserve:raise TimeoutError('budget cutoff '+label)
   case='dx1p0_s'+str(seed);base=content/'t15'/('case_'+label);shutil.copytree(stage/case,base)
   cfg=base/'conf.luwpf'
   if sha(cfg)!=man['cases'][case]:raise ValueError('config SHA mismatch '+case)
   cl=o/(label+'_actual_opencl.cl');env={**os.environ,'LUW_CAPTURE_CL':str(cl),'LUW_GROUND_MIX_A':'0',
        'LD_LIBRARY_PATH':str(stage/('FluidX3D_'+tree)/'src/OpenCL/lib')+':'+os.environ.get('LD_LIBRARY_PATH','')}
   log=o/(label+'_solver.log');start=time.time()
   with log.open('x') as f:rc=subprocess.run([str(exes[tree]),str(cfg)],cwd=base,env=env,stdout=f,stderr=subprocess.STDOUT,
                       timeout=180 if fixture else min(300,max(1,deadline-time.time()-60))).returncode
   exitfile=o/(label+'_exit.json');exitfile.write_text(json.dumps({'solver_exit':rc,'elapsed_s':time.time()-start})+'\n')
   for f in (log,exitfile):seal(f)
   if rc:
    if label=='E3_native':
     failed_csv=(content if fixture else pathlib.Path('/content'))/'t15_e3_force_tau.csv'
     if failed_csv.is_file():
      failed_copy=o/'E3_native_FAILED_native_e3.csv';shutil.copyfile(failed_csv,failed_copy);seal(failed_copy)
    raise RuntimeError('solver failed '+label)
   sources=[(log,'solver.log'),(exitfile,'exit.json')]
   if label=='E3_native':sources += [(o/(variant+'_gpu_compile.log'),variant+'_gpu_compile.log') for variant in ('off','on','e3','k3')]
   if label=='E3_native':
    e3=(content if fixture else pathlib.Path('/content'))/'t15_e3_force_tau.csv'
    evolution=(content if fixture else pathlib.Path('/content'))/'t15_e3_evolution.csv'
    top=(content if fixture else pathlib.Path('/content'))/'t15_e3_top_shear.csv'
    if not e3.exists() or not evolution.exists() or not top.exists():raise RuntimeError('native GPU E3-prime records/top evidence absent')
    compare=o/'E3_prime_replay.csv'
    verdict=subprocess.run([os.sys.executable,str(content/'assert_e3prime.py'),str(e3),str(evolution),'--top',str(top),'--comparison',str(compare)],capture_output=True,text=True)
    gate=o/'E3_native_gate.json';gate.write_text(verdict.stdout);seal(gate)
    sources.append((gate,'gate.json'))
    for src,suffix in ((e3,'native_e3.csv.gz'),(evolution,'evolution.csv.gz'),(top,'top_shear.csv.gz'),(compare,'replay.csv.gz')):
     if not src.is_file():raise RuntimeError('E3-prime file missing '+suffix)
     compressed=o/('E3_native_'+suffix)
     with src.open('rb') as fin,gzip.open(compressed,'xb',compresslevel=5) as fout:shutil.copyfileobj(fin,fout)
     seal(compressed);sources.append((compressed,suffix))
    gate_failed=verdict.returncode!=0
   else:
    vtks=list((base/'RESULTS/vtk').glob('*_avg-*.vtk'))
    if len(vtks)!=1:raise RuntimeError('missing/ambiguous mean VTK '+label)
    v=vtk_map(vtks[0]);u=np.asarray(v['fields']['u_avg'],dtype='<f4');fluid=np.asarray(v['fields']['fluid'],dtype='<f4')
    k0=round(-v['origin'][2]/v['spacing'][2]);k1=k0+(5 if fixture else 28)
    if u.shape[0]<k1 or (not fixture and (u.shape[1:3]!=(100,550) or fluid.shape[1:3]!=(100,550))):raise ValueError('VTK extent')
    thin=o/(label+'_thin.npz')
    with thin.open('xb') as f:np.savez_compressed(f,u_avg=u[k0:k1],fluid=fluid[k0:k1],metadata=json.dumps({'origin':v['origin'],'spacing':v['spacing'],'k_start':k0,'vtk_sha256':sha(vtks[0])}))
    seal(thin);sources.append((thin,'thin.npz'))
    upper_start=k0+28;upper_end=upper_start+6
    if u.shape[0]<upper_end:raise ValueError('upper profile height not exported '+label)
    upper=o/(label+'_profile_upper.npz')
    with upper.open('xb') as f:np.savez_compressed(f,u_avg=u[upper_start:upper_end],fluid=fluid[upper_start:upper_end],metadata=json.dumps({'origin':v['origin'],'spacing':v['spacing'],'k_start':upper_start,'vtk_sha256':sha(vtks[0])}))
    seal(upper);sources.append((upper,'profile_upper.npz'))
    if label=='E2_off_s107':
     ref=content/'t15_reference.npz'
     with np.load(ref,allow_pickle=False) as r:
      if not(np.array_equal(u[k0:k1],r['u_avg']) and np.array_equal(fluid[k0:k1],r['fluid'])):raise RuntimeError('E2 BITWISE FAIL')
     gate=o/'E2_bitwise.json';gate.write_text(json.dumps({'status':'PASS','reference_sha256':sha(ref),'u_elements':int(u[k0:k1].size),'fluid_elements':int(fluid[k0:k1].size)})+'\n');seal(gate);sources.append((gate,'bitwise.json'))
    if tree in ('on','k3'):
     for n in ('wall_tau_actual.csv','t3d_geometry_gate.csv'):
      f=base/'RESULTS'/n
      if not f.is_file():raise RuntimeError('native diagnostic absent '+label+'/'+n)
      sources.append((f,n))
   if not cl.is_file():raise RuntimeError('actual OpenCL absent '+label)
   sources.append((cl,'actual_opencl.cl'))
   hashes={}
   for src,suffix in sources:
    name=label+'_'+suffix;dst=o/name
    if src!=dst:
     shutil.copyfile(src,dst)
    if not (dst.parent/(dst.name+'.sha256')).exists():seal(dst)
    hashes[name]=sha(dst)
   hand=o/(label+'_handoff.json');hand.write_text(json.dumps({'sha256':hashes},sort_keys=True)+'\n');seal(hand)
   ack=o/(label+'.ack.json')
   while not ack.exists():
    if time.time()+20>deadline:raise TimeoutError('host ACK '+label)
    time.sleep(.1 if fixture else 2)
   if json.loads(ack.read_text())!=hashes:raise RuntimeError('ACK mismatch '+label)
   print('HOST_VERIFIED',label,flush=True)
   if label=='E3_native' and gate_failed:raise RuntimeError('E3-prime gate failed after verified handoff')
  done=o/'run.done';done.write_text(json.dumps({'verified_cases':[x[0] for x in CASES],'mode':budget['mode']})+'\n');seal(done)
 except BaseException:
  failure=o/'run.failed';failure.write_text(traceback.format_exc());seal(failure);raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--content',type=pathlib.Path,default=pathlib.Path('/content'));p.add_argument('--stub',type=pathlib.Path)
 a=p.parse_args();run(a.content.resolve(),a.stub.resolve() if a.stub else None)
