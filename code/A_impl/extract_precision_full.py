"""Extract small evidence from a full-size Colab VTK; no local solver."""
from pathlib import Path
import mmap,struct,math,json,csv
import numpy as np

def extract(case_dir,out, ustar=.2418545,z0=.024,kappa=.40):
 files=list((Path(case_dir)/'RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1,files
 with files[0].open('rb') as f:
  hdr=[]
  while True:
   line=f.readline().decode('ascii','replace').strip();hdr.append(line)
   if line.startswith('LOOKUP_TABLE'):break
  off=f.tell(); nx,ny,nz=map(int,next(x for x in hdr if x.startswith('DIMENSIONS')).split()[1:]); origin=list(map(float,next(x for x in hdr if x.startswith('ORIGIN')).split()[1:]));n=nx*ny*nz
  assert (nx,ny,nz)==(500,200,270) and origin[2]==-20,(nx,ny,nz,origin)
  mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  def at(offset,x,y,z,c=1):
   return np.frombuffer(mm,dtype='>f4',count=c,offset=offset+4*c*((z*ny+y)*nx+x)).astype('f8')
  uoff=off;rhooff=mm.find(b'LOOKUP_TABLE default\n',off+12*n)+len(b'LOOKUP_TABLE default\n');assert rhooff>12*n
  fluidpos=mm.find(b'LOOKUP_TABLE default\n',rhooff+4*n); fluidoff=fluidpos+len(b'LOOKUP_TABLE default\n')
  tkeoff=mm.find(b'LOOKUP_TABLE default\n',fluidoff+4*n)+len(b'LOOKUP_TABLE default\n')
  assert b'SCALARS rho_avg' in mm[rhooff-90:rhooff]
  inlet=lambda z:ustar/kappa*math.log((z+z0)/z0)
  rows=[]
  for x in (5,100,200,300,400,495):
   for z in range(1,61):
    v=np.mean([at(uoff,x,y,z+20,3) for y in (40,70,100,130,160)],axis=0)
    q=float(np.linalg.norm(v));rows.append(dict(x=x,z=z,speed=q,ratio=q/inlet(z),u=v.tolist(),tke=float(np.mean([at(tkeoff,x,y,z+20)[0] for y in (40,70,100,130,160)]))))
  # Cell-centered mean momentum flux incl pressure p=c_s^2*rho, via SI c_s=Uconv/sqrt(3)
  # Obtain lattice/physical U factor from config reference U profile ~0.1 LU / U(15.9) SI.
  uconvert=.1/3.9286416
  cs2=1.0/(3.0*uconvert*uconvert)
  def flux_x(x):
   adv=pres=kev=0.
   for z in range(21,270):
    for y in range(1,ny-1):
     v=at(uoff,x,y,z,3);rho=at(rhooff,x,y,z)[0]; adv+=rho*v[0]*v[0];pres+=rho*cs2;kev+=at(tkeoff,x,y,z)[0]*rho
   return dict(adv=adv,pres=pres, tke_upper_proxy=kev)
  def flux_top():
   adv=pres=kev=0.
   for x in range(100,401):
    for y in range(1,ny-1):
     v=at(uoff,x,y,269,3);rho=at(rhooff,x,y,269)[0];adv+=rho*v[0]*v[2];kev+=at(tkeoff,x,y,269)[0]*rho
   return dict(adv=adv,tke_upper_proxy=kev)
  f100=flux_x(100);f400=flux_x(400);top=flux_top()
  # ground wall force stored as sum over transverse columns, in LU units / rho.
  wallfile=Path(case_dir)/'RESULTS/wall_force_x.csv';wall=list(csv.DictReader(wallfile.open())) if wallfile.exists() else []
  data=dict(grid=[nx,ny,nz],origin=origin,rows=rows,flux100=f100,flux400=f400,top=top,wall_x=wall,wall_tau_csv=(Path(case_dir)/'RESULTS/wall_tau_actual.csv').read_text() if (Path(case_dir)/'RESULTS/wall_tau_actual.csv').exists() else None,unit_u_lattice_per_si=uconvert)
  Path(out).write_text(json.dumps(data,indent=2));mm.close()
 print('EXTRACT',out,[(v['x'],round(v['ratio'],4)) for v in rows if v['z']==2],flush=True)
