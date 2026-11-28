from pathlib import Path
import mmap,struct,json,numpy as np
r=Path('/content/b2u_case');v=list((r/'case/RESULTS/vtk').glob('*_avg*.vtk'));assert len(v)==1
f=v[0].open('rb');m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
header=[]
while True:
 line=f.readline().decode();header.append(line)
 if line.startswith('LOOKUP_TABLE'):break
N=np.prod([int(x) for x in next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]])
o=f.tell()
def nxt(off,c,name):
 pos=off+int(N)*4*c;tag=(f'SCALARS {name} float 1\nLOOKUP_TABLE default\n').encode();assert m[pos:pos+len(tag)]==tag,(name,pos,m[pos:pos+100]);return pos+len(tag)
rho=nxt(o,3,'rho_avg');fluid=nxt(rho,1,'fluid');tke=nxt(fluid,1,'tke');su=nxt(tke,1,'speed_mean');su2=nxt(su,1,'speed2_mean')
a=np.ndarray((int(N),3),dtype='>f4',buffer=m,offset=o);flags=np.ndarray((int(N),),dtype='>f4',buffer=m,offset=fluid);scalar=np.ndarray((int(N),),dtype='>f4',buffer=m,offset=su);sq=np.ndarray((int(N),),dtype='>f4',buffer=m,offset=su2)
# Chunked to bound memory. For interpolation of nonnegative weights Jensen holds when corners are fluid.
count=0;bad1=bad2=nonfinite=0;maximum1=maximum2=0.;min_scalar=1e9
for lo in range(0,int(N),1_000_000):
 hi=min(int(N),lo+1_000_000);mask=flags[lo:hi]>.5
 u=np.asarray(a[lo:hi],dtype=np.float64);s=np.asarray(scalar[lo:hi],dtype=np.float64);q=np.asarray(sq[lo:hi],dtype=np.float64)
 speed=np.sqrt(np.sum(u*u,axis=1));rms=np.sqrt(np.maximum(q,0));tol=3e-5
 bad1+=int(np.sum((speed>s+tol)&mask));bad2+=int(np.sum((s>rms+tol)&mask));nonfinite+=int(np.sum((~np.isfinite(s)|~np.isfinite(q))&mask))
 count+=int(mask.sum());maximum1=max(maximum1,float(np.max((speed-s)[mask],initial=0)));maximum2=max(maximum2,float(np.max((s-rms)[mask],initial=0)));min_scalar=min(min_scalar,float(np.min(s[mask],initial=1e9)))
result={'fluid_count':count,'violations_mean_vector_gt_scalar':bad1,'violations_scalar_gt_rms':bad2,'nonfinite':nonfinite,'max_gap_left':maximum1,'max_gap_right':maximum2,'min_scalar':min_scalar,'tolerance_mps':3e-5,'vtk_size':v[0].stat().st_size}
(r/'field_inequality.json').write_text(json.dumps(result)+'\n');print(result);assert bad1==bad2==nonfinite==0
m.close();f.close()
