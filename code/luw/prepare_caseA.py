"""Prepare official AIJ Case A observations and a single-building binary STL."""
import json, math, struct
from pathlib import Path
import xlrd
root=Path(__file__).parent
book=xlrd.open_workbook(str(root/'aij_caseA_official/CaseA(1_1_2).xls'))
B=32.; UH=4.491
rows={}
for key,s in zip(('vertical','z8','z80'),book.sheets()[2:]):
    pts=[]
    for i in range(2,s.nrows):
        r=s.row_values(i)
        if not isinstance(r[1],(int,float)):continue
        zratio=1.25 if key=='z80' else r[3] # official high-plane worksheet has erroneous z/b=0.125 in all cells
        pts.append(dict(id=int(r[0]),x_b=r[1],y_b=r[2],z_b=zratio,x=352+B*r[1],y=352+B*r[2],z=B*zratio,uvw=r[4:7],speed=math.sqrt(sum(t*t for t in r[4:7]))/UH,k=r[10]/UH**2))
    rows[key]=pts
assert [len(rows[k]) for k in ('vertical','z8','z80')]==[66,60,60]
(root/'caseA_observations.json').write_text(json.dumps({'source':'AIJ CaseA(1_1_2).xls','UH':UH,'B':B,'high_plane_note':'Worksheet z/b cells say 0.125 while title says 1.25; use title, paper and values as z=80 m; ASSUMPTION pending independent drawing check','groups':rows},indent=2))
# STL geometry: 32x32x64 prism center x=y=352, ground z=0; base z=-20..0.
def box(x0,x1,y0,y1,z0,z1):
    v=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    for a,b,c,d in faces:
        for ids in ((a,b,c),(a,c,d)):
            p,q,r=(v[j] for j in ids);u=[q[j]-p[j] for j in range(3)];w=[r[j]-p[j] for j in range(3)]
            n=(u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]);ln=math.sqrt(sum(t*t for t in n));yield tuple(t/ln for t in n),p,q,r
tris=list(box(336,368,336,368,0,64))+list(box(0,1088,0,704,-20,0))
p=root/'CaseA_PF_caseA.stl'
with p.open('wb') as f:
    f.write(b'LUW AIJ Case A 1:1:2 B=32 H=64'.ljust(80,b' '));f.write(struct.pack('<I',len(tris)))
    for n,a,b,c in tris:f.write(struct.pack('<12fH',*(n+a+b+c),0))
profile=root/'profile_caseA.dat'
s=book.sheet_by_name('Inflow')
with profile.open('w') as f:
    f.write('z U\n')
    for i in range(2,s.nrows):f.write(f'{s.cell_value(i,1)*B:.6f} {s.cell_value(i,2):.6f}\n')
    f.write('384.000000 6.751000\n')
print('groups', {k:len(v) for k,v in rows.items()},'stl triangles',len(tris),'profile',profile,'UH xls',s.cell_value(11,2))
