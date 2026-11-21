#!/usr/bin/env python3
"""Adapt T3c orchestration to a new immutable T3d run root."""
from pathlib import Path
import re
R=Path(__file__).resolve().parent;old=R.parent/'T3c'
files=['controller_t3c.py','remote_worker_t3c.py','launch_t3c.py','check_t3c.py','ack_t3c.py','analyze_t3c.py']
cases=['dx1p0_s107','dx0p5_s107','dx1p0_s108','dx0p5_s108','dx1p0_s109','dx0p5_s109']
oldtuple="('dx1p0_s105','dx0p5_s105','dx1p0_s106','dx0p5_s106')"
newtuple='('+','.join(repr(c) for c in cases)+')'
for name in files:
 text=(old/name).read_text()
 if name in ('controller_t3c.py','remote_worker_t3c.py','ack_t3c.py','analyze_t3c.py'):assert oldtuple in text,(name,'case list')
 text=text.replace(oldtuple,newtuple)
 text=text.replace('t3_t3c','t3_t3d').replace('t3c','t3d').replace('T3C','T3D')
 if name=='controller_t3c.py':
  text=text.replace('luw-r214a-t3d-r2-1116','luw-r214a-t3d-1116')
  text=text.replace('sessions-t3d-r2.json','sessions-t3d.json')
  text=text.replace('return len(acked)==4','return len(acked)==6')
  # Sized deadline: total cap 50 CU, 2 CU held as safety margin.
  text=text.replace('start+(42/rate)*3600','start+(48/rate)*3600')
  text=text.replace("'--expect-hours','8','--max-hours','9'","'--expect-hours','8','--max-hours','9'")
  text=text.replace('T3d_r2 #new','T3d #1be9fcce')
  # Separate the actual VM creation clock from allocation refusal time as in predecessor.
 if name=='remote_worker_t3c.py':
  text=text.replace("'avg_samples_expected':500","'avg_samples_expected':1500")
  text=text.replace('ref=1730*(c[\'cells_total\']/(500*500*470))*(c[\'steps\']/31000)',"ref=1.25*(200 if c['dx']==1.0 else 3000)*(c['steps']/(31000 if c['dx']==1.0 else 62000))")
  text=text.replace('time.time()+2*ref+900>deadline','time.time()+ref+1200>deadline')
 if name=='ack_t3c.py':
  text=text.replace("assert case in ('dx1p0_s107','dx0p5_s107','dx1p0_s108','dx0p5_s108')",'assert case in '+newtuple)
 if name=='analyze_t3c.py':
  text=text.replace('(105,106)','(107,108,109)')
  text=text.replace("abs(Qs['105']-Qs['106'])>.02","False")
  text=text.replace("abs(Qs['105']-Qs['106']) if all(v is not None for v in Qs.values()) else None","max(Qs.values())-min(Qs.values()) if all(v is not None for v in Qs.values()) else None")
  text=text.replace("elif Q>=1.06:verdict=", "elif all(v>=1.06 for v in Qs.values()):verdict=")
  text=text.replace("elif Q<=1.03:verdict=", "elif all(v<=1.03 for v in Qs.values()):verdict=")
  text=text.replace("else:verdict='不判：1.03 < Q < 1.06；本轮不判，交 Lead 决策'","else:verdict='中间，未区分；不再加种子'")
  text=text.replace('vals[:2])/statistics.mean(vals[2:])','vals[:3])/statistics.mean(vals[3:])')
  text=text.replace("Qs['105']-Qs['106']","Qs['107']-Qs['108']")
  text=text.replace("'不判：种子差 >0.02；本轮不判，交 Lead 决策'","'中间，未区分'")
  # The old curve indexes and pre-registered x sites are unchanged.
 dest=R/name.replace('t3c','t3d')
 if dest.exists():assert dest.read_text()==text,('partial generation mismatch',dest)
 else:dest.write_text(text)
 for predecessor in ('t3c','T3C','s105','s106'):
  if predecessor in text and predecessor in ('t3c','T3C'):raise AssertionError((name,predecessor))
print('generated',len(files),'case count',len(cases))
