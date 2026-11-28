#!/usr/bin/env python3
"""Case A 10 m v2 point extraction and streaming mean-field handoff."""
import gzip, hashlib, itertools, json, math, mmap, re, statistics, struct, sys
from pathlib import Path
root=Path(sys.argv[1]); path=Path(sys.argv[2]); obs=json.loads((root/'caseA_observations_official.json').read_text()); out=root/'out';out.mkdir(exist_ok=False)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
with path.open('rb') as f:
 head=[]
 for _ in range(30):
  line=f.readline().decode('ascii','replace').strip();head.append(line)
  if line=='LOOKUP_TABLE default':break
 offset=f.tell()
assert 'BINARY' in head and 'DATASET STRUCTURED_POINTS' in head
nx,ny,nz=map(int,next(s for s in head if s.startswith('DIMENSIONS')).split()[1:]);origin=list(map(float,next(s for s in head if s.startswith('ORIGIN')).split()[1:]));spacing=float(next(s for s in head if s.startswith('SPACING')).split()[1]);N=nx*ny*nz
assert (nx,ny)==(109,70) and nz>=39 and abs(spacing-704/70)<1e-3
with path.open('rb') as f:
 m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
 def after(start,key):
  token=[已隐去]'SCALARS {key} float 1\nLOOKUP_TABLE default\n'.encode();assert m[start:start+len(token)]==token,(key,start);return start+len(token)
 rho=after(offset+12*N,'rho_avg');fluid=after(rho+4*N,'fluid');tke=after(fluid+4*N,'tke');assert tke+4*N==len(m)
 def scalar(o,i,j,k):return struct.unpack_from('>f',m,o+4*(i+nx*(j+ny*k)))[0]
 def vec(i,j,k):return struct.unpack_from('>fff',m,offset+12*(i+nx*(j+ny*k)))
 def interp(x,y,z):
  frac=[(v-o)/spacing for v,o in zip((x,y,z),origin)];ids=[math.floor(v) for v in frac];w=[v-i for v,i in zip(frac,ids)]
  low=frac[2]<0;ids=[min(max(i,0),n-2) for i,n in zip(ids,(nx,ny,nz))];w=[min(1.,max(0.,q)) for q in w];v=[0.]*3;kval=0.;nf=0;bad=0
  for q in range(8):
   i=ids[0]+(q&1);j=ids[1]+((q>>1)&1);k=ids[2]+((q>>2)&1)
   weight=math.prod(w[d] if q&(1<<d) else 1-w[d] for d in range(3));vv=vec(i,j,k)
   for d in range(3):v[d]+=weight*vv[d]
   kval+=weight*scalar(tke,i,j,k);nf+=scalar(fluid,i,j,k)>.5;bad+=not all(math.isfinite(a) for a in vv)
  return dict(uvw=v,speed=math.sqrt(sum(a*a for a in v))/obs['UH'],k=kval/obs['UH']**2,fluid_corners=nf,below_first_center=low,nonfinite_corners=bad)
 masks=[]
 for sx,sy,sz in itertools.product((0.,spacing),repeat=3):
  tp=fp=fn=0
  for x in range(322,384,2):
   for y in range(322,384,2):
    i=min(nx-1,max(0,round((x-origin[0])/spacing)));j=min(ny-1,max(0,round((y-origin[1])/spacing)));k=min(nz-1,max(0,round((32+spacing/2-origin[2])/spacing)))
    solid=scalar(fluid,i,j,k)<.5;inside=336<=x-sx<368 and 336<=y-sy<368 and 0<=32-sz<64
    tp+=solid and inside;fp+=solid and not inside;fn+=inside and not solid
  masks.append(dict(shift=[sx,sy,sz],tp=tp,fp=fp,fn=fn,iou=tp/(tp+fp+fn) if tp+fp+fn else None))
 best=sorted(masks,key=lambda q:(-q['iou'],q['shift']))[0];shift=best['shift']
 groups={};diagnostic={}
 for key,pts in obs['groups'].items():
  groups[key]=[dict(id=p['id'],coord_m=[p['x'],p['y'],p['z']],obs_speed=p['speed'],obs_k=p['k'],no_shift=interp(p['x'],p['y'],p['z']+spacing/2),selected=interp(p['x']+shift[0],p['y']+shift[1],p['z']+spacing/2+shift[2])) for p in pts]
  if key in ('z8','z80'):
   height=8. if key=='z8' else 80.
   diagnostic[key]=[dict(id=p['id'],coord_m=[p['x'],p['y'],height],obs_speed=p['speed'],obs_k=p['k'],no_shift=interp(p['x'],p['y'],height+spacing/2),selected=interp(p['x']+shift[0],p['y']+shift[1],height+spacing/2+shift[2])) for p in pts]
 samples={'source_vtk':str(path),'vtk_sha256':sha(path),'dims':[nx,ny,nz],'origin':origin,'spacing':spacing,'height_rule':'effective physical height = VTK label - dx/2; sampling label=target + dx/2','selected_shift':best,'masks':masks,'groups':groups,'diagnostic':diagnostic}
 (out/'samples_r9_dx10_v2.json').write_text(json.dumps(samples,indent=2,allow_nan=False))
 # Same metric definitions as 0b compare_local.py, explicitly separately labeled.
 def pearson(a,b):
  av=statistics.mean(a);bv=statistics.mean(b);d=math.sqrt(sum((v-av)**2 for v in a)*sum((v-bv)**2 for v in b));return sum((v-av)*(w-bv) for v,w in zip(a,b))/d if d else None
 def metrics(rows,var):
  a=[p[var]['speed'] for p in rows];b=[p['obs_speed'] for p in rows];ak=[p[var]['k'] for p in rows];bk=[p['obs_k'] for p in rows]
  assert all(map(math.isfinite,a+b+ak+bk));ki=[i for i,k in enumerate(bk) if abs(k)>.05];ka=[ak[i] for i in ki];kb=[bk[i] for i in ki];rmse=math.sqrt(statistics.mean((v-w)**2 for v,w in zip(a,b)))
  return {'n':len(a),'n_tke':len(ki),'FAC2':statistics.mean(.5*w<=v<=2*w for v,w in zip(a,b)),'q_abs025':statistics.mean(abs(v-w)<=.25 for v,w in zip(a,b)),'q_rel025':statistics.mean(abs(v-w)<=.25*abs(w) for v,w in zip(a,b)),'r':pearson(a,b),'NRMSE_range':rmse/(max(b)-min(b)),'NRMSE_mean':rmse/statistics.mean(b),'TKE_FAC2':statistics.mean(.5*w<=v<=2*w for v,w in zip(ka,kb)),'TKE_r':pearson(ka,kb),'mean_ratio':statistics.mean(a)/statistics.mean(b),'mixed_solid':sum(p[var]['fluid_corners']<8 for p in rows),'below_first_center':sum(p[var]['below_first_center'] for p in rows)}
 results={'primary':{},'diagnostic':{}}
 for setkey,table in [('primary',groups),('diagnostic',diagnostic)]:
  for key,rows in table.items():results[setkey][key]={var:metrics(rows,var) for var in ('no_shift','selected')}
 (out/'metrics_r9_dx10_v2.json').write_text(json.dumps(results,indent=2,allow_nan=False))
 # Bounded per-plane little-endian float32 NPY/gzip, 0b-compatible field set.
 fields=[('u',offset,3,0),('v',offset,3,1),('w',offset,3,2),('k',tke,1,0),('fluid',fluid,1,0)];files={}
 for name,src,components,component in fields:
  dst=out/f'dx10_{name}.npy.gz'
  with dst.open('xb') as fd, gzip.GzipFile(fileobj=fd,mode='wb',compresslevel=3,mtime=0) as gz:
   header=json.dumps({'descr':'<f4','fortran_order':False,'shape':(nz,ny,nx)},separators=(',',':'))
   # NPY v1.0 dictionary header (not JSON), 16-byte aligned.
   h=str({'descr':'<f4','fortran_order':False,'shape':(nz,ny,nx)})
   hb=(h+' '*((-len(h)-11)%16)+'\n').encode('latin1');gz.write(b'\x93NUMPY\x01\x00'+struct.pack('<H',len(hb))+hb)
   for k in range(nz):
    plane=[]
    for j in range(ny):
     for i in range(nx):
      val=scalar(src,i,j,k) if components==1 else vec(i,j,k)[component]
      assert math.isfinite(val),(name,k,i,j)
      plane.append(val)
    gz.write(struct.pack('<'+str(len(plane))+'f',*plane))
  assert dst.stat().st_size<200_000_000
  files[name]={'path':str(dst),'bytes':dst.stat().st_size,'sha256':sha(dst)}
 m.close()
(out/'meta.json').write_text(json.dumps({'source_vtk':str(path),'dims_xyz':[nx,ny,nz],'origin_xyz_m':origin,'spacing_xyz_m':[spacing]*3,'stats':{'run_nstep':6400,'purge_avg_steps':4400,'stride_steps':8,'sample_count':550},'fields':files,'quantity_definition':{'u/v/w':'time-mean m/s','k':'resolved TKE m2/s2','fluid':'VTK scalar; NOT native flags'},'height_rule':'real = label - dx/2'},indent=2))
print('POST_DONE',len(files),len(groups),len(diagnostic))
