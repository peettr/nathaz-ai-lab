"""Read r4b average VTK on remote VM; output only sampled vectors."""
from pathlib import Path
import json,numpy as np,subprocess,sys
r=Path('/content/luw-aij-r4b');case=r/'case_west';assert 'exit=0' in (r/'solver.exit').read_text(),(r/'solver.exit').read_text()
files=list((case/'RESULTS/vtk').glob('*_avg*.vtk'));assert len(files)==1,files;p=files[0]
with p.open('rb') as f:
 h=[]
 for _ in range(16):
  s=f.readline().decode('ascii','replace').strip();h.append(s)
  if s.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
assert h[-2].startswith('SCALARS u_avg') and h[-1].startswith('LOOKUP_TABLE'),h
nx,ny,nz=map(int,next(s for s in h if s.startswith('DIMENSIONS')).split()[1:]);org=np.array(list(map(float,next(s for s in h if s.startswith('ORIGIN')).split()[1:])));dx=float(next(s for s in h if s.startswith('SPACING')).split()[1]);u=np.memmap(p,dtype='>f4',mode='r',offset=offset,shape=(nz,ny,nx,3));print('FIELD',str(p),p.stat().st_size,'dim',nx,ny,nz,'origin',org,'dx',dx,flush=True)
try:import xlrd
except ImportError:subprocess.run([sys.executable,'-m','pip','install','-q','xlrd'],check=True);import xlrd
book=xlrd.open_workbook(str(case/'CaseE(Niigata).xls'));sh=book.sheet_by_name('Geometry&Points');xy=np.array([[float(sh.cell_value(i,j)) for j in (2,3)] for i in range(2,82)]);ids=[int(sh.cell_value(i,1)) for i in range(2,82)]
shift=np.array([1010.50008-300,1000.60004-650]);uref=3.9286416
def bilinear(k,x,y):
 i=int(np.floor((x-org[0])/dx));j=int(np.floor((y-org[1])/dx));a=(x-org[0])/dx-i;b=(y-org[1])/dx-j
 if i<0 or j<0 or i+1>=nx or j+1>=ny:raise ValueError((i,j,x,y))
 v=np.asarray(u[k,j:j+2,i:i+2],dtype=np.float64)
 return ((1-a)*(1-b)*v[0,0]+a*(1-b)*v[0,1]+(1-a)*b*v[1,0]+a*b*v[1,1]),v
def linear_z(z,x,y):
 k=(z-org[2])/dx;lo=int(np.floor(k));a=k-lo;v0,c0=bilinear(lo,x,y);v1,c1=bilinear(lo+1,x,y);return (1-a)*v0+a*v1,lo,lo+1,c0,c1
rows=[]
for n,(x,y) in enumerate(xy+shift):
 vec,lo,hi,c0,c1=linear_z(2,x,y);rows.append({'id':ids[n],'xls_xy':xy[n].tolist(),'local_xy':[float(x),float(y)],'linear_ratio':float(np.linalg.norm(vec)/uref),'lower_fluid_corners':int((np.linalg.norm(c0,axis=2)>1e-7).sum()),'upper_fluid_corners':int((np.linalg.norm(c1,axis=2)>1e-7).sum())})
up=[]
for x in [10,100,300,450]:
 for z in [2,15.9]:
  vals=[]
  for y in np.linspace(200,500,13):
   v,*_=linear_z(z,x,y);vals.append(float(np.linalg.norm(v)))
  up.append({'x_m':x,'z_m':z,'mean_speed_mps':float(np.mean(vals)),'median_speed_mps':float(np.median(vals)),'min_speed_mps':float(np.min(vals)),'max_speed_mps':float(np.max(vals))})
out={'field_size_bytes':p.stat().st_size,'dimensions':[nx,ny,nz],'origin':org.tolist(),'dx':dx,'uref':uref,'crop_origin_raw_stl_m':[300,650],'rows':rows,'upstream':up}
(r/'samples.json').write_text(json.dumps(out,indent=2));print('COMPLETE',len(rows),'upstream',up,flush=True)
