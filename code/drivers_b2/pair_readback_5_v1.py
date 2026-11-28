#!/usr/bin/env python3
"""Read-only partial-cycle paired WPS audit; never writes driver data."""
import sys,json,datetime as dt,hashlib,pathlib
from readback_gc37x_b2 import P,records,coverage,SHARED
cfg=json.loads((P/'inputs_N8N9N10_v1'/'event_times_bbox_gc37x.json').read_text())['events']
result={}
for event,lead in [('N8',24),('N8',48),('N9',24),('N9',48),('N10',24)]:
 root=P/f'drivers_{event}_v1';spec=cfg[event]['leads'][f'{lead}h'];cycle=dt.datetime.fromisoformat(spec['t0']).strftime('%Y%m%d%H')
 n=spec['length_h']//6+1
 aa=sorted((root/'AI'/cycle).glob('FILE:*'));gg=sorted((root/'GFS'/cycle).glob('FILE:*'))
 assert len(aa)==len(gg)==n,(event,cycle,len(aa),len(gg),n)
 assert [p.name for p in aa]==[p.name for p in gg]
 grid=None
 for i,(a,g) in enumerate(zip(aa,gg)):
  ar,ag=records(a);gr,bg=records(g);assert ag==bg
  assert all(ar[(f,200100)]==gr[(f,200100)] for f in SHARED)
  if i==0:assert hashlib.sha256(a.read_bytes()).digest()==hashlib.sha256(g.read_bytes()).digest(),(event,cycle,'t0')
  grid=ag
 cov=coverage(cfg[event]['domain'],grid)
 result[f'{event}_{lead}h']={'cycle':cycle,'pairs':n,'five_fields_31_levels_finite':True,'shared_12_byte_identical':True,'t0_identical':True,'d01_min_margin_deg':cov['minimum_margin_deg']}
print(json.dumps(result,ensure_ascii=False,indent=2))
