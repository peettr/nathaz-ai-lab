import csv, json, random, collections, sys
from pathlib import Path
SRC=Path('./22_Lab/06_Logs/e_terrain/v2/paired_main_v2_raw.csv')
OUT=Path(__file__).resolve().parent
rows=[r for r in csv.DictReader(SRC.open()) if r['period']=='test']
f=lambda x: float(x) if x not in ('','nan','NaN') else None
for r in rows:
    for k in ('obs_ms','p90','bilinear_ms','mos_ms','wn_ms','wn_mos_ms'): r[k]=f(r[k])
    r['day']=r['valid_utc'][:10]
strong=[r for r in rows if r['obs_ms']>=r['p90']]
def mae(rs,c): v=[abs(r[c]-r['obs_ms']) for r in rs if r[c] is not None]; return sum(v)/len(v)
def stats(S,A):
    b,w,m,wm=(mae(S,c) for c in ('bilinear_ms','wn_ms','mos_ms','wn_mos_ms'))
    return {'R1':1-w/b,'D1':w-b,'R3':1-wm/m,'D3':wm-m,'D4':mae(A,'wn_ms')-mae(A,'bilinear_ms')}
pt=stats(strong,rows)
pe={c:round(mae(strong,c),2) for c in ('bilinear_ms','wn_ms','mos_ms','wn_mos_ms')}
pa={c:round(mae(rows,c),2) for c in ('bilinear_ms','wn_ms')}
assert len(strong)==207 and len(rows)==2131, (len(strong),len(rows))
assert pe=={'bilinear_ms':6.38,'wn_ms':6.70,'mos_ms':3.25,'wn_mos_ms':3.50}, pe
assert pa=={'bilinear_ms':3.04,'wn_ms':3.09}, pa
def group(rs,key):
    g=collections.defaultdict(list)
    for r in rs: g[r[key]].append(r)
    return g
gs_s,gs_a=group(strong,'station'),group(rows,'station')
gd_s,gd_a=group(strong,'day'),group(rows,'day')
stations=sorted(gs_a); days=sorted(gd_a)
B=10000
def boot(kind):
    rng=random.Random(20261107); out=collections.defaultdict(list)
    for _ in range(B):
        if kind=='station':
            pick=[rng.choice(stations) for _ in stations]
            S=[r for s in pick for r in gs_s.get(s,[])]; A=[r for s in pick for r in gs_a[s]]
        elif kind=='day':
            pick=[rng.choice(days) for _ in days]
            S=[r for d in pick for r in gd_s.get(d,[])]; A=[r for d in pick for r in gd_a[d]]
        else:
            ps=[rng.choice(stations) for _ in stations]; pd=[rng.choice(days) for _ in days]
            cnt=collections.Counter(pd)
            S=[r for s in ps for r in gs_s.get(s,[]) for _ in range(cnt.get(r['day'],0))]
            A=[r for s in ps for r in gs_a[s] for _ in range(cnt.get(r['day'],0))]
        if not S: continue
        for k,v in stats(S,A).items(): out[k].append(v)
    res={}
    for k,v in out.items():
        v.sort(); n=len(v); res[k]={'lo':v[int(0.025*n)],'hi':v[int(0.975*n)-1],'n':n}
    return res
res={k:boot(k) for k in ('station','day','station_x_day')}
# per-station strong (wins)
per={s:{'n':len(v),'bil':mae(v,'bilinear_ms'),'wn':mae(v,'wn_ms')} for s,v in gs_s.items()}
wins=sum(1 for v in per.values() if v['wn']<v['bil'])
resolve=all(res[k]['R1']['hi']<0.15 for k in ('station','day'))
resolve3=all(res[k]['R3']['hi']<0.15 for k in ('station','day'))
J={'source':str(SRC),'B':B,'seed':20261107,'strong_n':len(strong),'test_n':len(rows),'n_days':len(days),'n_days_with_strong':len(gd_s),
   'point':pt,'point_mae_strong':pe,'point_mae_all':pa,'ci95':res,'station_wins':wins,'per_station':per,
   'resolving_power_G1':resolve,'resolving_power_G3_aux':resolve3}
(OUT/'bootstrap_v2_results.json').write_text(json.dumps(J,indent=2,ensure_ascii=False))
L=['# E 示范 v2 自助法区间结果（方法见 METHOD_bootstrap_20261107.md）','',
   f'强风 {len(strong)} 条 / 全时次 {len(rows)} 条；12 站；检验期 {len(days)} 天（含强风 {len(gd_s)} 天）；B={B}，种子 20261107。点估计复核与 results_v2.md 一致。','',
   '|统计量|点估计|站点自助 95%|日块自助 95%|站×日（敏感性）|','|---|---:|---:|---:|---:|']
lab={'R1':'G1 强风相对降幅 1−WN/插值','D1':'G1 强风 MAE 差 WN−插值 (m/s)','R3':'G3 订正后相对降幅 1−(WN+MOS)/(插值+MOS)','D3':'G3 订正后 MAE 差 (m/s)','D4':'G4 全时次 MAE 差 WN−插值 (m/s)'}
for k in ('R1','D1','R3','D3','D4'):
    fm=(lambda x:f'{100*x:.1f}%') if k.startswith('R') else (lambda x:f'{x:+.3f}')
    L.append(f"|{lab[k]}|{fm(pt[k])}|[{fm(res['station'][k]['lo'])}, {fm(res['station'][k]['hi'])}]|[{fm(res['day'][k]['lo'])}, {fm(res['day'][k]['hi'])}]|[{fm(res['station_x_day'][k]['lo'])}, {fm(res['station_x_day'][k]['hi'])}]|")
L+=['',f'G2 胜出站数 {wins}/12（复核）。',f'分辨力判定（G1，两种主方案上限均 <15%）：{"有分辨力" if resolve else "分辨力不足"}；G3 辅助：{"上限均 <15%" if resolve3 else "有方案上限 ≥15%"}。']
(OUT/'bootstrap_v2_results.md').write_text('\n'.join(L)+'\n')
print('\n'.join(L))
