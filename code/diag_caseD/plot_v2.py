#!/usr/bin/env python3
"""Read-only geometry/point visualization. Native fluid field is unavailable."""
from pathlib import Path
import json,zipfile,struct
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).parent
Z=R.parent/'CaseD_retry6_20261115_0411/caseD_result.zip'
B=R.parent/'CaseD_retry5_20261115_0242/stage/caseD/proj_temp/CaseD_PF.stl'
with zipfile.ZipFile(Z) as z:
 data=json.loads(z.read('pointvalues.json'));gate=json.loads(z.read('geometry_gate.json'))
raw=B.read_bytes();n=struct.unpack_from('<I',raw,80)[0];tri=[]
for k in range(n):
 q=struct.unpack_from('<12fH',raw,84+50*k)
 v=[(q[3+i*3],q[4+i*3],q[5+i*3]) for i in range(3)]
 if max(p[2] for p in v)-min(p[2] for p in v)<.001 and 9.5<=v[0][2]<=100.5:tri.append(v)
assert len(data['rows'])==99 and len(gate['open_columns'])==4
im=Image.new('RGB',(2000,1120),'white');d=ImageDraw.Draw(im)
font=ImageFont.load_default()
views=[('Full LUW domain (m)',(0,1700,0,1100),(55,65,970,875)),('Measurement district (m)',(750,960,475,665),(1050,65,1960,875))]
for title,(xmin,xmax,ymin,ymax),(l,t,r,b) in views:
 d.rectangle((l,t,r,b),outline='#222222',width=3)
 layer=Image.new('RGB',im.size,'white');draw=ImageDraw.Draw(layer)
 def xy(x,y):return (l+(x-xmin)/(xmax-xmin)*(r-l),b-(y-ymin)/(ymax-ymin)*(b-t))
 for verts in tri:
  color='#e7aa66' if verts[0][2]<20 else '#8849aa'
  draw.polygon([xy(x,y) for x,y,_ in verts],fill=color,outline='#bd8651')
 for p in data['rows']:
  x,y,_=p['luw_sample_xyz_m']; px,py=xy(x,y)
  if l<=px<=r and t<=py<=b:
   color='#116bc1' if p['kind']=='S' else '#127b45'
   draw.ellipse((px-5,py-5,px+5,py+5),fill=color,outline='white',width=1)
 for idx,col in enumerate(gate['open_columns'],1):
  px,py=xy(*col['xy'])
  if l<=px<=r and t<=py<=b:
   draw.line((px-11,py,px+11,py),fill='#d02e35',width=4);draw.line((px,py-11,px,py+11),fill='#d02e35',width=4)
   draw.text((px+12,py-14),f'G{idx}',fill='#d02e35',font=font)
 im.paste(layer.crop((l+2,t+2,r-2,b-2)),(l+2,t+2))
 d.text((l,t-28),title,fill='black',font=font)
 d.text((l,b+8),f'x {xmin}..{xmax}; y {ymin}..{ymax}; roofs: orange 10m, purple 100m',fill='black',font=font)
d.text((55,950),'Blue: split-fiber S; green: thermistor T; red +: four native-mask open-ground gate columns (G1..G4).',fill='black',font=font)
d.text((55,975),'Points: x_LUW=x_C38+850, y_LUW=y_C38+550; all AGL=2m; 99 fluid interpolation neighborhoods, 0 solid corners.',fill='black',font=font)
d.text((55,1000),'CAVEAT: full native fluid mask and time-mean 3D velocity field were NOT archived; roofs are input STL facets, not mask pixels.',fill='#a01818',font=font)
d.text((55,1025),'The four red columns and 99 fluid corner statuses come from archived native-mask gate / point extractor summaries.',fill='black',font=font)
out=R/'points_roofs_gate_columns_v3.png'
with out.open('xb') as f: im.save(f,format='PNG')
print(out, out.stat().st_size)
