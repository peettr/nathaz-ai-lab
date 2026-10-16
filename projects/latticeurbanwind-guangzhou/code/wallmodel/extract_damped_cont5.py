"""Recover only the average-field diagnostic after z=1 profile bound."""
from pathlib import Path
import math,json,mmap,struct
r=Path('/content/luw_wall_cont5b');case=r/'damped';files=list((case/'RESULTS/vtk').glob('*avg*.vtk'));assert len(files)==1
with files[0].open('rb') as f:
 hdr=[]
 for _ in range(20):
  s=f.readline().decode('ascii','replace').strip();hdr.append(s)
  if s.startswith('LOOKUP_TABLE'):break
 offset=f.tell();nx,ny,nz=map(int,next(s for s in hdr if s.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(s for s in hdr if s.startswith('ORIGIN')).split()[1:]));n=nx*ny*nz;assert (nx,ny,nz)==(500,200,270) and org[2]==-20
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def field(off,name,c):
  tag=(f'SCALARS {name} float {c}\nLOOKUP_TABLE default\n').encode();assert m[off:off+len(tag)]==tag;return off+len(tag)
 rho=field(offset+n*12,'rho_avg',1);fluid=field(rho+n*4,'fluid',1);tke=field(fluid+n*4,'tke',1)
 def scalar(off,x,y,z):return struct.unpack_from('>f',m,off+((z*ny+y)*nx+x)*4)[0]
 def vec(x,y,z):return struct.unpack_from('>fff',m,offset+((z*ny+y)*nx+x)*12)
 profile=[tuple(map(float,line.split())) for line in (case/'wind_bc/profile.dat').read_text().splitlines()[1:]]
 def inlet(z):
  for (a,u),(b,w) in zip(profile,profile[1:]):
   if a<=z<=b:return u+(z-a)*(w-u)/(b-a)
  return None
 rows=[]
 for x in (5,50,100,200,250,300,350,400,450,495):
  for z in range(1,61):
   a=[(*vec(x,y,z+20),scalar(tke,x,y,z+20)) for y in (40,70,100,130,160)]
   avg=[sum(q[i] for q in a)/len(a) for i in range(4)];speed=math.sqrt(sum(t*t for t in avg[:3]));ref=inlet(z)
   rows.append(dict(x=x,z=z,speed=speed,ratio=speed/ref if ref else None,k=avg[3],TI=math.sqrt(max(2*avg[3]/3,0))/speed,mean_u=avg))
 m.close()
(r/'damped_profile.json').write_text(json.dumps(dict(grid=[nx,ny,nz],origin=org,rows=rows)))
print('EXTRACT',[(v['x'],round(v['ratio'],3),round(v['TI'],3)) for v in rows if v['z']==2 and v['x'] in (200,300,400)])
