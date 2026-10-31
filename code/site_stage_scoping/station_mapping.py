"""Join frozen ACE2 cells to IEM ASOS probes; distances use great-circle haversine."""
import csv, json, math
from pathlib import Path
P=Path(__file__).resolve().parent
new=json.loads((P.parent/'new_points_prereg/sites_frozen.json').read_text())['stations']
old={r['station']:r for r in json.loads(Path('./22_Lab/06_Logs/ai_climate_emulator/points.json').read_text())}
texas={r['station_anchor']:r for r in json.loads(Path('./22_Lab/06_Logs/ai_climate_emulator/dfw_aus_points.json').read_text())}
probes={r['icao']:r for r in csv.DictReader((P/'station_probe_2009_10.csv').open())}
mins={}
for r in csv.DictReader((P/'minute_probe.csv').open()):
    if int(r.get('nonmissing_gust_sknt') or 0): mins.setdefault(r['station'],[]).append(r)
def distance(a,b,c,d):
    a,b,c,d=map(math.radians,(a,b,c,d))
    x=math.sin((a-c)/2)**2+math.cos(a)*math.cos(c)*math.sin((b-d)/2)**2
    return 6371.0088*2*math.atan2(math.sqrt(x), math.sqrt(1-x))
rows=[]
for sid in 'KMSP KDSM KOMA KDTW KPIT KALB KDFW KAUS KFSD KFAR KICT KSTL KIND KCLE KBDL'.split():
    p=probes[sid]; q=new[sid] if sid in new else old.get(sid,texas.get(sid[1:]))
    glat=float(q.get('cell_lat',q.get('grid_lat'))); glon=float(q.get('cell_lon',q.get('grid_lon')))
    if glon>180:glon-=360
    stlat=float(p['station_lat']);stlon=float(p['station_lon'])
    verified='2005-04-01' if sid=='KAUS' else min(r['start_utc'] for r in mins[sid]); latest=max(r['end_utc_exclusive'] for r in mins[sid])
    jan=next(r for r in mins[sid] if r['start_utc']=='2010-01-01')
    missing=1-int(jan['nonmissing_gust_sknt'])/10080
    rows.append(dict(grid_id=sid,asos_icao=sid,iem_network=p['network'],iem_id=p['iem_id'],cell_lat=glat,cell_lon=glon,station_lat=stlat,station_lon=stlon,cell_station_distance_km=round(distance(glat,glon,stlat,stlon),1) if q else '',distance_scope='named airport ASOS to frozen ACE2 cell center; other nearby ASOS not exhaustively screened',metar_archive_begin=p['archive_begin'],metar_end='not verified (archive_end empty)',minute_peak_first_verified=verified,minute_peak_last_verified='2010-01-07' if latest=='2010-01-08' else latest,minute_peak_exact_start='unknown',metar_2009_10_hourly_wind_missing_pct=round(100*float(p['missing_wind_hour_frac']),2),minute_peak_2010_01_01_07_missing_pct=round(100*missing,1),minute_peak_full_season_missing_pct='unknown',metar_2009_10_gust_reports=p['gust_report_count'],metar_2009_10_pk_wnd_reports=p['peak_wind_report_count'],candidate='exclude: lake cell' if sid=='KMKE' else ('priority: plains' if sid in ('KDSM','KOMA','KFSD','KFAR','KICT') else 'comparison candidate')))
with (P/'station_mapping.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print('rows',len(rows))
for r in rows:print(r['grid_id'],r['cell_station_distance_km'],r['minute_peak_first_verified'],r['metar_2009_10_hourly_wind_missing_pct'],r['minute_peak_2010_01_01_07_missing_pct'])
