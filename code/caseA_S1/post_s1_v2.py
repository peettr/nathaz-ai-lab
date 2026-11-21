#!/usr/bin/env python3
"""Frozen Case A S1: wall-relative sampling, first-fluid clamp, solid exclusion."""
import array, gzip, hashlib, itertools, json, math, statistics, sys
from pathlib import Path

ROOT=Path(sys.argv[1]); OUT=ROOT/'out'; OUT.mkdir(exist_ok=False)
SRC=ROOT/'sources.json'
sources=json.loads(SRC.read_text()); obs=json.loads((ROOT/'caseA_observations_official.json').read_text())
assert set(sources)=={'dx2','dx4','dx10'} and obs['UH']>0

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1<<20),b''):h.update(block)
 return h.hexdigest()

def load(path,shape,expected):
 assert path.stat().st_size>0 and sha(path)==expected,(str(path),'SHA mismatch')
 with gzip.open(path,'rb') as f:
  import ast,struct
  magic=f.read(8)
  assert magic[:6]==b'\x93NUMPY' and magic[6:] in (b'\x01\x00',b'\x02\x00'),(path,magic)
  size_fmt='<H' if magic[6]==1 else '<I'
  header=ast.literal_eval(f.read(struct.unpack(size_fmt,f.read(struct.calcsize(size_fmt)))[0]).decode('latin1' if magic[6]==1 else 'utf8'))
  assert header['descr']=='<f4' and header['fortran_order'] is False and tuple(header['shape'])==tuple(shape),(path,header)
  vals=array.array('f'); vals.frombytes(f.read())
 assert len(vals)==math.prod(shape)
 if sys.byteorder!='little': vals.byteswap()
 return vals

def pearson(a,b):
 if len(a)<2:return None
 av=statistics.mean(a);bv=statistics.mean(b);den=math.sqrt(sum((x-av)**2 for x in a)*sum((x-bv)**2 for x in b))
 return sum((x-av)*(y-bv) for x,y in zip(a,b))/den if den else None

def metrics(rows):
 if not rows:return None
 a=[p['speed'] for p in rows];b=[p['obs_speed'] for p in rows];ak=[p['k'] for p in rows];bk=[p['obs_k'] for p in rows]
 assert all(math.isfinite(x) for x in a+b+ak+bk)
 ids=[i for i,x in enumerate(bk) if abs(x)>.05];ka=[ak[i] for i in ids];kb=[bk[i] for i in ids]
 rmse=math.sqrt(statistics.mean((x-y)**2 for x,y in zip(a,b)))
 return {'n':len(rows),'n_tke':len(ids),'FAC2':statistics.mean(.5*y<=x<=2*y for x,y in zip(a,b)),'q_abs025':statistics.mean(abs(x-y)<=.25 for x,y in zip(a,b)),'q_rel025':statistics.mean(abs(x-y)<=.25*abs(y) for x,y in zip(a,b)),'r':pearson(a,b),'NRMSE_range':rmse/(max(b)-min(b)) if max(b)>min(b) else None,'NRMSE_mean':rmse/statistics.mean(b) if statistics.mean(b) else None,'TKE_FAC2':statistics.mean(.5*y<=x<=2*y for x,y in zip(ka,kb)) if ids else None,'TKE_r':pearson(ka,kb),'mean_ratio':statistics.mean(a)/statistics.mean(b) if statistics.mean(b) else None}

