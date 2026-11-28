"""Score only frozen 7-event gate keys; preserve all prior checkpoints."""
import csv, json, statistics, collections
from pathlib import Path
D=Path(__file__).parent;root=D.parent.parent
factor=json.loads((D.parent/'gust_fit_2022.json').read_text())['factor'];assert abs(factor-1.6677111736957388)<1e-12
E=list(csv.DictReader((root/'events_verified.csv').open()));ids={x['event_id'] for x in E};assert len(ids)==7
old=[json.loads(x) for x in (D.parent/'segment2_v1_20261014/checkpoint_budget_final.jsonl').read_text().splitlines()]
raw=[json.loads(x) for x in (D/'checkpoint_gate_final.jsonl').read_text().splitlines()]
assert raw[:len(old)]==old,'The 153 previously preserved rows have changed'
assert (D/'gate7_done.txt').read_text()=='complete'
keys=collections.defaultdict(list)
for x in raw:
    if x.get('status')=='ok' and x['id'] in ids:keys[x['id'],x['lead_h']].append(x)
assert len(keys)==21
assert len(raw)==len(old)+21*11, (len(raw),len(old))
timing={(x['id'],x['lead_h']):x for x in map(json.loads,(D/'groups_final.jsonl').read_text().splitlines())}
assert len(timing)==21 and all(x['complete'] for x in timing.values())
rows=[]
for (eid,lead),items in sorted(keys.items()):
    hr=[x for x in items if x['source']=='hrrr'];ai={x['seed']:x for x in items if x['source']=='v1'}
    assert len(hr)==1 and len(items)==11 and set(ai)==set(range(101,111)),(eid,lead)
    h=hr[0]; v=list(ai.values()); obs=h['obs_kt']*0.514444
    r={'id':eid,'station':h['station'],'peak_utc':h['peak_utc'],'init_utc':h['init'],'lead_h':lead,'obs_kt':h['obs_kt'],'obs_ms':obs,'members':10,'group_wall_sec':timing[eid,lead]['wall_sec'],'member_wall_median_sec':statistics.median(x['runtime_sec'] for x in v),'member_wall_max_sec':max(x['runtime_sec'] for x in v),'group_CU_est_6p85_per_hr':timing[eid,lead]['wall_sec']*6.85/3600}
    for w in ('wide','narrow'):
        a=[x[w]['ms']*factor for x in v];g=h[w]['gust'];s=h[w]['speed10'];assert g and s and len(a)==10
        r.update({f'{w}_ai_gust_median_ms':statistics.median(a),f'{w}_ai_gust_max_member_ms':max(a),f'{w}_ai_obs_ratio':statistics.median(a)/obs,f'{w}_hrrr_gust_ms':g['ms'],f'{w}_hrrr_gust_obs_ratio':g['ms']/obs,f'{w}_hrrr10xcoef_ms':s['ms']*factor,f'{w}_hrrr10xcoef_obs_ratio':s['ms']*factor/obs,f'{w}_p257':sum(x>=25.7 for x in a)/10,f'{w}_ai_hit_pge0p3':int(sum(x>=25.7 for x in a)>=3),f'{w}_hrrr_gust_hit':int(g['ms']>=25.7),f'{w}_hrrr10xcoef_hit':int(s['ms']*factor>=25.7),f'{w}_ai_dist_median_km':statistics.median(x[w]['distance_km'] for x in v),f'{w}_ai_time_bias_median_min':statistics.median(x[w]['time_bias_min'] for x in v),f'{w}_hrrr_gust_dist_km':g['distance_km'],f'{w}_hrrr_gust_time_bias_min':g['time_bias_min']})
        if w=='wide':r.update(wide_ai_edge_fraction=sum(x[w]['distance_km']>=22.5 for x in v)/10,wide_hrrr10_edge=int(s['distance_km']>=22.5),wide_hrrr_gust_edge=int(g['distance_km']>=22.5))
    rows.append(r)
with (D/'gate_scores.csv').open('x',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
summary={}
for lead in (1,2,3):
    a=[x for x in rows if x['lead_h']==lead];assert len(a)==7
    summary[str(lead)]={'events':len(a),'ai_obs_ratio_median':statistics.median(x['wide_ai_obs_ratio'] for x in a),'hrrr_gust_obs_ratio_median':statistics.median(x['wide_hrrr_gust_obs_ratio'] for x in a),'hrrr10xcoef_obs_ratio_median':statistics.median(x['wide_hrrr10xcoef_obs_ratio'] for x in a),'ai_to_hrrr_gust_ratio_of_medians':statistics.median(x['wide_ai_obs_ratio'] for x in a)/statistics.median(x['wide_hrrr_gust_obs_ratio'] for x in a),'hit_ai':sum(x['wide_ai_hit_pge0p3'] for x in a),'hit_hrrr_gust':sum(x['wide_hrrr_gust_hit'] for x in a),'hit_hrrr10xcoef':sum(x['wide_hrrr10xcoef_hit'] for x in a),'edge_ai_members':sum(x['wide_ai_edge_fraction']*10 for x in a),'edge_hrrr10':sum(x['wide_hrrr10_edge'] for x in a),'edge_hrrr_gust':sum(x['wide_hrrr_gust_edge'] for x in a),'group_wall_median_s':statistics.median(x['group_wall_sec'] for x in a),'group_wall_max_s':max(x['group_wall_sec'] for x in a)}
(D/'gate_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
print('RAW',len(raw),'GATE',len(raw)-len(old),'GROUPS',len(rows));print(json.dumps(summary,indent=2,ensure_ascii=False))
