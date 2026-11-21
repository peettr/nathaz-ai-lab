"""Format-only BG binary STL/deck staging from fixed C38 polygons; no solver."""
from pathlib import Path
import csv,hashlib,json,struct,tarfile,math
ROOT=Path(__file__).resolve().parents[2]; BASE=Path(__file__).resolve().parent
SRC=ROOT.parent/'38_Collaborative_Research_Lab/06_Work/C38.2/data_DiB2021_derived'
CONF=(ROOT/'06_Logs/caseA_r9_2m_tacc_v2/stage/caseA/conf.luwpf').read_text()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def box(lo,hi):
 x,y,z=lo;X,Y,Z=hi;v=[(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
 sides=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
 return [tuple(v[i] for i in tri) for a,b,c,d in sides for tri in ((a,b,c),(a,c,d))]
def parse_shape(path):
 data=path.read_bytes();off=100;out=[]
 while off<len(data):
  num,size=struct.unpack_from('>2i',data,off);content=data[off+8:off+8+size*2];typ=struct.unpack_from('<i',content)[0];assert typ==5
  countparts,n=struct.unpack_from('<2i',content,36);assert countparts==1 and n==5
  pts=[struct.unpack_from('<2d',content,44+4*countparts+i*16) for i in range(n)]
  assert pts[0]==pts[-1] and len({*pts})==4
  xs={p[0] for p in pts};ys={p[1] for p in pts};assert len(xs)==len(ys)==2
  out.append((min(xs),max(xs),min(ys),max(ys)))
  off+=8+size*2
 assert off==len(data) and len(out)==9
 return out
def dbf_heights(p):
 data=p.read_bytes();count=struct.unpack_from('<I',data,4)[0];header,record=struct.unpack_from('<2H',data,8);assert count==9
 return [float(data[header+i*record+1:header+(i+1)*record].decode('ascii').strip()) for i in range(count)]
def stage(which,domain,steps,avg,stride):
 O=BASE/which/'stage';assert not O.exists(),O
 O.mkdir();C=O/which;(C/'proj_temp').mkdir(parents=True);(C/'wind_bc').mkdir()
 polys=parse_shape(SRC/f'bg_{which[3:]}.shp');heights=dbf_heights(SRC/f'bg_{which[3:]}.dbf')
 w,h,t=domain;tris=box((0,0,-20),(w,h,0))
 for (x1,x2,y1,y2),z in zip(polys,heights):tris+=box((x1+w/2,y1+h/2,0),(x2+w/2,y2+h/2,z))
 stl=C/'proj_temp'/f'{which}_PF.stl'
 with stl.open('xb') as f:
  f.write(b'BG binary STL'.ljust(80,b'\0'));f.write(struct.pack('<I',len(tris)))
  for a,b,c in tris:
   ax,ay,az=a;bx,by,bz=b;cx,cy,cz=c
   u=(by-ay)*(cz-az)-(bz-az)*(cy-ay);v=(bz-az)*(cx-ax)-(bx-ax)*(cz-az);q=(bx-ax)*(cy-ay)-(by-ay)*(cx-ax);norm=math.sqrt(u*u+v*v+q*q);assert norm
   f.write(struct.pack('<12fH',u/norm,v/norm,q/norm,*a,*b,*c,0))
 assert stl.stat().st_size==84+50*len(tris) and len(tris)==120
 inflow=list(csv.DictReader((SRC/'bg_inflow.csv').open()))
 assert all(float(inflow[i]['z_m'])<float(inflow[i+1]['z_m']) for i in range(len(inflow)-1))
 # Hold nearest measured value at and above the source-table top; source begins at z=3 m.
 (C/'wind_bc/profile.dat').write_text('z U\n'+''.join(f"{float(r['z_m']):.9f} {3.1*float(r['U_over_UH']):.9f}\n" for r in inflow))
 edits=[('CaseA',which),('1088.000000',f'{w:.6f}'),('704.000000',f'{h:.6f}'),('384.000000',f'{t:.6f}'),('run_nstep = 32000',f'run_nstep = {steps}'),('purge_avg = 22000',f'purge_avg = {avg}'),('purge_avg_stride = 40',f'purge_avg_stride = {stride}')]
 conf=CONF
 for old,new in edits:assert conf.count(old)==1,(old,conf.count(old));conf=conf.replace(old,new)
 (C/'conf.luwpf').write_text(conf)
 points=[r for r in csv.DictReader((SRC/'bg_points.csv').open()) if r['cfg']==which[3:]]
 assert len(points)==(195 if which=='BG_1H' else 200)
 with (O/'bg_points.csv').open('x',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=points[0].keys());writer.writeheader();writer.writerows(points)
 m={'case':which,'domain_m':domain,'steps':steps,'mean_window':avg,'stride':stride,'UH_mps':3.1,'UH_height_m':20,'stl_triangles':len(tris),'building_heights_m':heights,'coordinate_transform':f'x_LUW=x_C38+{w/2}; y_LUW=y_C38+{h/2}','inlet_top_rule':'hold last measured value; inlet z is full-scale metres','input_sha256':{p.name:sha(p) for p in (SRC/f'bg_{which[3:]}.shp',SRC/f'bg_{which[3:]}.dbf',SRC/'bg_inflow.csv',SRC/'bg_points.csv')},'output_sha256':{str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file()}}
 (O/'manifest.json').write_text(json.dumps(m,indent=2));tar=BASE/which/'bg_stage.tar.gz'
 with tarfile.open(tar,'w:gz') as f:
  for p in sorted(O.rglob('*')):
   if p.is_file():f.add(p,arcname=str(p.relative_to(O)))
 print(which,tar,sha(tar),m)
stage('BG_1H',(340,220,120),14487,9960,18)
stage('BG_3H',(1020,660,360),43461,29880,54)
