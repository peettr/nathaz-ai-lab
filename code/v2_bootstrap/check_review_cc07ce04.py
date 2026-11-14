# 11-07 裁决 cc07ce04 时的只读核对：等权宏平均读法、逐站比、预报超阈条件计数
import csv,random,collections,json
from pathlib import Path
S='./22_Lab/06_Logs/e_terrain/v2/paired_main_v2_raw.csv'
R=[r for r in csv.DictReader(open(S)) if r['period']=='test']
f=lambda x: float(x) if x not in('','nan','NaN') else None
for r in R:
  for k in('obs_ms','p90','p99','bilinear_ms','wn_ms','mos_ms','wn_mos_ms'): r[k]=f(r[k])
st=[r for r in R if r['obs_ms']>=r['p90']]
g=collections.defaultdict(list)
for r in st: g[r['station']].append(r)
mae=lambda rs,c: sum(abs(r[c]-r['obs_ms']) for r in rs)/len(rs)
per={s:1-mae(v,'wn_ms')/mae(v,'bilinear_ms') for s,v in g.items()}
def macroA(ss): return 1-sum(mae(g[s],'wn_ms') for s in ss)/sum(mae(g[s],'bilinear_ms') for s in ss)
def macroB(ss): return sum(per[s] for s in ss)/len(ss)
stn=sorted(g); rng=random.Random(20261107); A=[];B=[]
for _ in range(10000):
  p=[rng.choice(stn) for _ in stn]; A.append(macroA(p)); B.append(macroB(p))
A.sort();B.sort()
ci=lambda v:(v[250],v[9749])
cnt={}
for c in('bilinear_ms','wn_ms','mos_ms','wn_mos_ms'):
  av=[r for r in R if r[c] is not None]; al=[r for r in av if r[c]>=r['p99']]
  cnt[c]={'forecast_ge_p99':len(al),'hits':sum(r['obs_ms']>=r['p99'] for r in al),'obs_events':sum(r['obs_ms']>=r['p99'] for r in av)}
out={'per_station_R1':per,'max_station_R1':max(per.values()),'macroA_point':macroA(stn),'macroA_ci':ci(A),'macroB_point':macroB(stn),'macroB_ci':ci(B),'forecast_conditioned_p99':cnt}
Path('check_review_cc07ce04.json').write_text(json.dumps(out,indent=1,ensure_ascii=False)); print(json.dumps(out,indent=1))
