"""Format trial of judge_gc37_v3 on WRF 24 h readout (11-16). Not the formal scoring."""
import csv, json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'k_gc37_prereg'))
import judge_gc37_v3 as j
D=Path(sys.argv[1]); EV=json.loads((Path(__file__).resolve().parents[1]/'k_gc37_prereg'/'event_times_gc37.json').read_text())
F={'time':'time_utc','latitude':'lat','longitude':'lon','area':'area_km2','member':'member','tier':'tier','first':'first_utc','left':'left_censored','station_lat':'station_lat','station_lon':'station_lon','nearest_cell':'nearest_cell_km'}
issues=[]
def rows(p): return list(csv.DictReader(open(p)))
def b(v): return v in (True,'True','true',1)
obs_on=json.loads((D/'obs/onsets_typed.json').read_text())
out={}
for ev in ('E1','E2','E3'):
    for tag,members in (('formal',{'E1':('E1_AI_24h','E1_GFS_24h'),'E2':('E2_AI_24h_dt20_r2','E2_GFS_24h'),'E3':('E3_AI_24h_dt20_r2','E3_GFS_24h')}[ev]),
                        ('dt15',{'E2':('E2_AI_24h_dt15','E2_GFS_24h_dt15'),'E3':('E3_AI_24h_dt15','E3_GFS_24h_dt15')}.get(ev))):
        if not members: continue
        frames=rows(D/f'obs/{ev}_OBS_objects.csv'); ft={}
        o=json.loads((D/f'obs/{ev}_frame_times.json').read_text()); ft['OBS']=o if isinstance(o,list) else o.get('OBS')
        if isinstance(o,list): issues.append(f'{ev} obs frame_times is bare list (model files are dict keyed by arm)') if f'{ev} obs' not in str(issues) else None
        if ft['OBS'] is None: issues.append(f'{ev} obs frame_times keys {list(o)[:3]}')
        for m in members:
            frames+=rows(D/f'models/{m}_objects.csv')
            t=json.loads((D/f'models/{m}_frame_times.json').read_text()); ft.update({k:v for k,v in t.items()})
        res={}
        for tier in (64,16):
            ons={'OBS':{'first_utc':obs_on[ev][str(tier)]['OBS']['first_utc'],'left_censored':obs_on[ev][str(tier)]['OBS']['left_censored']}}
            for m in members:
                for r in rows(D/f'models/{m}_onset.csv'):
                    if int(r['tier'])==tier: ons[r['member']]={'first_utc':r['first_utc'] or None,'left_censored':b(r['left_censored'])}
            res[tier]=j.compare_tier(EV[ev],frames,ons,tier,F,ft)
        res['area']=j.combine_areas(res[64],res[16]); out[f'{ev}_{tag}']=res
json.dump({'issues':issues,'results':out},open('trial_judge_24h_out.json','w'),ensure_ascii=False,indent=1,default=str)
print('issues',issues); print({k:v['area'] for k,v in out.items()})
