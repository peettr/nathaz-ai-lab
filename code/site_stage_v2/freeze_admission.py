"""Freeze v2 admission before any ERA5-station pairing. Run on Colab only."""
import csv,json,datetime as dt,collections
from pathlib import Path
root=Path('/content/site_stage_v2');meta=list(csv.DictReader((root/'static_gates.csv').open()));p=root/'station_only_seasons_corrected.jsonl';obs=[json.loads(s) for s in p.read_text().splitlines()]
by=collections.defaultdict(dict)
for x in obs:
 k=(x['station'],x['season_year'])
 if x['season_year'] in by[x['station']]:raise ValueError(('duplicate',k))
 by[x['station']][x['season_year']]=x
assert len(obs)==44*15,(len(obs),'incomplete; no admission file written')
assert all(len(by[r['station']])==15 for r in meta)
now=dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).isoformat(timespec='seconds')
out=[]
for r in meta:
 s=r['station'];sea=by[s];n=sum(bool(sea[y].get('valid')) for y in range(2007,2022));errors=[y for y in range(2007,2022) if sea[y].get('error')];reasons=[]
 for k in ['instrument_ok','relocation_ok','elevation_ok','geog_ok','land_ok']:
  if r.get(k)!='true':reasons.append(k)
 if n<12:reasons.append('valid_seasons_lt12')
 if errors:reasons.append('unresolved_download_errors')
 out.append({'station':s,'region':r['region'],'admission_generated_edt':now,'admitted':str(not reasons).lower(),'reasons':';'.join(reasons),'valid_seasons':n,'observed_seasons':15,'error_seasons':json.dumps(errors),'instrument_ok':r.get('instrument_ok'),'relocation_ok':r.get('relocation_ok'),'elevation_m':r.get('elev_m'),'elevation_ok':r.get('elevation_ok'),'coast_km':r.get('coast_km'),'great_lake_km':r.get('great_lake_km'),'geog_ok':r.get('geog_ok'),'ace_lat':r.get('ace_lat'),'ace_lon':r.get('ace_lon'),'ace_iy':r.get('ace_iy'),'ace_ix':r.get('ace_ix'),'land_fraction':r.get('land_fraction'),'land_ok':r.get('land_ok'),'homr_url':r.get('source_url'),'land_url':'gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr'})
path=root/'station_admission.csv'
assert not path.exists(),'freeze once; never overwrite'
with path.open('x',newline='') as f:w=csv.DictWriter(f,list(out[0]));w.writeheader();w.writerows(out)
for g in ('plains','other'):
 print('ADMITTED',g,[r['station'] for r in out if r['region']==g and r['admitted']=='true'],flush=True)
print('FROZEN',str(path),now,flush=True)
