"""Case A R21.6-0b: independent Colab root, four sequential mesh-only runs."""
from pathlib import Path
import subprocess, shutil, time, json, math, mmap, struct, itertools, hashlib, traceback
ROOT=Path('/content/r216_caseA_0b'); OUT=ROOT/'out'; OUT.mkdir(parents=True,exist_ok=True)
OBS=json.loads(Path('/content/caseA_observations_official.json').read_text())
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def log(s):
 with (ROOT/'run.log').open('a',buffering=1) as f:f.write(time.strftime('%Y-%m-%d %H:%M:%S %z ')+str(s)+'\n')
 print(s,flush=True)
def prepare(repo,dx,mode):
 name=f'{mode}_dx{dx:g}'; c=ROOT/name
 assert not c.exists(); (c/'proj_temp').mkdir(parents=True);(c/'wind_bc').mkdir()
 shutil.copy2('/content/CaseA_PF_caseA.stl',c/'proj_temp/CaseA_PF.stl');shutil.copy2('/content/profile_caseA.dat',c/'wind_bc/profile.dat')
 txt=(repo/'examples/example_ProfileResearch_noDEM/conf.luwpf').read_text()
 changes=[('casename = CaseE','casename = CaseA'),('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 1088.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 704.000000]'),('si_z_cfd = [0.000000, 270.000000]','si_z_cfd = [0.000000, 384.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n',f'cell_size = {dx:.1f}\n'),('angle = [0, 90, 180, 270]','angle = [270]')]
 for a,b in changes:
  assert txt.count(a)==1,(a,txt.count(a));txt=txt.replace(a,b)
 # dt is dx*0.1/U_ref, so equal physical duration needs 2/dx times the reference steps.
 steps=round(32000*2/dx); avg=round(22000*2/dx); stride=max(1,round(40*2/dx))
 txt+=f'\nrun_nstep = {steps}\npurge_avg = {avg}\npurge_avg_stride = {stride}\noutput_tke_ti_tls = [tke]\n'
 if mode=='r9':txt+='\nvk_inlet_ti = 0.1468030617\nvk_inlet_l = 100.0\nvk_inlet_inflow_only = true\nvk_inlet_face_mode = TARGET_INFLOW\n'
 (c/'conf.luwpf').write_text(txt)
 return name,c,steps,avg,stride
def extract(case,name,dx):
 files=list(case.glob('RESULTS/vtk/*_avg*.vtk'));assert len(files)==1,files
 vtk=files[0]
 with vtk.open('rb') as f:
  head=[]
  for _ in range(25):
   s=f.readline().decode('ascii','replace').strip();head.append(s)
   if s.startswith('LOOKUP_TABLE'):break
  offset=f.tell()
 assert head[-2].startswith('SCALARS u_avg'),head
 nx,ny,nz=map(int,next(s for s in head if s.startswith('DIMENSIONS')).split()[1:]);origin=list(map(float,next(s for s in head if s.startswith('ORIGIN')).split()[1:])); spacing=float(next(s for s in head if s.startswith('SPACING')).split()[1]);assert abs(dx-spacing)<.01
 N=nx*ny*nz
 with vtk.open('rb') as f:
  m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def off(start,field,components):
   tag=f'SCALARS {field} float {components}\nLOOKUP_TABLE default\n'.encode();assert m[start:start+len(tag)]==tag,(field,start,m[start:start+70]);return start+len(tag)
  rho=off(offset+N*12,'rho_avg',1);fluid=off(rho+N*4,'fluid',1);tk=off(fluid+N*4,'tke',1);assert tk+N*4==len(m)
  def scalar(o,i,j,k):return struct.unpack_from('>f',m,o+((k*ny+j)*nx+i)*4)[0]
  def vec(i,j,k):return struct.unpack_from('>fff',m,offset+((k*ny+j)*nx+i)*12)
  def interp(x,y,z):
   frac=[(a-b)/spacing for a,b in zip((x,y,z),origin)];ids=[math.floor(v) for v in frac];weights=[v-i for v,i in zip(frac,ids)]
   # Preserve every low-plane point; below first grid-center, clamp to first layer and flag extrapolation.
   low=frac[2]<0; weights[2]=max(0.,weights[2]);ids[2]=max(0,ids[2]);ids=[min(max(i,0),n-2) for i,n in zip(ids,(nx,ny,nz))]
   weights=[min(1.,max(0.,w)) for w in weights];v=[0.]*3;e=0.;nf=0;nonfinite=0
   for q in range(8):
    i=ids[0]+(q&1);j=ids[1]+((q>>1)&1);k=ids[2]+((q>>2)&1)
    w=math.prod(weights[d] if q&(1<<d) else 1-weights[d] for d in range(3));vv=vec(i,j,k)
    for d in range(3):v[d]+=w*vv[d]
    e+=w*scalar(tk,i,j,k);nf+=scalar(fluid,i,j,k)>.5
    nonfinite+=not all(math.isfinite(t) for t in vv)
   return dict(uvw=v,speed=math.sqrt(sum(a*a for a in v))/OBS['UH'],k=e/OBS['UH']**2,fluid_corners=nf,below_first_center=low,nonfinite_corners=nonfinite)
  masks=[]
  # Match the footprint to analytic STL at mid-building, independent of point MAE.
  for sx,sy,sz in itertools.product((0.,spacing),repeat=3):
   tp=fp=fn=0
   for x in range(322,384,2):
    for y in range(322,384,2):
     i=round((x-origin[0])/spacing);j=round((y-origin[1])/spacing);k=round((32-origin[2])/spacing)
     i=max(0,min(nx-1,i));j=max(0,min(ny-1,j));k=max(0,min(nz-1,k))
     solid=scalar(fluid,i,j,k)<.5;inside=336<=x-sx<368 and 336<=y-sy<368 and 0<=32-sz<64
     tp+=int(solid and inside);fp+=int(solid and not inside);fn+=int(inside and not solid)
   masks.append(dict(shift=[sx,sy,sz],tp=tp,fp=fp,fn=fn,iou=tp/(tp+fp+fn) if tp+fp+fn else None))
  best=sorted(masks,key=lambda q:(-q['iou'],q['shift']))[0];shift=best['shift']
  groups={};diagnostic={}
  for key,pts in OBS['groups'].items():
   groups[key]=[dict(id=p['id'],coord_m=[p['x'],p['y'],p['z']],obs_speed=p['speed'],obs_k=p['k'],no_shift=interp(p['x'],p['y'],p['z']),selected=interp(p['x']+shift[0],p['y']+shift[1],p['z']+shift[2])) for p in pts]
   if key in ('z8','z80'):
    height=8. if key=='z8' else 80.
    diagnostic[key]=[dict(id=p['id'],coord_m=[p['x'],p['y'],height],obs_speed=p['speed'],obs_k=p['k'],no_shift=interp(p['x'],p['y'],height),selected=interp(p['x']+shift[0],p['y']+shift[1],height+shift[2])) for p in pts]
  m.close()
 result=dict(name=name,dx_m=dx,vtk=str(vtk),vtk_size=vtk.stat().st_size,dimensions=[nx,ny,nz],origin=origin,spacing=spacing,mask=masks,selected_shift=best,groups=groups,diagnostic=diagnostic,group_height_m={'z8':4.,'z80':40.,'vertical':'original varying'},diagnostic_height_m={'z8':8.,'z80':80.},UH=OBS['UH'],notes='Diagnostic 8/80 m retains official 4/40 m observed values only as labeled noncolocated reference; not a validation metric. Low 4 m below first center is clamped and flagged.' )
 p=OUT/f'samples_{name}.json';p.write_text(json.dumps(result,indent=2,allow_nan=False));return p

