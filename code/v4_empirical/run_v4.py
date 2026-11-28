#!/usr/bin/env python3
"""Frozen v4 empirical substitutions; execute on Colab CPU only."""
import csv,json,math,statistics,sys,time,urllib.request
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timedelta
import numpy as np
BASE=Path('/content/b_tc'); OUT=Path('/content/v4out')
sys.path[:0]=[str(BASE/'s2'),str(BASE/'v1')]
import chain_b_s2a as b
import chain_a_v1 as v
import importlib
wf=importlib.import_module('climada.hazard.trop_cyclone.trop_cyclone_windfields')
old=v.old
EVENTS=('BERYL','DEBBY','DELTA','FRANCINE','HELENE','IAN','MILTON','NICOLE','ZETA')
VARIANTS=('V0','VK','PH','VK_land')
CHAINS=('b','c')
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def save(name,rr):
 if not rr:return
 with (OUT/name).open('x',newline='') as f:
  w=csv.DictWriter(f,rr[0]);w.writeheader();w.writerows(rr)
def station_meta(event,ev,roster):
 ss={};land=datetime.fromisoformat(ev['landfall_utc'])
 for state in old.CANDIDATES[event][2].split(','):ss.update(old.stations(state,float(ev['lat']),float(ev['lon']),land))
 return [ss[r['station']] for r in roster if r['event']==event and r['status']=='include']
def h08_external(track,stations,geo,external):
 """Only intercept the H08 B_s calculation; all remaining original v1 code untouched."""
 if external is None:return v.predict(track,stations,geo)
 original=wf._bs_holland_2008
 def replace(si_track,gradient_to_surface_winds=wf.DEF_GRADIENT_TO_SURFACE_WINDS):
  original(si_track,gradient_to_surface_winds=gradient_to_surface_winds)
  assert len(si_track.time)==len(external)
  si_track['hol_b'].values[:]=external
 try:
  wf._bs_holland_2008=replace
  return v.predict(track,stations,geo)
 finally:wf._bs_holland_2008=original
def node_formula(variant,vm_kt,lat,lon,orig_dp,land_dt,t):
 vm=vm_kt*old.KNOT
 if variant=='PH':
  dp=(.88669*vm/4.765)**(1/.6205)
  B=-.01877*lat+.00617*dp+1.50474
  flight=math.exp(.04897*lat-.00477*dp+2.62898)
  rmw=(flight-8.92)/.89;truncated=rmw<5
  return dp,max(5,rmw),B,0,False,truncated
 dp=orig_dp;conv=False
 for it in range(1,101):
  gulf=lon< -81 and lat>18
  rmw=math.exp(3.858-7.700e-5*dp**2) if gulf else math.exp(3.015-6.291e-5*dp**2+.0337*lat)
  B=1.881-.00557*rmw-.01295*lat
  if variant=='VK_land' and gulf and land_dt-timedelta(hours=12)<=t<=land_dt:B-=.21
  new=1.15*math.e*vm**2/B/100
  if abs(new-dp)<.01:conv=True;dp=new;break
  dp=new
 gulf=lon< -81 and lat>18
 rmw=math.exp(3.858-7.700e-5*dp**2) if gulf else math.exp(3.015-6.291e-5*dp**2+.0337*lat)
 B=1.881-.00557*rmw-.01295*lat
 if variant=='VK_land' and gulf and land_dt-timedelta(hours=12)<=t<=land_dt:B-=.21
 return dp,rmw,B,it,not conv,False
