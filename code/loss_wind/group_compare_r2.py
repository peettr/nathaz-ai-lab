#!/usr/bin/env python3
"""Describe DAT estimated mph against station max gust, one record per station-time group."""
import csv, pathlib, statistics, json
from collections import defaultdict
P=pathlib.Path(__file__).parent
rows=list(csv.DictReader((P/'dat_iem_pairs_scale_r2.csv').open()))
groups=defaultdict(list)
for r in rows:
  for distance in (10,25):
    if float(r['distance_km'])<=distance:
      groups[(r['year'],r['efscale'],distance,r['network'],r['station'],r['nearest_utc'])].append(r)
out=[]
for (year,ef,dist,net,station,utc),rr in sorted(groups.items()):
    numeric=[float(r['dat_windspeed_mph']) for r in rr if r['dat_windspeed_mph']]
    maxgust=[float(r['max_mph']) for r in rr]
    # One station's maximum can differ across DAT point-centered event windows within the same station-time group.
    # Only compare exact reported values per point, then take within-group median of those differences.
    diffs=[float(r['dat_minus_max_mph']) for r in rr if r['dat_minus_max_mph']]
    out.append({'year':year,'efscale':ef,'threshold_km':dist,'network':net,'station':station,'nearest_utc':utc,'damage_points':len(rr),'numeric_dat_points':len(numeric),'dat_median_mph':statistics.median(numeric) if numeric else '', 'station_max_median_mph':statistics.median(maxgust),'dat_minus_station_max_within_group_median_mph':statistics.median(diffs) if diffs else '', 'station_max_min_mph':min(maxgust),'station_max_max_mph':max(maxgust),'any_over_100kt':any(r['gust_over_100kt']=='True' for r in rr)})
p=P/'dat_iem_station_time_groups_r2.csv'
if p.exists():raise FileExistsError(p)
with p.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
def percentiles(a,q):
    if not a:return None
    a=sorted(a);pos=(len(a)-1)*q;i=int(pos);return round(a[i]+(a[min(i+1,len(a)-1)]-a[i])*(pos-i),1)
s=[]
for ef in ('TSTM/Wind','Tropical'):
 for th in (10,25):
    gg=[r for r in out if r['efscale']==ef and r['threshold_km']==th];vals=[float(r['dat_minus_station_max_within_group_median_mph']) for r in gg if r['dat_minus_station_max_within_group_median_mph']!='']
    s.append({'efscale':ef,'threshold_km':th,'all_groups':len(gg),'groups_with_numeric_dat':len(vals),'diff_mph_p10':percentiles(vals,.1),'diff_mph_median':percentiles(vals,.5),'diff_mph_p90':percentiles(vals,.9),'positive_groups':sum(v>0 for v in vals),'negative_groups':sum(v<0 for v in vals)})
p=P/'group_comparison_summary_r2.json'
if p.exists():raise FileExistsError(p)
p.write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s,indent=2))
