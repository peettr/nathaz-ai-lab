#!/usr/bin/env python3
"""Stage Case C 0D/1D/2D decks; no solver or GPU work on 工作站."""
import csv, hashlib, json, math, pathlib, struct, tarfile
R=pathlib.Path(__file__).resolve().parent
SRC=pathlib.Path('./38_Collaborative_Research_Lab/06_Work/C38.2/data_caseC_derived')
AF=SRC.parent/'data_AIJ_CaseC_zenodo15401792/AF_caseC.csv'
BASE=R.parent/'C38.2_caseD_bg/BG_1H/stage/BG_1H/conf.luwpf'
DOM=(500,300,150);DX=2;N=tuple(v//DX for v in DOM)
assert tuple(v/d for v,d in zip(DOM,(DX,)*3))==N

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def box(lo,hi):
 x,y,z=lo;X,Y,Z=hi;v=[(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
 sides=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
 return [tuple(v[i] for i in tri) for a,b,c,d in sides for tri in ((a,b,c),(a,c,d))]
def shape(path):
 b=path.read_bytes();off=100;out=[]
 while off<len(b):
  _,words=struct.unpack_from('>2I',b,off);rec=b[off+8:off+8+2*words]
  assert struct.unpack_from('<I',rec)[0]==5
  parts,n=struct.unpack_from('<2I',rec,36);assert parts==1 and n==5
  pts=[struct.unpack_from('<2d',rec,48+16*i) for i in range(n)]
  assert pts[0]==pts[-1] and len(set(pts))==4
  out.append((min(x for x,y in pts),max(x for x,y in pts),min(y for x,y in pts),max(y for x,y in pts)))
  off+=8+2*words
 assert off==len(b)
 return out
def heights(path):
 b=path.read_bytes();count=struct.unpack_from('<I',b,4)[0];head,step=struct.unpack_from('<HH',b,8)
 fields=[];i=32
 while b[i]!=13:
  name=b[i:i+11].split(b'\0')[0].decode();fields.append((name,b[i+16]));i+=32
 rows=[]
 for j in range(count):
  row=b[head+j*step:head+(j+1)*step];pos=1;d={}
  for name,width in fields:d[name]=row[pos:pos+width].decode().strip();pos+=width
  rows.append(d)
 return rows

def run():
 manifest=json.loads((SRC/'SHA256.json').read_text());assert sha(SRC/'SHA256.json')=='35bc7bd6f31d7f0e116184097f104dbb52ca74a9da857c54c1ab4b899d683653'
 assert len(manifest)==15 and all(sha(SRC/k)==v for k,v in manifest.items())
 inflow=list(csv.DictReader(AF.open(encoding='utf-8-sig')));assert len(inflow)>10
 z=[float(q['z (m)'])*100 for q in inflow];u=[float(q['U (m/s)']) for q in inflow]
 assert all(a<b for a,b in zip(z,z[1:])) and z[-1]==120
 z.append(float(DOM[2]));u.append(u[-1])  # declared hold of last AF value above measured 120 m
 conf=BASE.read_text();summary={'input_manifest_sha256':sha(SRC/'SHA256.json'),'input_checks':len(manifest),'inflow_source':str(AF),'inflow_sha256':sha(AF),'physical_domain_m':DOM,'dx_m':DX,'grid':N,'grid_formula':'500/2=250; 300/2=150; 150/2=75','domain_choice':'preliminary engineering assumption; not established by Case C primary source','cases':{}}
 for label in ('0D','1D','2D'):
  name='caseC_'+label;shapes=shape(SRC/(name+'.shp'));h=heights(SRC/(name+'.dbf'))
  assert len(shapes)==len(h)==(8 if label=='0D' else 9)
  assert all('HEIGHT' in {k.upper() for k in row} for row in h),h[0]
  C=R/'stage_v2'/name;(C/'proj_temp').mkdir(parents=True,exist_ok=False);(C/'wind_bc').mkdir()
  tris=box((0,0,-20),(DOM[0],DOM[1],0));dims=[]
  for (x1,x2,y1,y2),rec in zip(shapes,h):
   height=float(next(v for k,v in rec.items() if k.upper()=='HEIGHT'))
   assert height in (20.,40.)
   tris+=box((x1+250,y1+150,0),(x2+250,y2+150,height));dims.append(height)
  stl=C/'proj_temp'/(name+'_PF.stl')
  with stl.open('xb') as f:
   f.write(b'Case C binary STL'.ljust(80,b'\0'));f.write(struct.pack('<I',len(tris)))
   for a,b,c in tris:
    ax,ay,az=a;bx,by,bz=b;cx,cy,cz=c
    vx=(by-ay)*(cz-az)-(bz-az)*(cy-ay);vy=(bz-az)*(cx-ax)-(bx-ax)*(cz-az);vz=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax);norm=math.sqrt(vx*vx+vy*vy+vz*vz);assert norm>0
    f.write(struct.pack('<12fH',vx/norm,vy/norm,vz/norm,*a,*b,*c,0))
  assert stl.stat().st_size==84+50*len(tris)
  (C/'wind_bc/profile.dat').write_text('z U\n'+''.join(f'{a:.9f} {b:.9f}\n' for a,b in zip(z,u)))
  deck=conf
  for old,new in [('BG_1H',name),('340.000000','500.000000'),('220.000000','300.000000'),('120.000000','150.000000')]:
   assert deck.count(old)==1,(old,deck.count(old));deck=deck.replace(old,new)
  (C/'conf.luwpf').write_text(deck)
  points=list(csv.DictReader((SRC/(name+'_points.csv')).open()));assert len(points)==120 and len({r['point_id'] for r in points})==120
  summary['cases'][label]={'n_buildings':len(shapes),'building_heights_m':dims,'n_points':len(points),'stl_sha256':sha(stl),'deck_sha256':sha(C/'conf.luwpf'),'profile_sha256':sha(C/'wind_bc/profile.dat'),'points_sha256':manifest[name+'_points.csv']}
  with tarfile.open(R/(name+'.tar.gz'),'w:gz') as tar:
   for p in sorted(C.rglob('*')):
    if p.is_file():tar.add(p,arcname=str(p.relative_to(R/'stage_v2')))
  summary['cases'][label]['tar_sha256']=sha(R/(name+'.tar.gz'))
 (R/'STAGING.json').write_text(json.dumps(summary,indent=2))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
