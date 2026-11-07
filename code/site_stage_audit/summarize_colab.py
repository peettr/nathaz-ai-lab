"""Colab-only aggregate of 360 station-seasons and labeled seasonal peaks."""
import csv,json,statistics,collections
from pathlib import Path
P=Path('/content/site_stage_audit')
a=[json.loads(s) for s in (P/'season_audit.jsonl').read_text().splitlines()]
e=[json.loads(s) for s in (P/'peak_labels_corrected.jsonl').read_text().splitlines()]
g=[json.loads(s) for s in (P/'metar_peak_gaps.jsonl').read_text().splitlines()]
qc=json.load(open(P/'peak_qc_screen.json'))['cases'];qc_key={(x['station'],x['season']):x for x in qc}
g_key={(x['station'],x['season']):x for x in g}
assert len(a)==360 and len(g)==360 and len({(r['station'],r['season']) for r in a})==360
assert len({(r['station'],r['season']) for r in g})==360
assert len(e)==1074
# Flatten scientific small tables, preserve raw evidence in JSONL separately.
def csvout(name,rows):
 f=P/name;fields=list(dict.fromkeys(k for r in rows for k in r))
 with f.open('x',newline='') as out:
  w=csv.DictWriter(out,fieldnames=fields);w.writeheader();w.writerows(rows)
 return str(f)
flat=[]
for x in sorted(a,key=lambda z:(z['station'],z['season'])):
 z=g_key[x['station'],x['season']];q=qc_key.get((x['station'],x['season']))
 flat.append({k:x[k] for k in ('station','season','expected_minutes','raw_rows','observed_unique_minutes','wind_valid_minutes','gust_nonempty_minutes','row_coverage','wind_coverage','gust_nonempty_fraction','max_gap_rows_min','max_gap_wind_min','minute_peak_knots','minute_peak_utc','peak_plusminus6h_missing_rows','peak_plusminus6h_missing_wind','peak_plusminus6h_missing_gust','metar_report_count','minute_url','metar_url')}|{'metar_season_peak_knots':z.get('metar_peak_knots'),'metar_season_peak_utc':z.get('metar_peak_utc'),'metar_peak_source':z.get('metar_peak_type'),'metar_peak_window_missing_rows':z.get('window_missing_rows'),'metar_peak_window_missing_wind':z.get('window_missing_wind'),'metar_peak_window_error':z.get('error'),'qc_discordance20kn':bool(q),'qc_isolated30kn_jump':bool(q and q.get('isolated_30kn_jump'))})
csvout('season_metrics.csv',flat)
peaks=[]
for x in e:
 z=x['evidence'];peaks.append({k:x[k] for k in ('station','season','peak_type','peak_utc','knots')}|{'mechanism':z.get('label'),'metar_complete':z.get('metar_hourly_complete'),'metar_hits':';'.join(z.get('metar_hits',[])),'storm_event_types':';'.join(y['type'] for y in z.get('matched_events',[])),'storm_event_ids':';'.join(str(y['event_id']) for y in z.get('matched_events',[])),'nhc_fixes':len(z.get('nhc_500km_fixes',[])),'metar_error':z.get('error'),'qc_discordance20kn':bool(qc_key.get((x['station'],x['season']))) if x['peak_type']=='minute' else False})
csvout('peak_events.csv',peaks)
station=[]
for st in sorted({z['station'] for z in flat}):
 v=[x for x in flat if x['station']==st];ev=[x for x in peaks if x['station']==st];mn=[x for x in ev if x['peak_type']=='minute'];mt=[x for x in ev if x['peak_type'] in ('metar_gust','metar_pk')]
 c=collections.Counter(x['mechanism'] for x in mn);mc=collections.Counter(x['mechanism'] for x in mt)
 station.append({'station':st,'seasons':len(v),'minute_seasons_with_peak':len(mn),'row_coverage_median_pct':round(statistics.median(x['row_coverage'] for x in v)*100,2),'row_coverage_min_pct':round(min(x['row_coverage'] for x in v)*100,2),'wind_coverage_median_pct':round(statistics.median(x['wind_coverage'] for x in v)*100,2),'wind_coverage_min_pct':round(min(x['wind_coverage'] for x in v)*100,2),'gust_nonempty_median_pct':round(statistics.median(x['gust_nonempty_fraction'] for x in v)*100,2),'seasons_wind_below_90pct':sum(x['wind_coverage']<.9 for x in v),'seasons_peak6h_missing_wind':sum(x['peak_plusminus6h_missing_wind'] is not None and x['peak_plusminus6h_missing_wind']>0 for x in v),'seasons_metar_peak6h_missing_wind':sum(x['metar_peak_window_missing_wind'] is not None and x['metar_peak_window_missing_wind']>0 for x in v),'max_wind_gap_minutes':max(x['max_gap_wind_min'] for x in v),'raw_minute_peak_qc_screen_count':sum(x['qc_discordance20kn'] for x in v),'raw_minute_peak_isolated_count':sum(x['qc_isolated30kn_jump'] for x in v),'minute_convective':c['convection'],'minute_tropical':c['tropical_cyclone'],'minute_nonconvective':c['nonconvective'],'minute_unknown':c['unknown'],'metar_convective_reports':mc['convection'],'metar_tropical_reports':mc['tropical_cyclone'],'metar_nonconvective_reports':mc['nonconvective'],'metar_unknown_reports':mc['unknown']})
csvout('station_summary.csv',station)
sumry={'seasons':len(a),'stations':len(station),'labels':len(e),'metar_gap_rows':len(g),'metar_gap_errors':sum('error' in x for x in g),'no_minute_peak':sum(x['minute_peak_knots'] is None for x in a),'qc_screen':len(qc),'qc_isolated':sum(x.get('isolated_30kn_jump',False) for x in qc),'minute_mechanism_counts':dict(collections.Counter(x['mechanism'] for x in peaks if x['peak_type']=='minute')),'metar_mechanism_counts':dict(collections.Counter(x['mechanism'] for x in peaks if x['peak_type']!='minute')),'station_summary':station}
(P/'analysis_summary.json').open('x').write(json.dumps(sumry,ensure_ascii=False,indent=2))
print('SUMMARY',json.dumps({k:v for k,v in sumry.items() if k!='station_summary'}),flush=True)
