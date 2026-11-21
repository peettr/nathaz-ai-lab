#!/usr/bin/env python3
"""Colab-only Case D: immutable staged deck, voxel mask gate, full solve and S1 points."""
import csv, hashlib, json, math, mmap, os, pathlib, shutil, struct, subprocess, tarfile, time, traceback
R=pathlib.Path('/content/luw-c38-cased-r4-20261115'); P=R/'stage'; C=P/'caseD'; E=R/'evidence'; E.mkdir(parents=True,exist_ok=True)
LOG=R/'run.log'
def log(*args):
 with LOG.open('a') as f:print(time.strftime('%Y-%m-%d %H:%M:%S %z'),*args,file=f,flush=True)
def cmd(args,stdout=None,cwd=None):
 log('CMD',args);t=time.monotonic()
 with (R/(stdout or 'command.log')).open('a') as f:
  result=subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 log('EXIT',result.returncode,'WALL',round(time.monotonic()-t,2));return result.returncode
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<22),b''):h.update(b)
 return h.hexdigest()
def read_vtk(path):
 f=open(path,'rb');header=[]
 for _ in range(30):
  line=f.readline().decode('ascii','replace').strip();header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 assert header[-2].startswith('SCALARS u_avg'),header
 dims=list(map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]));origin=list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:]));sp=list(map(float,next(x for x in header if x.startswith('SPACING')).split()[1:]));n=math.prod(dims)
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def offset(pos,name):
  b=f'SCALARS {name} float 1\nLOOKUP_TABLE default\n'.encode();assert m[pos:pos+len(b)]==b,(name,pos,m[pos:pos+90]);return pos+len(b)
 u=f.tell();rho=offset(u+n*12,'rho_avg');fluid=offset(rho+n*4,'fluid');tke=offset(fluid+n*4,'tke');assert tke+n*4==len(m)
 def index(i,j,k):return i+dims[0]*(j+dims[1]*k)
 def mask(i,j,k):return struct.unpack_from('>f',m,fluid+index(i,j,k)*4)[0]>.5
 def vel(i,j,k):return struct.unpack_from('>fff',m,u+index(i,j,k)*12)
 return f,m,dims,origin,sp,mask,vel

