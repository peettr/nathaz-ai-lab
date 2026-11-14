#!/usr/bin/env python3
"""Compute common pressure coordinate from native GRIB inventories, not documentation."""
import json
from pathlib import Path
R=Path(__file__).resolve().parent
GC37=[1,2,3,5,7,10,20,30,50,70,100,125,150,175,200,225,250,300,350,400,450,500,550,600,650,700,750,775,800,825,850,875,900,925,950,975,1000]
all_levels=[]
lines=['NCAR GDEX d084001 GFS 0.25° raw GRIB pressure-layer inventory; 2026-11-12 EST',
       'Evidence: per-cycle *_pilot_inventory.json, downloaded original GRIB SHA256/size therein.',
       'Five complete WRF fields: gh,t,u,v and derived q from native relative humidity r plus T (native q unavailable).',
       'Values below are hPa. Record is based on real GRIB message headers of all three t0 f000 files; no historical WPS proxy.','']
for c in ('2020060606','2020060706','2020060806'):
 d=json.loads((R/f'{c}_pilot_inventory.json').read_text())
 f=f'gfs.0p25.{c}.f000.grib2';inv=d['inventory'][f]['isobaric_hpa']
 required=('gh','t','u','v','r')
 for v in required: assert v+'/isobaricInhPa' in inv,(c,v)
 common=set.intersection(*(set(inv[v+'/isobaricInhPa']) for v in required))
 all_levels.append(common)
 lines += [f'{c} f000 sha256 {next(x["sha256"] for x in d["retrieval"] if x["file"].endswith(f))}',
           f'  gh {len(inv["gh/isobaricInhPa"])}; t {len(inv["t/isobaricInhPa"])}; u {len(inv["u/isobaricInhPa"])}; v {len(inv["v/isobaricInhPa"])}; r {len(inv["r/isobaricInhPa"])}',
           f'  complete {len(common)}: '+', '.join(map(str,sorted(common,reverse=True))),'']
assert all(x==all_levels[0] for x in all_levels), 'cycle pressure lists disagree'
actual=all_levels[0]
(R/'GFS_202006_levels_ACTUAL.txt').write_text('\n'.join(lines)+f'All-cycle actual complete levels {len(actual)}: '+', '.join(map(str,sorted(actual,reverse=True)))+'\n')
shared=actual.intersection(GC37)
(R/'GC37_GFS_common_levels_ACTUAL.txt').write_text('GC37 ∩ GFS 2020 raw GRIB complete level list, hPa.\n'+'Evidence: GFS_202006_levels_ACTUAL.txt and GC37 official weight model coordinate (model output still unverified).\n'+f'{len(shared)} levels descending: '+', '.join(map(str,sorted(shared,reverse=True)))+'\n'+f'GC37 missing in GFS: '+', '.join(map(str,sorted(set(GC37)-actual,reverse=True)))+'\n')
print('actual',len(actual), sorted(actual,reverse=True));print('shared',len(shared),sorted(shared,reverse=True))
