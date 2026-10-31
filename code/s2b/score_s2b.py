#!/usr/bin/env python3
"""Score complete frozen tracks; preserve missing-event denominator and raw provenance."""
import csv,json,statistics,sys,collections,math
from datetime import datetime,timedelta
from pathlib import Path
HERE=Path(__file__).resolve().parent; S2=HERE.parent; BASE=S2.parent;sys.path.insert(0,str(S2));sys.path.insert(0,str(BASE/'v1'))
OUT=HERE/'final';OUT.mkdir(exist_ok=True)
import chain_a_v1 as v
import chain_b_s2a as b
old=v.old

def writecsv(name,rows,fields):
 with (OUT/name).open('x',newline='') as f:
  w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def met(err):return {'n':len(err),'mae':statistics.median(map(abs,err)) if err else None,'bias':statistics.median(err) if err else None}
def getnum(x):return float(x) if x not in ('','None',None) else None

def main():
 events=list(csv.DictReader((BASE/'events_verified.csv').open()));obs=list(csv.DictReader((BASE/'v1/run2/station_rows_v1.csv').open()));observed={(x['event'],x['station']):x for x in obs}
 bs=json.loads((S2/'s2a/b_status.json').read_text());bfull={(x['event'],x['nominal_lead_h']) for x in bs if x.get('nodes')==97 and not x.get('error')};br=list(csv.DictReader((S2/'s2a/b_station_rows.csv').open()))
 br=[dict(x,chain='b') for x in br if (x['event'],int(x['nominal_lead_h'])) in bfull]
 geo=v.get_land();hur=old.parse_hurdat();cr=[];paths=[];statuses=[]
 for ev in events:
  event=ev['name'];land=datetime.fromisoformat(ev['landfall_utc']);sid=ev['atcf_id'].lower();ss={}
  for state in old.CANDIDATES[event][2].split(','):ss.update(old.stations(state,float(ev['lat']),float(ev['lon']),land))
  stations=[ss[station] for name,station in observed if name==event and station in ss]
  a,_=b.load_a(sid)
  for model,lead in [('PANG',24),('PANG',48),('FOUR',48),('GRAP',48)]:
   source=HERE/f'track_{event.lower()}_{model.lower()}_{lead}.json'
   state=dict(event=event,chain=model,lead=lead,source=source.name,status='no_track',n_stations_eligible=sum(x['reason']=='eligible' for x in obs if x['event']==event))
   if not source.exists():statuses.append(state);continue
   obj=json.loads(source.read_text());state.update(bytes=obj['bytes'],elapsed_s=obj['elapsed_s'],failure=obj['failure'],n_track_points=len(obj['points']))
   initial,error=b.get_initial(a,datetime.fromisoformat(obj['init_utc']))
   if error:state.update(status=error);statuses.append(state);continue
   points=obj['points'];pairs=[(datetime.fromisoformat(x['valid_utc']),(x['lat'],x['lon'])) for x in points]
   if len(pairs)>1:
    for p in points:
     t=datetime.fromisoformat(p['valid_utc']);true=old.interp([(x['t'],(x['lat'],x['lon'])) for x in hur[event][1]],t,None)
     paths.append(dict(event=event,chain=model,lead=lead,init_utc=obj['init_utc'],valid_utc=p['valid_utc'],lat=p['lat'],lon=p['lon'],best_lat=true[0] if true else '',best_lon=true[1] if true else '',error_km=old.km(p['lat'],p['lon'],*true) if true else '',rmw_nmi=initial['rmw']))
    center=old.interp(pairs,land,None)
    state['landfall_error_km']=old.km(*center,float(ev['lat']),float(ev['lon'])) if center else None
    d=[r['error_km'] for r in paths if r['event']==event and r['chain']==model and r['lead']==lead and r['error_km']!='' and abs((datetime.fromisoformat(r['valid_utc'])-land).total_seconds())<=43200]
    state['mean_12h_path_error_km']=statistics.mean(d) if d else None
   if obj['failure']:
    state['status']='broken_track';statuses.append(state);continue
   ofcl=sorted((z for (c,aid,k),z in a.items() if c==datetime.fromisoformat(obj['init_utc']) and aid=='OFCL' and k>=0 and z['v']>0),key=lambda z:z['t'])
   start=land-timedelta(hours=12);winds=[(x['t'],(x['v'],)) for x in ofcl];rows=[]
   for i in range(97):
    t=start+timedelta(minutes=15*i);loc=old.interp(pairs,t,None);ww=b.forecast_interp(winds,t)
    if loc is None or ww is None:continue
    wind=ww[0];pressure=initial['poci']-(initial['poci']-initial['p'])*(wind/initial['v0'])**(1/.644)
    if 0<pressure<initial['poci']:rows.append((t,loc[0],loc[1],wind,pressure,initial['rmw'],initial['poci']))
   state['n_window_nodes']=len(rows)
   if len(rows)!=97:state['status']='incomplete_window';statuses.append(state);continue
   try:
    scored,_=b.score(event,lead,rows,stations,observed,land,geo)
    cr.extend(dict(x,chain=model) for x in scored)
    state['status']='scored'
   except Exception as exc:state['status']='score_error';state['error']=repr(exc)
   statuses.append(state);print('SCORE',event,model,lead,state['status'],flush=True)
 # b72 coarse interpolation, no extrapolation
 oldfun=b.forecast_interp
 def coarse(pairs,t):
  lo=max((x for x in pairs if x[0]<=t),default=None,key=lambda x:x[0]);hi=min((x for x in pairs if x[0]>=t),default=None,key=lambda x:x[0])
  if lo is None or hi is None or (hi[0]-lo[0]).total_seconds()>25*3600:return None
  w=(t-lo[0]).total_seconds()/max(1,(hi[0]-lo[0]).total_seconds());return [x+(y-x)*w for x,y in zip(lo[1],hi[1])]
 b.forecast_interp=coarse
 for ev in events:
  event=ev['name'];land=datetime.fromisoformat(ev['landfall_utc']);cycle=b.cycle_at(land,72);a,_=b.load_a(ev['atcf_id'].lower());initial,error=b.get_initial(a,cycle)
  state=dict(event=event,chain='b_coarse',lead=72,status=error or 'incomplete_window')
  if not error:
   rows,_=b.official(a,cycle,initial,land-timedelta(hours=12),land+timedelta(hours=12));state['n_window_nodes']=len(rows)
   if len(rows)==97:
    ss={}
    for st in old.CANDIDATES[event][2].split(','):ss.update(old.stations(st,float(ev['lat']),float(ev['lon']),land))
    stations=[ss[s] for e,s in observed if e==event and s in ss]
    try:cr.extend(dict(x,chain='b_coarse') for x in b.score(event,72,rows,stations,observed,land,geo)[0]);state['status']='scored'
    except Exception as exc:state['status']='score_error';state['error']=repr(exc)
    for t,lat,lon,*_ in rows:
     true=old.interp([(x['t'],(x['lat'],x['lon'])) for x in hur[event][1]],t,None)
     paths.append(dict(event=event,chain='b_coarse',lead=72,init_utc=cycle.isoformat(),valid_utc=t.isoformat(),lat=lat,lon=lon,best_lat=true[0] if true else '',best_lon=true[1] if true else '',error_km=old.km(lat,lon,*true) if true else '',rmw_nmi=initial['rmw']))
    state['landfall_error_km']=old.km(rows[48][1],rows[48][2],float(ev['lat']),float(ev['lon']))
  statuses.append(state)
 b.forecast_interp=oldfun
 cr+=br
 writecsv('station_comparison.csv',cr,list(cr[0]));writecsv('paths.csv',paths,list(paths[0]));(OUT/'status.json').write_text(json.dumps(statuses,indent=2,default=str))
 eventrows=[]
 for chain in ('a','b','b_coarse','PANG','FOUR','GRAP'):
  for lead in ([0] if chain=='a' else [24,48] if chain in ('b','PANG') else [72] if chain=='b_coarse' else [48]):
   source=obs if chain=='a' else [x for x in cr if x['chain']==chain and int(x['nominal_lead_h'])==lead]
   for ev in events:
    event=ev['name'];rr=[x for x in source if x['event']==event and x['reason']=='eligible']
    for var in ('s','g'):
     e=[getnum(x['err_'+var]) for x in rr];e=[x for x in e if x is not None]
     eventrows.append(dict(event=event,chain=chain,lead=lead,variable=var,**met(e)))
 writecsv('event_comparison.csv',eventrows,list(eventrows[0]));summary={}
 for chain in ('a','b','b_coarse','PANG','FOUR','GRAP'):
  for lead in ([0] if chain=='a' else [24,48] if chain in ('b','PANG') else [72] if chain=='b_coarse' else [48]):
   source=obs if chain=='a' else [x for x in cr if x['chain']==chain and int(x['nominal_lead_h'])==lead]
   for var in ('s','g'):
    e=[getnum(x['err_'+var]) for x in source if x['reason']=='eligible'];e=[x for x in e if x is not None]
    summary[f'{chain}_{lead}_{var}']=met(e)
 for model in ('PANG','FOUR','GRAP'):
  same={x['event'] for x in statuses if x['chain']==model and x['lead']==48 and x['status']=='scored' and (x['event'],48) in bfull and x['n_stations_eligible']>0}
  eligible=[x for x in eventrows if x['event'] in same and x['lead']==48 and x['variable']=='s']
  bmed=[getnum(x['err_s']) for x in br if x['event'] in same and int(x['nominal_lead_h'])==48 and x['reason']=='eligible'];bmed=[x for x in bmed if x is not None]
  cmed=[getnum(x['err_s']) for x in cr if x['chain']==model and x['event'] in same and int(x['nominal_lead_h'])==48 and x['reason']=='eligible'];cmed=[x for x in cmed if x is not None]
  wins=[ev for ev in same if next((x['mae'] for x in eligible if x['event']==ev and x['chain']==model),math.inf)<=next((x['mae'] for x in eligible if x['event']==ev and x['chain']=='b'),-1)]
  summary[f'{model}_gate']={'events':sorted(same),'n_event':len(same),'n_stations':len(cmed),'c_median_abs':met(cmed)['mae'],'b_median_abs':met(bmed)['mae'],'ratio':met(cmed)['mae']/met(bmed)['mae'] if cmed and bmed else None,'wins':sorted(wins),'n_win':len(wins),'passes':len(same)==9 and len(cmed)==22 and met(cmed)['mae']<=1.1*met(bmed)['mae'] and len(wins)*3>=len(same)*2 if cmed and bmed else False,'ten_event_denominator_wins':f'{len(wins)}/10'}
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False));print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