def main():
 OUT.mkdir(exist_ok=True)
 assert not any((OUT/f).exists() for f in ('rows_v4.csv','node_params.csv','v0_gate.json'))
 t0=time.monotonic()
 import importlib.metadata
 version=importlib.metadata.version('climada')
 print('CLIMADA',version,'rho',wf.DEF_RHO_AIR,flush=True)
 assert version=='6.1.0' and wf.DEF_RHO_AIR==1.15
 if not (BASE/'v1/ne_10m_land.zip').exists():
  urllib.request.urlretrieve('https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip',BASE/'v1/ne_10m_land.zip')
 geo=v.get_land()
 evs={r['name']:r for r in read(BASE/'events_verified.csv')}
 obs={(r['event'],r['station']):r for r in read(BASE/'v1/run2/station_rows_v1.csv')}
 roster=read(BASE/'v4_empirical/sample_list.csv')
 expected={(r['event'],r['station']) for r in roster if r['status']=='include'}
 assert len(expected)==22 and {k[0] for k in expected}==set(EVENTS)
 baseline={(r['event'],r['station'],r['chain']):r for r in read(BASE/'s2/s2b/final/station_comparison.csv') if r['reason']=='eligible' and r['nominal_lead_h']=='48' and r['chain'] in ('b','PANG') and (r['event'],r['station']) in expected}
 assert len(baseline)==44
 tracks={};stations_by={}
 for event in EVENTS:
  ev=evs[event];land=datetime.fromisoformat(ev['landfall_utc']);cycle=b.cycle_at(land,48)
  a,_=b.load_a(ev['atcf_id'].lower());initial,error=b.get_initial(a,cycle);assert not error,(event,error)
  official,_=b.official(a,cycle,initial,land-timedelta(hours=12),land+timedelta(hours=12));assert len(official)==97,event
  cobj=json.loads((BASE/f's2/s2b/track_{event.lower()}_pang_48.json').read_text());assert not cobj['failure'],event
  pairs=[(datetime.fromisoformat(x['valid_utc']),(x['lat'],x['lon'])) for x in cobj['points']]
  ofcl=sorted((r for (cy,aid,k),r in a.items() if cy==cycle and aid=='OFCL' and k>=0 and r['v']>0),key=lambda r:r['t'])
  c=[]
  for i in range(97):
   t=land-timedelta(hours=12)+timedelta(minutes=15*i);loc=old.interp(pairs,t,None);wind=b.forecast_interp([(r['t'],(r['v'],)) for r in ofcl],t)
   assert loc is not None and wind is not None,(event,i)
   p=initial['poci']-(initial['poci']-initial['p'])*(wind[0]/initial['v0'])**(1/.644)
   assert 0<p<initial['poci']
   c.append((t,loc[0],loc[1],wind[0],p,initial['rmw'],initial['poci']))
  tracks[event]={'b':official,'c':c};stations_by[event]=station_meta(event,ev,roster)
  assert len(stations_by[event])==sum(k[0]==event for k in expected)
  print('TRACK',event,len(official),len(c),flush=True)
 # Physical pointwise parity of external B with H08 internally calculated B.
 testrows=tracks['BERYL']['b'];track=b.dataset(testrows);station=stations_by['BERYL']
 si=wf.tctrack_to_si(track);wf._bs_holland_2008(si);internal=si['hol_b'].values.copy()
 original=v.predict(track,station,geo)[0]
 external=h08_external(track,station,geo,internal)[0]
 rel=np.max(np.abs(original-external)/np.maximum(np.abs(original),1e-12))
 assert rel<1e-9,rel
 (OUT/'h08_external_b_test.log').write_text(f'CLIMADA 6.1.0; B_s internal passed to external hook, BERYL b full 97 nodes x {len(station)} stations; max relative difference {rel:.16g}; criterion <1e-9 PASS\n')
 print('H08_B_PARITY',rel,flush=True)
 rows=[];nodes=[]
 for variant in VARIANTS:
  for event in EVENTS:
   land=datetime.fromisoformat(evs[event]['landfall_utc'])
   for chain in CHAINS:
    original_rows=tracks[event][chain];changed=[];bvals=[];bad=False
    for idx,r in enumerate(original_rows):
     t,lat,lon,wind,pc,rmw_nmi,penv=r;original_dp=penv-pc
     if variant=='V0':dp,rmw_km,B,it,nonconv,cut=original_dp,rmw_nmi*1.852,'',0,False,False
     else:dp,rmw_km,B,it,nonconv,cut=node_formula(variant,wind,lat,lon,original_dp,land,t)
     if nonconv or not (0<dp<penv and rmw_km>0 and (B=='' or B>0)):bad=True
     if variant!='V0':
      nodes.append(dict(event=event,chain=chain,variant=variant,valid_utc=t.isoformat(),vm_kt=wind,lat=lat,lon=lon,dp_hpa=dp,rmw_km=rmw_km,B=B,iterations=it,nonconverged=int(nonconv),rmw_truncated=int(cut)))
     changed.append((t,lat,lon,wind,penv-dp,rmw_km/1.852,penv));bvals.append(B)
    if bad:
     print('BAD_NODES',event,chain,variant,flush=True);continue
    ds=b.dataset(changed)
    if variant=='V0':sustained,_,_=v.predict(ds,stations_by[event],geo)
    else:sustained,_,_=h08_external(ds,stations_by[event],geo,np.asarray(bvals))
    for j,st in enumerate(stations_by[event]):
     key=(event,st['station']);o=obs[key];ref=baseline[(event,st['station'],'b' if chain=='b' else 'PANG')]
     assert float(ref['obs_s_kt'])==float(o['obs_s_kt'])
     peak=float(sustained[:,j].max());err=peak/float(o['obs_s_kt'])-1
     rows.append(dict(event=event,station=st['station'],chain=chain,variant=variant,obs_s_kt=o['obs_s_kt'],pred_s_kt=f'{peak/1:.12g}',err_s=f'{err:.15g}',model_peak_utc=changed[int(np.argmax(sustained[:,j]))][0].isoformat()))
   print('SCORED',variant,event,len(rows),'elapsed',round(time.monotonic()-t0,2),flush=True)
  if variant=='V0':
   def metric(chain,absval):
    z=[abs(float(x['err_s'])) if absval else float(x['err_s']) for x in rows if x['variant']=='V0' and x['chain']==chain]
    assert len(z)==22
    return statistics.median(z)
   vals={'b_B':metric('b',False),'b_M':metric('b',True),'c_M':metric('c',True)}
   target={'b_B':-.3789187742129117,'b_M':.4105298506025953,'c_M':.4191043855069705}
   delta={k:100*(vals[k]-target[k]) for k in vals}
   (OUT/'v0_gate.json').write_text(json.dumps(dict(values=vals,s2b=target,difference_pp=delta,passed=all(abs(x)<=.1 for x in delta.values())),indent=2))
   save('rows_v0.csv',rows)
   print('V0_GATE',vals,delta,flush=True)
   if any(abs(x)>.1 for x in delta.values()):raise RuntimeError('V0 gate failed; STOP before VK/PH')
 save('node_params.csv',nodes);save('rows_v4.csv',rows)
 print('COMPLETE',len(nodes),len(rows),'elapsed',time.monotonic()-t0,flush=True)
if __name__=='__main__':main()