report={'rule':'S1 frozen 11-11 20:40: target AGL from measured effective ground; below first fluid center clamp to that center; exclude any positive-weight solid interpolation corner; horizontal IoU; >=80% un-clamped and unmixed for all three grids per group','source_manifest_sha256':sha(SRC),'observation_sha256':sha(ROOT/'caseA_observations_official.json'),'grids':{},'comparison':{}}
for grid in ('dx2','dx4','dx10'):
 cfg=sources[grid];base=Path(cfg['base']);meta=json.loads(Path(cfg['meta']).read_text());info=meta[grid] if grid!='dx10' else meta
 shape=info['array_shape_zyx'];nz,ny,nx=shape; origin=info['origin_xyz_m'];dx=info['spacing_xyz_m'][0]
 assert all(abs(d-dx)<1e-8 for d in info['spacing_xyz_m'])
 index=lambda i,j,k:i+nx*(j+ny*k)
 files=info['quantities'] if grid!='dx10' else info['fields']
 data={name:load(base/f'{grid}_{name}.npy.gz',shape,files[name]['sha256']) for name in ('fluid','u','v','w','k')}
 def value(name,i,j,k):return data[name][index(i,j,k)]
 # The open-ground columns must agree; skip the sealed k=1 dead layer.
 columns=[]
 for x,y in ((100,100),(160,200),(500,500),(600,160)):
  i=round((x-origin[0])/dx);j=round((y-origin[1])/dx)
  assert 1<i<nx-2 and 1<j<ny-2
  candidates=[k for k in range(2,nz) if value('fluid',i,j,k)>.5]
  assert candidates,(grid,x,y)
  k0=candidates[0];assert value('fluid',i,j,k0-1)<.5
  columns.append({'xy_m':[x,y],'first_fluid_k':k0,'first_fluid_label_m':origin[2]+dx*k0})
 assert len({c['first_fluid_k'] for c in columns})==1,(grid,columns)
 first=columns[0]['first_fluid_k'];wall=origin[2]+dx*(first-.5);first_agl=dx/2
 assert first=={'dx2':11,'dx4':6,'dx10':3}[grid],(grid,columns)
 # Freeze registration on IoU, never select by velocity error.
 masks=[]
 for sx,sy in itertools.product((0.,dx),repeat=2):
  tp=fp=fn=0
  for x in range(322,384,2):
   for y in range(322,384,2):
    i=min(nx-1,max(0,round((x-origin[0])/dx)));j=min(ny-1,max(0,round((y-origin[1])/dx)));k=min(nz-1,max(0,round((32-origin[2])/dx)))
    solid=value('fluid',i,j,k)<.5;inside=336<=x-sx<368 and 336<=y-sy<368
    tp+=bool(solid and inside);fp+=bool(solid and not inside);fn+=bool(inside and not solid)
  masks.append({'shift_xy_m':[sx,sy],'tp':tp,'fp':fp,'fn':fn,'iou':tp/(tp+fp+fn) if tp+fp+fn else None})
 best=sorted(masks,key=lambda q:(-q['iou'],q['shift_xy_m']))[0];shift=best['shift_xy_m']
 def sample(x,y,z):
  xyz=[(v-o)/dx for v,o in zip((x,y,z),origin)];ids=[math.floor(v) for v in xyz];frac=[v-i for v,i in zip(xyz,ids)]
  assert all(0<=i<n-1 for i,n in zip(ids,(nx,ny,nz))),(grid,x,y,z,ids)
  sums={n:0. for n in ('u','v','w','k')};solid=[]
  for q in range(8):
   t=[(q>>d)&1 for d in range(3)];weight=math.prod(frac[d] if t[d] else 1-frac[d] for d in range(3))
   if weight<=1e-12:continue  # zero-weight neighbors are not interpolation corners
   i,j,k=(ids[d]+t[d] for d in range(3))
   if value('fluid',i,j,k)<.5:solid.append([i,j,k])
   for n in sums:sums[n]+=weight*value(n,i,j,k)
  assert all(math.isfinite(v) for v in sums.values())
  return {'speed':math.sqrt(sum(sums[n]**2 for n in ('u','v','w')))/obs['UH'],'k':sums['k']/obs['UH']**2,'solid_corners':solid,'label_m':z,'actual_agl_m':z-wall}
 groups={}
 for group,pts in obs['groups'].items():
  rows=[]
  for p in pts:
   target=p['z'];actual=max(target,first_agl);clamped=target<first_agl-1e-9
   got=sample(p['x']+shift[0],p['y']+shift[1],wall+actual)
   rows.append({'id':p['id'],'coord_m':[p['x'],p['y'],target],'obs_speed':p['speed'],'obs_k':p['k'],'speed':got['speed'],'k':got['k'],'label_m':got['label_m'],'actual_agl_m':got['actual_agl_m'],'clamped':clamped,'solid_corners':got['solid_corners']})
  unmixed=[r for r in rows if not r['solid_corners']];clean=[r for r in unmixed if not r['clamped']]
  groups[group]={'total':len(rows),'clamped':sum(r['clamped'] for r in rows),'mixed_solid':len(rows)-len(unmixed),'unclamped_unmixed':len(clean),'unclamped_unmixed_fraction':len(clean)/len(rows),'metrics_excluding_mixed':metrics(unmixed),'metrics_unclamped_unmixed':metrics(clean),'clamped_actual_agl_m':sorted({round(r['actual_agl_m'],8) for r in rows if r['clamped']}),'rows':rows}
 report['grids'][grid]={'shape_zyx':shape,'dx_m':dx,'origin_xyz_m':origin,'ground_label_m':wall,'first_fluid_agl_m':first_agl,'open_ground_columns':columns,'iou_candidates':masks,'selected_shift':best,'groups':groups,'source_fields_sha256':{n:files[n]['sha256'] for n in data}}
 print('GRID',grid,'ground',wall,'shift',shift,'groups',[(g,v['total'],v['clamped'],v['mixed_solid']) for g,v in groups.items()],flush=True)
 del data
for group,label in (('z8','4m'),('z80','40m'),('vertical','vertical')):
 all_comparable=all(report['grids'][g]['groups'][group]['unclamped_unmixed_fraction']>=.8 for g in report['grids'])
 report['comparison'][label]={'all_three_comparable':all_comparable,'grid_verdict':{g:'可比' if all_comparable else '不可比' for g in report['grids']}}
(OUT/'s1_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
print('S1_DONE',OUT/'s1_results.json',flush=True)
