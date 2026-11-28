#!/usr/bin/env python3
"""Read native NCAR GDEX GFS GRIB on Colab; no local large files."""
import hashlib, json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
import requests
import pygrib

ROOT = Path('/content/r234c_gc37_310e5531')
ROOT.mkdir(exist_ok=True)
CYCLES = ('2020060606', '2020060706', '2020060806')
URL = 'https://osdf-director.osg-htc.org/ncar/gdex/d084001/2020/{date}/gfs.0p25.{cycle}.f{lead:03}.grib2'

def fetch(cycle, lead):
    name = f'gfs.0p25.{cycle}.f{lead:03}.grib2'
    path = ROOT / name
    if path.exists():
        raise RuntimeError('refuse to overwrite existing '+str(path))
    url = URL.format(date=cycle[:8], cycle=cycle, lead=lead)
    start = time.monotonic()
    with requests.get(url, stream=True, timeout=(20, 90)) as response:
        response.raise_for_status()
        length = int(response.headers['Content-Length'])
        sha = hashlib.sha256(); written = 0
        with path.open('xb') as out:
            for chunk in response.iter_content(2**20):
                if chunk:
                    sha.update(chunk); out.write(chunk); written += len(chunk)
                    if written // (100*2**20) != (written-len(chunk)) // (100*2**20):
                        print('FETCH',name,written,length,'sec',round(time.monotonic()-start,1),flush=True)
    assert written == length and path.stat().st_size == length, (name,written,length)
    with path.open('rb') as f: assert f.read(4) == b'GRIB'
    return {'url':url,'file':str(path),'bytes':written,'sha256':sha.hexdigest(),'download_seconds':round(time.monotonic()-start,2)}

def inventory(path):
    fields = {}; all_records = 0; apcp = []
    with pygrib.open(str(path)) as messages:
        for grb in messages:
            all_records += 1
            key = f'{grb.shortName}/{grb.typeOfLevel}'
            if grb.typeOfLevel == 'isobaricInhPa': fields.setdefault(key,set()).add(int(grb.level))
            if grb.shortName in ('tp','apcp') or 'precipitation' in grb.name.lower():
                apcp.append({'shortName':grb.shortName,'name':grb.name,'level':int(grb.level),'stepType':grb.stepType,'startStep':grb.startStep,'endStep':grb.endStep,'units':grb.units})
    return {'messages':all_records,'isobaric_hpa':{k:sorted(v) for k,v in fields.items()},'precipitation':apcp}

def main():
    cycle = sys.argv[1] if len(sys.argv)>1 else CYCLES[0]
    assert cycle in CYCLES
    before = (datetime.strptime(cycle,'%Y%m%d%H')-timedelta(hours=6)).strftime('%Y%m%d%H')
    evidence = {'cycle':cycle,'retrieval':[],'inventory':{}}
    for stamp,lead in ((cycle,0),(before,0),(before,6)):
        row = fetch(stamp,lead); evidence['retrieval'].append(row)
        evidence['inventory'][Path(row['file']).name] = inventory(Path(row['file']))
        (ROOT/f'{cycle}_pilot_inventory.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print('INVENTORY',row['file'],evidence['inventory'][Path(row['file']).name],flush=True)
    prev = evidence['inventory'][f'gfs.0p25.{before}.f006.grib2']['precipitation']
    assert any('6' in str(x['endStep']) and x['stepType']=='accum' for x in prev), 'no 6h accumulated precipitation'
    print('PILOT_DONE',cycle,flush=True)

if __name__ == '__main__': main()