def gate():
 files=list((C/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(files)==1,files
 vtk=files[0];f,m,dims,o,sp,mask,vel=read_vtk(vtk)
 log('GATE_VTK',str(vtk),vtk.stat().st_size,'dims',dims,'origin',o,'spacing',sp)
 assert all(abs(x-2)<.01 for x in sp),sp
 def ij(x,y):return round((x-o[0])/sp[0]),round((y-o[1])/sp[1])
 open_cols=[]
 for x,y in ((100,100),(300,300),(1400,850),(1600,1000)):
  i,j=ij(x,y); solid=[k for k in range(2,15) if not mask(i,j,k)];ff=next(k for k in range(2,25) if mask(i,j,k));open_cols.append({'xy':[x,y],'solid_k':solid,'first_fluid_k':ff,'wall_label_m':o[2]+sp[2]*(ff-.5)})
 assert len({q['first_fluid_k'] for q in open_cols})==1,open_cols
 for q in open_cols:
  assert len(q['solid_k'])>=8 and q['solid_k']==list(range(2,q['first_fluid_k'])),q
 wall=open_cols[0]['wall_label_m'];log('GATE_GROUND',open_cols)
 # Scan each 4m column in the original 560x540 m block for solid attachment and roof classes.
 height_classes={'low':[],'tower':[]};floating=[]
 for x in range(572,1130,4):
  for y in range(282,820,4):
   i,j=ij(x,y);ks=[k for k in range(open_cols[0]['first_fluid_k'],min(dims[2],75)) if not mask(i,j,k)]
   if not ks:continue
   if ks[0]>open_cols[0]['first_fluid_k']:floating.append((x,y,ks[0]))
   top=o[2]+sp[2]*(max(ks)+.5)-wall
   if abs(top-10)<=2:height_classes['low'].append([x,y,top])
   if abs(top-100)<=2:height_classes['tower'].append([x,y,top])
 assert not floating,floating[:10]
 assert height_classes['low'] and height_classes['tower'],{k:len(v) for k,v in height_classes.items()}
 summary={'vtk':str(vtk),'vtk_size':vtk.stat().st_size,'dims':dims,'origin':o,'spacing':sp,'open_columns':open_cols,'ground_wall_label_m':wall,'low_roof_sample_count':len(height_classes['low']),'tower_roof_sample_count':len(height_classes['tower']),'low_roof_examples':height_classes['low'][:4],'tower_roof_examples':height_classes['tower'][:4],'floating':len(floating)}
 (E/'geometry_gate.json').write_text(json.dumps(summary,indent=2));m.close();f.close();log('GEOMETRY_GATE_PASS',json.dumps(summary))
 # Gate field is only a one-step snapshot and must not be used for point extraction.
 return summary

def points():
 files=list((C/'RESULTS/vtk').glob('*_avg-*.vtk'));assert len(files)==1,files
 f,m,dims,o,sp,mask,vel=read_vtk(files[0]);wall=json.loads((E/'geometry_gate.json').read_text())['ground_wall_label_m']
 def scalar(off,i,j,k):return struct.unpack_from('>f',m,off+((k*dims[1]+j)*dims[0]+i)*4)[0]
 n=math.prod(dims);uoff=f.tell();rho=uoff+n*12+len(b'SCALARS rho_avg float 1\nLOOKUP_TABLE default\n');fluid=rho+n*4+len(b'SCALARS fluid float 1\nLOOKUP_TABLE default\n');tke=fluid+n*4+len(b'SCALARS tke float 1\nLOOKUP_TABLE default\n')
 rows=[]
 with (P/'caseD_points.csv').open(newline='',encoding='utf-8-sig') as c:
  for rec in csv.DictReader(c):
   x,y,h=[float(rec[q]) for q in ('x','y','z')];xl,yl=x+850,y+550;label=max(wall+h,wall+sp[2]/2);clamped=wall+h<label-1e-9
   xyz=[(p-a)/d for p,a,d in zip((xl,yl,label),o,sp)];ids=[math.floor(q) for q in xyz];frac=[q-i for q,i in zip(xyz,ids)]
   assert all(0<=i<dim-1 for i,dim in zip(ids,dims)),(rec,ids,dims)
   comps=[0.,0.,0.];solids=[]
   for code in range(8):
    offset=[(code>>j)&1 for j in range(3)];weight=math.prod(frac[j] if offset[j] else 1-frac[j] for j in range(3))
    if weight<=1e-12:continue
    i,j,k=[ids[d]+offset[d] for d in range(3)]
    if not mask(i,j,k):solids.append([i,j,k])
    for d,v in enumerate(vel(i,j,k)):comps[d]+=weight*v
   assert all(map(math.isfinite,comps))
   rows.append({'kind':rec['kind'],'id':rec['No'],'c38_xyz_m':[x,y,h],'luw_sample_xyz_m':[xl,yl,label],'actual_agl_m':label-wall,'u_mps':comps[0],'v_mps':comps[1],'w_mps':comps[2],'speed_over_UH':math.sqrt(sum(v*v for v in comps))/6.65,'clamped':clamped,'solid_corners':solids})
 assert len(rows)==99,len(rows)
 m.close();f.close()
 summary={'source_vtk':str(files[0]),'source_vtk_size':files[0].stat().st_size,'source_vtk_sha256':sha(files[0]),'origin_xyz_m':o,'spacing_xyz_m':sp,'wall_label_m':wall,'UH_mps':6.65,'UH_height_m':100,'rows':rows,'clamped':sum(x['clamped'] for x in rows),'mixed':sum(bool(x['solid_corners']) for x in rows)}
 (E/'pointvalues.json').write_text(json.dumps(summary,indent=2,allow_nan=False));log('POINTS_DONE',len(rows),summary['clamped'],summary['mixed'])

def main():
 assert not (R/'started').exists();(R/'started').touch(exist_ok=False)
 with tarfile.open('/content/cased_stage.tar.gz') as a:a.extractall(P,filter='data')
 assert sha('/content/source_dd438c1.tar.gz')=='88ac44d3005dde28267a18f40fe6d5f5071105719ead40ca12509a5c492204d0'
 with tarfile.open('/content/source_dd438c1.tar.gz') as a:a.extractall(R/'source',filter='data')
 file_hashes=json.loads(pathlib.Path('/content/source_extracted_sha256.json').read_text())
 for name,h in file_hashes.items():assert sha(R/'source'/name)==h,name
 log('EXTRACTED_SOURCE_VERIFIED',len(file_hashes))
 manifest=json.loads((P/'manifest.json').read_text())
 for name,h in manifest['output_sha256'].items(): assert sha(P/name)==h,name
 assert cmd(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'])==0
 assert cmd(['make','Linux','-j2'],stdout='build.log',cwd=R/'source/core/cfd_core/FluidX3D')==0
 binary=R/'source/core/cfd_core/FluidX3D/bin/FluidX3D';assert binary.is_file()
 full=(C/'conf.luwpf').read_text();gc=full.replace('run_nstep = 33767','run_nstep = 1').replace('purge_avg = 23215','purge_avg = 1').replace('purge_avg_stride = 42','purge_avg_stride = 1')
 assert gc!=full
 # Gate in independent root, never overwrite its average field with the scientific run.
 gate_dir=R/'gate';shutil.copytree(C,gate_dir,ignore=shutil.ignore_patterns('RESULTS'));(gate_dir/'conf.luwpf').write_text(gc)
 original=C;globals()['C']=gate_dir
 try:
  assert cmd([str(binary),str(gate_dir/'conf.luwpf')],stdout='gate_solver.log',cwd=gate_dir)==0
  gate()
 finally:globals()['C']=original
 # Full run only after actual voxelized mask passes and the creation-to-stop budget still covers it.
 deadline=float((R/'deadline_epoch').read_text());remaining=deadline-time.time()
 log('REMAINING_BEFORE_SOLVE_S',round(remaining,1))
 assert remaining>=2700, f'budget insufficient for solver+extraction+stop: {remaining:.1f}s'
 t=time.monotonic();solverlog=(R/'solver.log').open('a')
 try:
  p=subprocess.Popen([str(binary),str(C/'conf.luwpf')],cwd=C,stdout=solverlog,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
  try: ret=p.wait(timeout=max(1,deadline-time.time()-240))
  except subprocess.TimeoutExpired:
   p.terminate()
   try:p.wait(timeout=20)
   except subprocess.TimeoutExpired:p.kill();p.wait()
   ret=p.returncode;log('SOLVER_BUDGET_STOP',ret)
 finally:solverlog.close()
 (E/'solver_exit.json').write_text(json.dumps({'exit':ret,'wall_seconds':time.monotonic()-t}))
 assert ret==0,ret
 points()
 for name in ('geometry_gate.json','solver_exit.json','pointvalues.json'):
  assert (E/name).stat().st_size>0
 files=[E/name for name in ('geometry_gate.json','solver_exit.json','pointvalues.json')]+[R/name for name in ('run.log','gate_solver.log','solver.log','build.log')]
 (E/'sha256.json').write_text(json.dumps({p.name:sha(p) for p in files},indent=2))
 import zipfile
 with zipfile.ZipFile(R/'result.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
  for p in files+[E/'sha256.json']:z.write(p,p.name)
 log('SUCCESS',sha(R/'result.zip'));(R/'run.done').write_text('success\n')
if __name__=='__main__':
 try:main()
 except BaseException:
  log('FAILED',traceback.format_exc());(R/'run.failed').write_text(traceback.format_exc());raise
