#!/usr/bin/env python3
"""Extract only B2u-registered 80 points from the remote average VTK."""
import hashlib,json,math,mmap,pathlib,struct,sys,statistics
r=pathlib.Path(sys.argv[1]); case=r/'case_4gpu'
assert (r/'solver.exitcode').read_text().strip()=='0'
files=list((case/'RESULTS/vtk').glob('*_avg*.vtk'));assert len(files)==1,files
vtk=files[0]; ref=json.loads((r/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80
with vtk.open('rb') as f:
 header=[]
 for _ in range(25):
  line=f.readline().decode('ascii','replace').strip();header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
assert header[-2].startswith('SCALARS u_avg'),header
nx,ny,nz=map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:]));dx=float(next(x for x in header if x.startswith('SPACING')).split()[1]);N=nx*ny*nz
assert (nx,ny,nz)==(500,500,270) and dx==1.0,(nx,ny,nz,dx)
with vtk.open('rb') as f:
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def off(start,name,components):
  tag=(f'SCALARS {name} float {components}\nLOOKUP_TABLE default\n').encode();assert m[start:start+len(tag)]==tag,(name,start,m[start:start+80]);return start+len(tag)
 rho=off(offset+N*12,'rho_avg',1);fluid=off(rho+N*4,'fluid',1);tke=off(fluid+N*4,'tke',1);su=off(tke+N*4,'speed_mean',1);su2=off(su+N*4,'speed2_mean',1);assert su2+N*4==len(m)
 def at(pos,i,j,k):return struct.unpack_from('>f',m,pos+((k*ny+j)*nx+i)*4)[0]
 rows=[]
 for p in ref['rows']:
  x=p['xls_xy'][0]+1010.50008-760+dx;y=p['xls_xy'][1]+1000.60004-750+dx;z=2.
  f=[(v-o)/dx for v,o in zip((x,y,z),org)];inds=[math.floor(v) for v in f];w=[v-i for v,i in zip(f,inds)];assert all(0<=i<n-1 for i,n in zip(inds,(nx,ny,nz)))
  speed=0.;corners=0
  for c in range(8):
   ijk=[inds[d]+int(bool(c&(1<<d))) for d in range(3)]
   weight=math.prod(w[d] if c&(1<<d) else 1-w[d] for d in range(3))
   speed+=weight*at(su,*ijk);corners+=at(fluid,*ijk)>.5
  rows.append({'id':p['id'],'obs':p['after'],'Su':speed/ref['uref'],'fluid_corners':corners})
 m.close()
assert {q['id'] for q in rows}==set(range(1,81)) and all(math.isfinite(q['Su']) for q in rows)
mae=statistics.mean(abs(q['Su']-q['obs']) for q in rows)
old={q['id']:q['sample']['plus_dx']['Su_ratio'] for q in ref['rows']}
delta=[abs(q['Su']-old[q['id']]) for q in rows]
h=hashlib.sha256()
with vtk.open('rb') as vf:
 for block in iter(lambda:vf.read(1024*1024),b''): h.update(block)
result={'vtk':str(vtk),'vtk_bytes':vtk.stat().st_size,'vtk_sha256':h.hexdigest(),'rows':rows,'mae':mae,'baseline_mae':statistics.mean(abs(old[q['id']]-q['obs']) for q in rows),'mae_delta_abs':abs(mae-statistics.mean(abs(old[q['id']]-q['obs']) for q in rows)),'point_delta_median':statistics.median(delta),'point_delta_max':max(delta),'gate_b':abs(mae-statistics.mean(abs(old[q['id']]-q['obs']) for q in rows))<=.005 and statistics.median(delta)<=.01,'dimensions':[nx,ny,nz],'origin':org,'dx':dx,'uref':ref['uref']}
(r/'points_80_t1c.json').write_text(json.dumps(result,indent=2)+'\n');print('EXTRACT',json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
