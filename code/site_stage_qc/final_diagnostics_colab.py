"""Post-decision diagnostics only; never changes frozen decision."""
import csv,json,math,statistics,datetime as dt
from collections import Counter,defaultdict
from pathlib import Path
r=Path('/content/site_stage_qc/final');prev=Path('/content/site_stage_qc')
qc=[json.loads(x) for x in (r/'qc_station_seasons.jsonl').open()];params=list(csv.DictReader((r/'station_params.csv').open()));gev=list(csv.DictReader((r/'gev_lmom_sensitivity.csv').open()));fits=json.loads((r/'gev_fits.json').read_text());base=list(csv.DictReader(open('/content/old_station_params.csv')))
old={x['station']:x for x in base};new={x['station']:x for x in params};G={x['station']:x for x in gev};coef=[]
for st in new:
 a=old[st];b=new[st];coef.append({'station':st,'region':b['region'],'old_x10_kn':a['station_x10_kn'],'qc_x10_kn':b['station_x10_kn'],'delta_kn':float(b['station_x10_kn'])-float(a['station_x10_kn']),'old_x50_kn':a['station_x50_kn'],'qc_x50_kn':b['station_x50_kn']})
with (r/'x10_changes.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,coef[0]);w.writeheader();w.writerows(coef)
counts=Counter();seasons=Counter()
for x in qc:
 for k,v in x.get('rule_counts',{}).items():counts[k]+=v
 if x.get('original_peak') and x.get('qc_peak') and x['original_peak']['kn']!=x['qc_peak']['kn']:seasons['value_changed']+=1
 if x.get('original_peak') and x.get('qc_peak') and x['original_peak']['event_utc']!=x['qc_peak']['event_utc']:seasons['event_changed']+=1
 if not x['valid']:seasons['invalid']+=1
 if any(k.startswith('Q') and v for k,v in x.get('rule_counts',{}).items()):seasons['any_q_action']+=1
# GEV baseline: mean of training station GEV x10 (not Gumbel baseline).
meta={x['station']:x for x in csv.DictReader((r/'static_gates.csv').open())}
import numpy as np
def hav(a,b):
 p,q=np.deg2rad([float(a['lat']),float(b['lat'])]);dl=np.deg2rad(float(a['lon'])-float(b['lon']));h=np.sin((p-q)/2)**2+np.cos(p)*np.cos(q)*np.sin(dl/2)**2
 return 12742*np.arcsin(np.sqrt(h))
gh=bh=0;region=defaultdict(lambda:Counter())
for st,q in G.items():
 train=[z for z in G if z!=st and hav(meta[st],meta[z])>200]
 actual=fits[st]['station']['x10'];bpred=float(np.mean([fits[z]['station']['x10'] for z in train]));ok=abs(float(q['R10'])-1)<=.15;bok=abs(bpred/actual-1)<=.15
 gh+=ok;bh+=bok;region[q['region']]['mapped']+=ok;region[q['region']]['baseline']+=bok
out={'generated_edt':dt.datetime.now(dt.timezone(dt.timedelta(hours=-4))).isoformat(),'qc_counts':dict(counts),'season_counts':dict(seasons),'gev_lmom_hit_count':gh,'gev_lmom_baseline_hit_count':bh,'gev_lmom_regional':{k:dict(v) for k,v in region.items()},'max_abs_x10_change':max(coef,key=lambda z:abs(z['delta_kn']))}
(r/'diagnostics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False),flush=True)
