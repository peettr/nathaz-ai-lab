#!/usr/bin/env python3
"""Evaluate completed single Pangu 850 pilot without substituting BEST into forecast."""
import sys,csv,json,statistics
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent/'v1'))
import chain_a_v1 as v
import chain_b_s2a as b
old=v.old

def main():
    p=HERE/'pilot_full_milton_pang_48.json'
    obj=json.loads(p.read_text());points=obj['points'];assert not obj['failure'],obj['failure']
    event='MILTON';ev=next(x for x in csv.DictReader((HERE.parent/'events_verified.csv').open()) if x['name']==event)
    land=datetime.fromisoformat(ev['landfall_utc']);start=land-timedelta(hours=12);end=land+timedelta(hours=12)
    init=datetime.fromisoformat(obj['init_utc']);a,url=b.load_a(ev['atcf_id'].lower());initial,error=b.get_initial(a,init);assert not error
    ofcl=sorted((z for (c,aid,k),z in a.items() if c==init and aid=='OFCL' and k>=0 and z['v']>0),key=lambda z:z['t'])
    pairs=[(datetime.fromisoformat(x['valid_utc']),(x['lat'],x['lon'])) for x in points]
    winds=[(x['t'],(x['v'],)) for x in ofcl]
    rows=[]
    for i in range(97):
        t=start+timedelta(minutes=15*i)
        loc=old.interp(pairs,t,None);ww=b.forecast_interp(winds,t)
        if loc is None or ww is None:continue
        wind=ww[0];pressure=initial['poci']-(initial['poci']-initial['p'])*(wind/initial['v0'])**(1/.644)
        rows.append((t,loc[0],loc[1],wind,pressure,initial['rmw'],initial['poci']))
    result={'event':event,'model':'PANG','nominal_lead_h':48,'n_window_nodes':len(rows),'n_tracker_points':len(points),'bytes':obj['bytes'],'calls':obj['calls'],'elapsed_s':obj['elapsed_s']}
    if len(rows)==97:
        stations_by_state={}
        for state in old.CANDIDATES[event][2].split(','):stations_by_state.update(old.stations(state,float(ev['lat']),float(ev['lon']),land))
        observed={(r['event'],r['station']):r for r in csv.DictReader((HERE.parent/'v1/run2/station_rows_v1.csv').open())}
        ss=[stations_by_state[s] for e,s in observed if e==event]
        pred,_=b.score(event,48,rows,ss,observed,land,v.get_land())
        with (HERE/'c_pang_milton48_stations.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,pred[0].keys());writer.writeheader();writer.writerows(pred)
        best=v.old.parse_hurdat()[event][1]
        for x in points:
            t=datetime.fromisoformat(x['valid_utc']);true=old.interp([(r['t'],(r['lat'],r['lon'])) for r in best],t,None)
            x['best_error_km']=old.km(x['lat'],x['lon'],*true) if true else None
        with (HERE/'c_pang_milton48_path.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,points[0].keys());writer.writeheader();writer.writerows(points)
        center=old.interp(pairs,land,None)
        result['landfall_path_error_km']=old.km(*center,float(ev['lat']),float(ev['lon'])) if center else None
        for field in ('s','g'):
            errors=[float(x['err_'+field]) for x in pred if x['err_'+field] is not None]
            result[field]={'n':len(errors),'median_abs_error':statistics.median(map(abs,errors)) if errors else None,'median_bias':statistics.median(errors) if errors else None}
    (HERE/'c_pang_milton48_pilot_metrics.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
