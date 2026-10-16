"""Remote read-only postprocess of r3 average VTK. Keep all large fields on VM."""
from pathlib import Path
import json,re
import numpy as np
import xlrd
r=Path('/content/luw-aij-r3');case=r/'case_fine2';assert 'exit=0' in (r/'fine2.exit').read_text();files=list((case/'RESULTS/vtk').glob('*_avg*.vtk'))
assert len(files)==1,files
p=files[0]
with p.open('rb') as f:
 h=[]
 for _ in range(16):
  s=f.readline().decode('ascii','replace').strip();h.append(s)
  if s.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
assert h[-2].startswith('SCALARS u_avg') and h[-1].startswith('LOOKUP_TABLE'),h
dim=list(map(int,next(s for s in h if s.startswith('DIMENSIONS')).split()[1:]));org=np.array(list(map(float,next(s for s in h if s.startswith('ORIGIN')).split()[1:])));dx=float(next(s for s in h if s.startswith('SPACING')).split()[1]);nx,ny,nz=dim
u=np.memmap(p,dtype='>f4',mode='r',offset=offset,shape=(nz,ny,nx,3))
print('VTK',p,p.stat().st_size,'dim',dim,'origin',org,'dx',dx,flush=True)
book=xlrd.open_workbook(str(case/'CaseE(Niigata).xls'));sh=book.sheet_by_name('Geometry&Points');xy=np.array([[float(sh.cell_value(i,j)) for j in (2,3)] for i in range(2,82)]);ids=[int(sh.cell_value(i,1)) for i in range(2,82)]
shift=np.array([1010.50008,1000.60004]); profile=np.loadtxt(case/'wind_bc/profile.dat',skiprows=1)
print('PROFILE',profile[:10],flush=True)
# Profile file format explicitly inspected below if needed; Uref supplied from previous exact interpolation.
uref=3.9286416

def bilinear(k,x,y):
 i=int(np.floor((x-org[0])/dx));j=int(np.floor((y-org[1])/dx));a=(x-org[0])/dx-i;b=(y-org[1])/dx-j
 if i<0 or j<0 or i+1>=nx or j+1>=ny:raise ValueError((i,j))
 v=np.asarray(u[k,j:j+2,i:i+2],dtype=np.float64)
 return ((1-a)*(1-b)*v[0,0]+a*(1-b)*v[0,1]+(1-a)*b*v[1,0]+a*b*v[1,1]),v

def linear_z(z,x,y):
 k=(z-org[2])/dx;lo=int(np.floor(k));a=k-lo
 v0,c0=bilinear(lo,x,y);v1,c1=bilinear(lo+1,x,y)
 return (1-a)*v0+a*v1,lo,lo+1,c0,c1
rows=[];k_above=int(np.ceil((2-org[2])/dx))
for n,(x,y) in enumerate(xy+shift):
 vec,kl,kh,c0,c1=linear_z(2,x,y)
 # first height >=2 m for which all four bilinear horizontal neighbours are strictly nonzero
 fluid=None
 for k in range(k_above,min(nz,k_above+50)):
  v,c=bilinear(k,x,y)
  if np.all(np.linalg.norm(c,axis=2)>1e-7):
   fluid={'z_m':float(org[2]+k*dx),'k':k,'ratio':float(np.linalg.norm(v)/uref)};break
 rows.append({'id':ids[n],'xls_xy':xy[n].tolist(),'vtk_xy':[float(x),float(y)],'linear_ratio':float(np.linalg.norm(vec)/uref),'linear_lo_fluid_corners':int((np.linalg.norm(c0,axis=2)>1e-7).sum()),'linear_hi_fluid_corners':int((np.linalg.norm(c1,axis=2)>1e-7).sum()),'above_fluid':fluid})
# Inflow +y side: points x=750..1250, y near upstream 1960..1990 and outside buildings.
up=[]
for y in [1600,1800,1900,1960,1990]:
 for z in [2,15.9]:
  vals=[]
  for x in np.linspace(750,1250,21):
   v,*_=linear_z(z,x,y);vals.append(float(np.linalg.norm(v)))
  up.append({'y_m':y,'z_m':z,'mean_speed_mps':float(np.mean(vals)),'median_speed_mps':float(np.median(vals)),'min_speed_mps':float(np.min(vals)),'max_speed_mps':float(np.max(vals))})
out={'file':str(p),'size':p.stat().st_size,'dimensions':dim,'origin':org.tolist(),'dx':dx,'uref':uref,'k_above_2m':k_above,'z_above_m':float(org[2]+k_above*dx),'rows':rows,'upstream':up}
(r/'samples_r3.json').write_text(json.dumps(out,indent=2));print('COMPLETE',len(rows),'upstream',up,flush=True)
