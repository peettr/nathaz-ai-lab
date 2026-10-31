from pathlib import Path
import tarfile,subprocess,time,traceback,json,struct,mmap,math,hashlib
R=Path('/content/c05k_gate_01');R.mkdir(exist_ok=False)
def log(s):
 with (R/'progress.log').open('a') as f:f.write(str(s)+'\n')
 print(s,flush=True)
try:
 with tarfile.open('/content/gate_inputs.tar.gz') as t:t.extractall(R,filter='data')
 defs=R/'FluidX3D/src/defines.hpp';s=defs.read_text();assert '//#define CITY_STABILITY_MONITOR' in s;defs.write_text(s.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
 with (R/'build.log').open('w') as f:ret=subprocess.run(['make','Linux','-j4'],cwd=R/'FluidX3D',stdout=f,stderr=subprocess.STDOUT,timeout=900)
 log('BUILD '+str(ret.returncode));assert ret.returncode==0,(R/'build.log').read_text()[-4000:]
 case=R/'case';start=time.monotonic(); trace=case/'RESULTS/city_stability.csv'
 with (R/'solver.log').open('w',buffering=1) as f:
  proc=subprocess.Popen([str(R/'FluidX3D/bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
  while proc.poll() is None:
   time.sleep(8)
   if trace.exists():
    with trace.open() as g:
     h=g.readline().strip().split(',');q=''
     for line in g:q=line
    if q:
     d=dict(zip(h,q.strip().split(',')));step=int(d['step'])
     if step%1000==0:log('STEP '+str(step))
     if d['first_nonfinite_xyz_component'] or float(d['max_u_lattice'])>.3 or (step>=3000 and (float(d['min_rho'])<.9 or float(d['max_rho'])>1.1)):
      proc.terminate();raise RuntimeError('monitor failure '+repr(d))
   if time.monotonic()-start>1800:proc.terminate();raise RuntimeError('gate timeout')
  code=proc.wait(timeout=60)
 (R/'solver.exit').write_text(str(code)+'\n');assert code==0,(R/'solver.log').read_text()[-2000:]
 vtk=list(case.glob('RESULTS/vtk/*_avg*.vtk'));assert len(vtk)==1,vtk
 v=vtk[0]
 with v.open('rb') as f:
  header=[]
  while True:
   line=f.readline().decode().strip();header.append(line)
   if line.startswith('LOOKUP_TABLE'):break
  off=f.tell()
 dims=list(map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]));org=list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:]));dx=float(next(x for x in header if x.startswith('SPACING')).split()[1]);n=math.prod(dims)
 with v.open('rb') as f:
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  pos=off+n*12; offsets={}
  for name,comp in [('rho_avg',1),('fluid',1),('tke',1),('speed_mean',1),('speed2_mean',1)]:
   tag=f'SCALARS {name} float {comp}\nLOOKUP_TABLE default\n'.encode();assert m[pos:pos+len(tag)]==tag,(name,m[pos:pos+80]);pos+=len(tag);offsets[name]=pos;pos+=n*comp*4
  rows=[]
  def vec(i,j,k):return struct.unpack_from('>fff',m,off+((k*dims[1]+j)*dims[0]+i)*12)
  def val(name,i,j,k):return struct.unpack_from('>f',m,offsets[name]+((k*dims[1]+j)*dims[0]+i)*4)[0]
  def interp(x,y,z):
   q=[(a-b)/dx for a,b in zip((x,y,z),org)];ids=[math.floor(a) for a in q];w=[a-b for a,b in zip(q,ids)];u=[0.,0.,0.];ke=0
   for c in range(8):
    i=ids[0]+(c&1);j=ids[1]+((c>>1)&1);k=ids[2]+((c>>2)&1);wt=math.prod(w[d] if c&(1<<d) else 1-w[d] for d in range(3));v3=vec(i,j,k)
    for d in range(3):u[d]+=wt*v3[d]
    ke+=wt*val('tke',i,j,k)
   return math.sqrt(sum(a*a for a in u)),ke
  for z in range(1,31):
   vals=[interp(5.,float(y),float(z)) for y in range(100,311,30)]
   rows.append({'z':z,'U_mps':sum(x[0] for x in vals)/len(vals),'k_m2s2':sum(x[1] for x in vals)/len(vals)})
  m.close()
 (R/'gate_profiles.json').write_text(json.dumps({'rows':rows,'steps':6000,'avg_steps':4000,'vtk_size':v.stat().st_size},indent=2))
 log('EXTRACT '+str(len(rows)))
except Exception:
 (R/'error.txt').write_text(traceback.format_exc());log(traceback.format_exc()[-4000:])
finally:(R/'all.done').write_text('done\n')
