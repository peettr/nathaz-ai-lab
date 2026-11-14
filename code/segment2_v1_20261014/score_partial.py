"""Score complete paired V1 groups in newest preserved checkpoint; controls QC tagged."""
import json,csv,collections,statistics,pathlib,sys
D=pathlib.Path(__file__).parent;R=D.parent
p=D/'checkpoint_budget_final.jsonl'
if not p.exists():p=max(D.glob('keepalive_checkpoint_*.jsonl'),key=lambda x:x.stat().st_mtime)
raw=[json.loads(x) for x in p.read_text().splitlines()]
factor=json.loads((R/'gust_fit_2022.json').read_text())['factor']
qc={x['id']:x for x in map(json.loads,(D/'control_neighbor_audit.jsonl').read_text().splitlines())}
keys=collections.defaultdict(list)
for x in raw:
    if x['status']=='ok':keys[(x['id'],x['lead_h'])].append(x)
rows=[]
for (eid,lead),rr in sorted(keys.items()):
    ai={x.get('seed'):x for x in rr if x['source']=='v1'};hs=[x for x in rr if x['source']=='hrrr']
    if set(ai)!=set(range(101,111)) or len(hs)!=1:continue
    h=hs[0];vals=list(ai.values());group=h['group'];q=qc.get(eid,{})
    row={'id':eid,'station':h['station'],'group':group,'lead_h':lead,'obs_kt':h['obs_kt'],'control_qc':q.get('validation','not_applicable')}
    for w in ('wide','narrow'):
        if any(x.get(w) is None for x in vals) or any(h[w].get(k) is None for k in ('gust','speed10')):break
        v=[x[w]['ms']*factor for x in vals];med=statistics.median(v)
        g=h[w]['gust']['ms'];s=h[w]['speed10']['ms']*factor
        row.update({w+'_ai_median_ms':med,w+'_ai_max_ms':max(v),w+'_p257':sum(x>=25.7 for x in v)/10,w+'_ai_hit':int(sum(x>=25.7 for x in v)>=3),w+'_hrrr_gust_ms':g,w+'_hrrr_gust_hit':int(g>=25.7),w+'_hrrr_10xcoef_ms':s,w+'_hrrr_10xcoef_hit':int(s>=25.7),w+'_ai_edge_frac':sum(x[w]['distance_km']>=22.5 for x in vals)/10 if w=='wide' else None,w+'_hrrr10_edge':int(h[w]['speed10']['distance_km']>=22.5) if w=='wide' else None,w+'_hrrr_gust_edge':int(h[w]['gust']['distance_km']>=22.5) if w=='wide' else None})
        if group!='control':row.update({w+'_ai_obs_ratio':med/(h['obs_kt']*.514444),w+'_hrrr_gust_obs_ratio':g/(h['obs_kt']*.514444),w+'_hrrr_10xcoef_obs_ratio':s/(h['obs_kt']*.514444)})
    else:rows.append(row)
if not rows:raise SystemExit('no complete paired groups')
with (D/'scored_partial.csv').open('x',newline='') as f:
    ww=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for x in rows for k in x)));ww.writeheader();ww.writerows(rows)
summary={'checkpoint':str(p),'raw_rows':len(raw),'complete_pairs':len(rows),'complete_events':len({x['id'] for x in rows if x['group']!='control' and all(any(y['id']==x['id'] and y['lead_h']==lead for y in rows) for lead in (1,2,3))}),'complete_controls':len({x['id'] for x in rows if x['group']=='control' and all(any(y['id']==x['id'] and y['lead_h']==lead for y in rows) for lead in (1,2,3))}),'per_lead':{}}
for lead in (1,2,3):
    sub=[x for x in rows if x['lead_h']==lead];e=[x for x in sub if x['group']!='control'];c=[x for x in sub if x['group']=='control' and x['control_qc']=='nearby_metar_lt40'];other=[x for x in sub if x['group']=='control' and x['control_qc']!='nearby_metar_lt40']
    def median(key,xx):return statistics.median(x[key] for x in xx) if xx else None
    summary['per_lead'][str(lead)]={'events':len(e),'verified_controls':len(c),'unverified_controls':len(other),'wide_ratio_ai':median('wide_ai_obs_ratio',e),'wide_ratio_hrrr_gust':median('wide_hrrr_gust_obs_ratio',e),'wide_ratio_hrrr_10xcoef':median('wide_hrrr_10xcoef_obs_ratio',e),'hits_ai':sum(x['wide_ai_hit'] for x in e),'hits_hrrr_gust':sum(x['wide_hrrr_gust_hit'] for x in e),'false_ai':sum(x['wide_ai_hit'] for x in c),'false_hrrr_gust':sum(x['wide_hrrr_gust_hit'] for x in c),'wide_edge_ai':median('wide_ai_edge_frac',sub),'wide_edge_hrrr10':sum(x['wide_hrrr10_edge'] for x in sub),'wide_edge_hrrr_gust':sum(x['wide_hrrr_gust_edge'] for x in sub)}
(D/'summary_partial.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False));print(json.dumps(summary,indent=2,ensure_ascii=False))
