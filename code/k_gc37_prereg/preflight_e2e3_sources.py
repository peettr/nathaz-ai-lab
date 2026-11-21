#!/usr/bin/env python3
"""Read-only object/DDS inventory for frozen E2/E3 cycles; no GRIB downloads."""
import datetime as dt
import json
import pathlib
import re
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVENTS = json.loads((HERE / 'event_times_gc37.json').read_text())
BASE = 'https://osdf-director.osg-htc.org/ncar/gdex'
DAP = 'https://thredds.rda.ucar.edu/thredds/dodsC/files/g'
LEVELS = (1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200, 150, 100, 70, 50, 30, 20, 10, 7, 5, 3, 2, 1)
MIDDLE = (125, 175, 225, 775, 825, 875)
REQUIRED = ('Geopotential_height_isobaric', 'Temperature_isobaric', 'u-component_of_wind_isobaric', 'v-component_of_wind_isobaric', 'Specific_humidity_isobaric')

def check(ds, issue, lead):
    stem = 'gfs.0p25b' if ds == 'd084003' else 'gfs.0p25'
    tail = f'{ds}/2024/{issue:%Y%m%d}/{stem}.{issue:%Y%m%d%H}.f{lead:03d}.grib2'
    out = {'dataset': ds, 'issue': issue.isoformat(), 'lead_hours': lead, 'range_url': BASE + '/' + tail, 'dds_url': DAP + '/' + tail + '.dds'}
    for name, url, headers in (('range', out['range_url'], {'Range': 'bytes=0-15'}), ('dds', out['dds_url'], {})):
        try:
            request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0', **headers})
            with urllib.request.urlopen(request, timeout=28) as response:
                data = response.read(250000 if name == 'dds' else 16)
                out[name+'_http'] = response.status
                if name == 'range': out['grib_header'] = data[:4].decode(errors='replace')
                else:
                    lines = data.decode(errors='replace').splitlines()
                    out['dds_required'] = {field: [x.strip() for x in lines if re.search(r'\b'+re.escape(field)+r'\[', x)] for field in REQUIRED}
                    out['dds_apcp'] = [x.strip() for x in lines if 'Total_precipitation_surface_' in x and ('Accumulation' in x or 'accumulation' in x)][:15]
                    out['dds_surface'] = {s: [x.strip() for x in lines if s in x][:4] for s in ('Temperature_height_above_ground', 'u-component_of_wind_height_above_ground', 'v-component_of_wind_height_above_ground')}
                    out['dds_isobaric_dimensions'] = [x.strip() for x in lines if re.search(r'Float(32|64) isobaric\d*\[', x)][:5]
        except Exception as exc:
            out[name+'_error'] = f'{type(exc).__name__}: {exc}'
            out[name+'_http'] = getattr(exc, 'code', None)
    return out

def main():
    result = {'description':'metadata only; actual GRIB values, land masks and full pressure coordinates require decoding on compute host', 'files':[], 'cycles':{}}
    cache={}
    for event in ('E2','E3'):
        for lead_name, spec in EVENTS[event]['leads'].items():
            issue=dt.datetime.fromisoformat(spec['t0']); end=dt.datetime.fromisoformat(EVENTS[event]['end']); key=f'{event}_{lead_name}'
            todo=[]
            for t in (issue-dt.timedelta(hours=6),issue):
                todo.extend([('d084001',t,0),('d084003',t,0),('d084001',t-dt.timedelta(hours=6),6)])
            todo += [('d084001',issue,h) for h in range(6,int((end-issue).total_seconds()/3600)+1,6)]
            ids=[]
            for ds,t,h in todo:
                token=[已隐去],t.isoformat(),h)
                if token not in cache:
                    cache[token]=len(result['files'])
                    rec=check(ds,t,h);result['files'].append(rec)
                    print(event,lead_name,ds,t.isoformat(),h,rec.get('range_http'),rec.get('dds_http'),flush=True)
                ids.append(cache[token])
            result['cycles'][key]={'issue':spec['t0'],'end':EVENTS[event]['end'],'file_indices':ids,'all_range_206':all(result['files'][i].get('range_http')==206 and result['files'][i].get('grib_header')=='GRIB' for i in ids),'all_dds_required_names':all(all(result['files'][i].get('dds_required',{}).get(k) for k in REQUIRED) for i in ids if result['files'][i]['dataset']=='d084001' and result['files'][i]['lead_hours']!=6)}
    dest=HERE/'INPUT_PREFLIGHT_E2E3_2024.json'
    with dest.open('x') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print('RESULT',dest,'unique_files',len(result['files']),'cycles',len(result['cycles']),flush=True)
if __name__=='__main__':main()
