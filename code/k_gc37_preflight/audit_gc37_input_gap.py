#!/usr/bin/env python3
"""Compare original GraphCast checkpoint input levels to native NCAR GRIB records."""
import json, hashlib
from pathlib import Path
R=Path(__file__).resolve().parent
GC37=[1,2,3,5,7,10,20,30,50,70,100,125,150,175,200,225,250,300,350,400,450,500,550,600,650,700,750,775,800,825,850,875,900,925,950,975,1000]
rows=[]
for cycle in ('2020060606','2020060706','2020060806'):
 d=json.loads((R/f'{cycle}_pilot_inventory.json').read_text())
 for x in d['retrieval']:
  inv=d['inventory'][Path(x['file']).name]
  row={'cycle':cycle,'file':Path(x['file']).name,'url':x['url'],'sha256':x['sha256'],'bytes':x['bytes'],'fields':{}}
  for key in ('gh','t','u','v','r','w'):
   levels=inv['isobaric_hpa'].get(key+'/isobaricInhPa',[])
   row['fields'][key]={'native_levels_hpa':levels,'missing_graphcast_levels_hpa':sorted(set(GC37)-set(levels))}
  row['precip_6h_accum_count']=sum(y['shortName']=='tp' and y['startStep']==0 and y['endStep']==6 and y['stepType']=='accum' for y in inv['precipitation'])
  rows.append(row)
out={'graphcast_checkpoint':'GraphCast - ERA5 1979-2017 - resolution 0.25 - pressure levels 37 - mesh 2to6 - precipitation input and output.npz','checkpoint_sha256':'4e8cf600f3f402ebb430483e782b94648cef57bb757dec24dd7b11760d3fbacc','checkpoint_actual_input_requires':'vertical_velocity at all 37 pressure levels; t-6h and t0','rows':rows,'status':'STOP: w absent at upper 1,2,3,5,7,10,20,30,50,70 hPa in all six f000 initial-state files; six additional intermediate levels absent; cannot source exact GFS w from NCAR d084001; no silent zero-fill or GDAS substitution.'}
p=R/'NATIVE_GRIB_GC37_INPUT_GAP.json';p.write_text(json.dumps(out,indent=2),encoding='utf8')
print(out['status']);print('rows',len(rows));print('sha256',hashlib.sha256(p.read_bytes()).hexdigest())