def run_one(repo,dx,mode):
 name,c,steps,avg,stride=prepare(repo,dx,mode);log(f'START {name} steps={steps} avg={avg} stride={stride} config_sha={digest(c/"conf.luwpf")}')
 t=time.time();logpath=OUT/f'solver_{name}.log'
 with logpath.open('w') as f:p=subprocess.run([str(repo/'core/cfd_core/FluidX3D/bin/FluidX3D'),str(c/'conf.luwpf')],cwd=c,stdout=f,stderr=subprocess.STDOUT)
 log(f'END {name} exit={p.returncode} wall_s={time.time()-t:.2f} log_size={logpath.stat().st_size}')
 evidence=dict(name=name,dx=dx,mode=mode,exit=p.returncode,wall_s=time.time()-t,steps_requested=steps,avg_steps_requested=avg,stride=stride,config_sha256=digest(c/'conf.luwpf'),log_sha256=digest(logpath),log_size=logpath.stat().st_size,log_mtime=logpath.stat().st_mtime)
 if p.returncode==0:
  sample=extract(c,name,dx);evidence.update(samples=str(sample),samples_sha256=digest(sample),samples_size=sample.stat().st_size,samples_mtime=sample.stat().st_mtime)
 (OUT/f'evidence_{name}.json').write_text(json.dumps(evidence,indent=2));return evidence

def main():
 if (ROOT/'started').exists():raise RuntimeError('exclusive start marker exists')
 (ROOT/'started').write_text(str(time.time()))
 repo=ROOT/'repo';log('CLONE start');subprocess.run(['git','clone','-q','https://github.com/hweifluids/LatticeUrbanWind.git',str(repo)],check=True)
 sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();assert sha=='dd438c1c68664980a92460e4778f18f36be3f47c',sha
 log('BUILD start '+sha);build=OUT/'build.log'
 with build.open('w') as f:p=subprocess.run(['make','Linux','-j2'],cwd=repo/'core/cfd_core/FluidX3D',stdout=f,stderr=subprocess.STDOUT)
 assert p.returncode==0,build.read_text()[-1000:]
 for dx,mode in [(4.,'r9'),(10.,'r9'),(4.,'r8'),(10.,'r8')]:
  # A100 nominal 5.4 CU/h. Hard 0.9 CU gate measured from session creation in owner-side monitor.
  if mode=='r8' and time.time()-float(Path('/content/r216_session_start').read_text())>0.7/5.4*3600:
   log('SKIP r8: cumulative session cost > 0.7 CU');break
  if time.time()-float(Path('/content/r216_session_start').read_text())>0.9/5.4*3600:
   log('STOP 0.9 CU guard');break
  evidence=run_one(repo,dx,mode)
  if evidence['exit']!=0:log('STOP solver nonzero');break
 (ROOT/'done').write_text(str(time.time()));log('DONE')
if __name__=='__main__':
 try:main()
 except Exception:
  log(traceback.format_exc());(ROOT/'failed').write_text(traceback.format_exc());raise
