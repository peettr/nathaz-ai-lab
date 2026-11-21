#!/usr/bin/env python3
"""Read registered fine-grid Su points and compact 1.5/2 m planes."""
import array,hashlib,json,math,mmap,pathlib,statistics,struct,sys,zipfile
r=pathlib.Path(sys.argv[1]);case=r/'case_4gpu'
assert (r/'solver.exitcode').read_text().strip()=='0'
files=list((case/'RESULTS/vtk').glob('*_avg*.vtk'));assert len(files)==1,files
vtk=files[0];ref=json.loads((r/'B2u_reference_points.json').read_text());assert len(ref['rows'])==80
with vtk.open('rb') as f:
 header=[]
 for _ in range(25):
  line=f.readline().decode('ascii','replace').strip();header.append(line)
  if line.startswith('LOOKUP_TABLE'):break
 offset=f.tell()
assert header[-2].startswith('SCALARS u_avg'),header
nx,ny,nz=map(int,next(x for x in header if x.startswith('DIMENSIONS')).split()[1:]);org=list(map(float,next(x for x in header if x.startswith('ORIGIN')).split()[1:]));dx=float(next(x for x in header if x.startswith('SPACING')).split()[1]);N=nx*ny*nz
assert (nx,ny,nz)==(1000,1000,540) and dx==.5,(nx,ny,nz,dx)
with vtk.open('rb') as f:
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def off(start,name,components):
  tag=(f'SCALARS {name} float {components}\nLOOKUP_TABLE default\n').encode();assert m[start:start+len(tag)]==tag,(name,start);return start+len(tag)
 rho=off(offset+N*12,'rho_avg',1);fluid=off(rho+N*4,'fluid',1);tke=off(fluid+N*4,'tke',1);su=off(tke+N*4,'speed_mean',1);su2=off(su+N*4,'speed2_mean',1);assert su2+N*4==len(m)
 def at(pos,i,j,k):return struct.unpack_from('>f',m,pos+((k*ny+j)*nx+i)*4)[0]
 rows=[]
 for p in ref['rows']:
  # Preserve the baseline physical point registration: +1 m is the original
  # spreadsheet-to-CFD registration, not the new mesh spacing.
  x=p['xls_xy'][0]+1010.50008-760+1.;y=p['xls_xy'][1]+1000.60004-750+1.;z=2.
  a=[(v-o)/dx for v,o in zip((x,y,z),org)];inds=[math.floor(v) for v in a];w=[v-i for v,i in zip(a,inds)]
  assert all(0<=i<n-1 for i,n in zip(inds,(nx,ny,nz)))
  speed=0.;corners=0;solid_weight=0.
  for c in range(8):
   ijk=[inds[d]+int(bool(c&(1<<d))) for d in range(3)]
   weight=math.prod(w[d] if c&(1<<d) else 1-w[d] for d in range(3))
   speed+=weight*at(su,*ijk);isfluid=at(fluid,*ijk)>.5
   corners+=isfluid;solid_weight+=weight*(not isfluid)
  rows.append({'id':p['id'],'obs':p['after'],'Su':speed/ref['uref'],'fluid_corners':corners,'solid_weight':solid_weight})
 assert {q['id'] for q in rows}==set(range(1,81)) and all(math.isfinite(q['Su']) for q in rows)
 mae=statistics.mean(abs(q['Su']-q['obs']) for q in rows)
 old={q['id']:q['sample']['plus_dx']['Su_ratio'] for q in ref['rows']}
 result={'vtk':str(vtk),'vtk_bytes':vtk.stat().st_size,'rows':rows,'mae':mae,'baseline_mae':statistics.mean(abs(old[q['id']]-q['obs']) for q in rows),'delta_mae':mae-statistics.mean(abs(old[q['id']]-q['obs']) for q in rows),'dimensions':[nx,ny,nz],'origin':org,'dx':dx,'uref':ref['uref']}
 (r/'points_80_t2.json').write_text(json.dumps(result,indent=2)+'\n')
 flags_path=case/'RESULTS/native_flags_z0_23.bin'
 assert flags_path.stat().st_size==nx*ny*24
 with flags_path.open('rb') as fl:
  flags=mmap.mmap(fl.fileno(),0,access=mmap.ACCESS_READ)
  for z in (1.5,2.):
   k0=math.floor((z-org[2])/dx);w=(z-org[2])/dx-k0
   assert 0<=k0<23,(z,k0,org)
   dest=r/f'plane_z{z:g}.zip'
   with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
    for name,pos,comp in [('u_avg',offset,3),('Su',su,1),('k',tke,1),('fluid',fluid,1)]:
     # Stream a plane-sized buffer per field, never materialize 540 levels.
     for d in range(comp):
      vals=array.array('f')
      for j in range(ny):
       for i in range(nx):
        v=(1-w)*at(pos,i,j,k0)+w*at(pos,i,j,k0+1) if comp==1 else (1-w)*struct.unpack_from('>f',m,pos+(((k0*ny+j)*nx+i)*comp+d)*4)[0]+w*struct.unpack_from('>f',m,pos+((((k0+1)*ny+j)*nx+i)*comp+d)*4)[0]
        vals.append(v)
      archive.writestr(f'{name}_{d}.f32le',vals.tobytes())
    archive.writestr('flags_lower.u8',flags[k0*nx*ny:(k0+1)*nx*ny])
    archive.writestr('flags_upper.u8',flags[(k0+1)*nx*ny:(k0+2)*nx*ny])
    archive.writestr('metadata.json',json.dumps({'nx':nx,'ny':ny,'z_m':z,'origin':org,'spacing_m':dx,'dtype':'float32 little-endian','order':'x fastest','flag_levels':[k0,k0+1],'flag_is_native':True}))
   print('PLANE',dest,dest.stat().st_size,flush=True)
  flags.close()
 m.close()
print('EXTRACT',json.dumps({'mae':mae,'delta_mae':result['delta_mae'],'points':len(rows),'vtk_bytes':vtk.stat().st_size}),flush=True)
