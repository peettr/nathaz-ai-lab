"""Score complete ten-member pilot cells only; partial sample is not a gate."""
import csv,json,statistics,pathlib,collections
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).parent
fit=json.loads((ROOT/'gust_fit_2022.json').read_text())['factor']
raw=[json.loads(x) for x in (ROOT/'v1_checkpoint_1932.jsonl').read_text().splitlines()]
by=collections.defaultdict(list)
for x in raw:by[(x['id'],x['lead_h'],x['source'])].append(x)
cases=[]
for (eid,lead,src),members in by.items():
 if src!='v1' or len(members)!=10 or {x['seed'] for x in members}!={*range(101,111)}:continue
 base=by.get((eid,lead,'hrrr'),[])
 if len(base)!=1:continue
 cases.append((eid,lead,'V1_ERA5',members,base[0]))
conus=[json.loads(x) for x in (ROOT/'conus_pilot_final.jsonl').read_text().splitlines()]
assert len(conus)==10 and {x['seed'] for x in conus}=={*range(101,111)}
base0=json.loads((ROOT/'conus_hrrr_pilot.json').read_text())
cases.append(('1329296',1,'CONUS_ERA5',conus,{'wide':{'gust':base0['wide_gust'],'speed10':base0['wide_speed10']},'narrow':{'gust':base0['narrow_gust'],'speed10':base0['narrow_speed10']}}))
rows=[]
for eid,lead,model,members,base in cases:
 obs=members[0]['obs_kt']*.514444
 for win in ('wide','narrow'):
  values=[x[win]['ms']*fit for x in members]
  a=statistics.median(values);g=base[win]['gust']['ms'];h=base[win]['speed10']['ms']*fit
  rows.append({'model':model,'event_id':eid,'station':members[0]['station'],'lead_h':lead,'window':win,'members':10,'obs_kt':members[0]['obs_kt'],'factor':fit,'ai_median_ms':round(a,3),'ai_max_ms':round(max(values),3),'ai_p257':sum(x>=25.7 for x in values)/10,'hrrr_gust_ms':round(g,3),'hrrr_speed_times_factor_ms':round(h,3),'ai_to_obs':round(a/obs,3),'hrrr_gust_to_obs':round(g/obs,3),'ai_edge_frac':round(sum(x['wide']['distance_km']>=22.5 for x in members)/10,3) if win=='wide' else '','hrrr_gust_edge':int(base['wide']['gust']['distance_km']>=22.5) if win=='wide' else ''})
rows.sort(key=lambda x:(x['model'],x['event_id'],x['lead_h'],x['window']))
with (ROOT/'pilot_window_scores.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
wide=[r for r in rows if r['window']=='wide'];fig,ax=plt.subplots(figsize=(10,5))
pos=list(range(len(wide)));labels=[f"{x['model']} {x['station']} L{x['lead_h']}" for x in wide]
ax.scatter([x-.15 for x in pos],[r['ai_to_obs'] for r in wide],label='AI gust proxy / ASOS',s=54,color='#1d4ed8')
ax.scatter([x+.15 for x in pos],[r['hrrr_gust_to_obs'] for r in wide],label='HRRR GUST / ASOS',s=54,color='#ea580c')
ax.axhline(1,color='gray',linestyle='--',linewidth=1)
ax.set_xticks(pos,labels,rotation=35,ha='right');ax.set_ylabel('Neighborhood peak / observed gust');ax.legend();ax.grid(axis='y',alpha=.2)
fig.text(.01,.01,'Pilot only (2 V1 events + 1 CONUS event); NOAA Storm Events/IEM ASOS, AWS HRRR, ARCO ERA5, NVIDIA StormCast. Not r2 gate.',fontsize=7)
fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(ROOT/'pilot_peak_ratio.png',dpi=160)
print('PILOT_CELLS',len(wide),'ROWS',len(rows));print('\n'.join(str(x) for x in wide))
