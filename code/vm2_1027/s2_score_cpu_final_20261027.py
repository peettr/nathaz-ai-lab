"""Frozen R23.4b S2 reduction. Run on Colab CPU after all GPU sessions stop.
No cohort/threshold selection is learned from predictions. Requires all three immutable segments.
"""
import csv
import datetime as dt
import hashlib
import json
import pathlib
from collections import defaultdict
import numpy as np

ROOT = pathlib.Path('./23_AI_Weather/06_Logs/convective_r3/s2/vm2_1027/score_cpu_final')
ROOT.mkdir(exist_ok=False)
IN = pathlib.Path('./23_AI_Weather/06_Logs/convective_r3')
segments = [pathlib.Path('./23_AI_Weather/06_Logs/convective_r3/s2/vm2_1027/s2_merged_0_239_20261027.jsonl')]
events = [r for r in csv.DictReader((IN/'events_r3.csv').open()) if r['group']=='v1']
controls = [r for r in csv.DictReader((IN/'controls_r3.csv').open()) if r['group']=='v1']
assert len(events)==len(controls)==120
assert [r['id'] for r in events]==[r['event_id'] for r in controls]
units = [(kind,r) for e,c in zip(events,controls) for kind,r in [('event',e),('control',c)]]
assert len(units)==240
rows = defaultdict(list)
errors = defaultdict(list)
for path in segments:
    assert path.is_file() and path.stat().st_size>0, path
    for line in path.open():
        if not line.strip(): continue
        row=json.loads(line)
        i=int(row['unit_index']); key=(i,row['kind'],row.get('seed'))
        assert 0<=i<240
        assert 0<=i<240, (path,i)
        (rows if row['status']=='ok' else errors)[key].append(row)
assert all(len(v)==1 for v in rows.values()), 'duplicate success key'

out=[]; exclusions=[]; variants=[]
for i,(kind,source) in enumerate(units):
    baseline=rows.get((i,'baseline',None),[])
    members=[rows.get((i,'member',s),[]) for s in range(101,111)]
    if len(baseline)!=1 or any(len(m)>1 for m in members) or sum(bool(m) for m in members)<8:
        exclusions.append({'unit_index':i,'reason':'baseline missing or <8 valid members', 'n':sum(bool(m) for m in members)}); continue
    b=baseline[0]; m=[x[0] for x in members if x]
    if b['event_id']!=(source['id'] if kind=='event' else source['event_id']): raise AssertionError((i,'id'))
    if b.get('fg_wide') is None or b.get('fg_narrow') is None:
        exclusions.append({'unit_index':i,'reason':'HRRR window missing'}); continue
    try:
        a=np.array([float(x['methods']['diagnostic']['wide']['ms']) for x in m])
        an=np.array([float(x['methods']['diagnostic']['narrow']['ms']) for x in m])
        factor=np.array([float(x['methods']['factor16777']['wide']['ms']) for x in m])
        heur=np.array([float(x['methods']['hrrrcast_without_vvel']['wide']['ms']) for x in m])
        h=float(b['fg_wide']['ms']); hn=float(b['fg_narrow']['ms'])
        obs=float(source['obs_kt'] if kind=='event' else source['max_kt'])*0.514444
        assert np.isfinite(a).all() and np.isfinite(an).all() and np.isfinite([h,hn,obs]).all()
    except (ValueError,TypeError,KeyError) as ex:
        exclusions.append({'unit_index':i,'reason':'observation/peak missing: '+repr(ex)});continue
    nonmono=sum(x['nonmonotonic_columns'] for x in m); columns=sum(x['columns'] for x in m)
    assert columns>0
    out.append(dict(unit_index=i,kind=kind,event_id=b['event_id'],utc=source['utc'],utc_day=source['utc'][:10],year=source['year'],
                    n=len(m),obs_ms=obs,ai_p=float(np.mean(a>=25.7)),hrrr_p=float(h>=25.7),
                    ai_median_ms=float(np.median(a)),ai_max_ms=float(np.max(a)),hrrr_ms=h,
                    ai_narrow_median_ms=float(np.median(an)),hrrr_narrow_ms=hn,
                    any_member_hit=int(np.any(a>=25.7)),factor_median_ms=float(np.median(factor)),heur_median_ms=float(np.median(heur)),
                    hrrr_formula_ms=float(b['hrrr_formula_wide']['ms']) if b.get('hrrr_formula_wide') else None,
                    nonmono_fraction=nonmono/columns,nonmono_flag=int(nonmono/columns>0.20),
                    ai_min_ms=float(np.min(a)),ai_upper_ms=float(np.max(a)),
                    ai_edge_km_median=float(np.median([x['methods']['diagnostic']['wide']['edge_km'] for x in m]))))
    variants.append(dict(utc_day=source['utc'][:10],kind=kind,method_a=(a,h),factor16777=(factor,h),hrrrcast_without_vvel=(heur,h),hrrr_same_formula=(a,float(b['hrrr_formula_wide']['ms'])),narrow=(an,hn)))

assert not exclusions, f'Cannot score full frozen cohort: {len(exclusions)} missing units; {exclusions[:5]}'
assert len(out)==240 and sum(x['kind']=='event' for x in out)==120 and sum(x['kind']=='control' for x in out)==120
with (ROOT/'unit_scores.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(out[0]));writer.writeheader();writer.writerows(out)
vm1_source=IN/'s2/ckpt_20_130_1022_0330_rescue.jsonl'
vm1_errors=[json.loads(line) for line in vm1_source.open() if 'No space left on device' in line]
assert len(vm1_errors)==10 and {x['unit_index'] for x in vm1_errors}=={120} and {x['seed'] for x in vm1_errors}==set(range(101,111))
(ROOT/'key_audit.json').write_text(json.dumps({'units':len(out),'member_success':sum(x['n'] for x in out),'success_rows':len(rows),'error_rows':sum(map(len,errors.values())),'additional_vm1_disk_full_errors':len(vm1_errors),'additional_vm1_disk_full_source':str(vm1_source),'additional_vm1_disk_full_unit_index':120,'error_rows_scope':'merged input only; VM1 failures separately counted','excluded':exclusions},indent=2))

def vals(z,key):return np.array([x[key] for x in z],dtype=float)
def metrics(z):
    e=[x for x in z if x['kind']=='event'];c=[x for x in z if x['kind']=='control']
    if not e or not c:return None
    y=vals(z,'kind_event') if False else np.array([int(x['kind']=='event') for x in z])
    pa=vals(z,'ai_p');ph=vals(z,'hrrr_p')
    hit_a=float(np.mean(vals(e,'ai_p')>=.3));hit_h=float(np.mean(vals(e,'hrrr_p')>=.3))
    false_a=float(np.mean(vals(c,'ai_p')>=.3));false_h=float(np.mean(vals(c,'hrrr_p')>=.3))
    ratios=vals(e,'ai_median_ms')/vals(e,'hrrr_ms')
    prevalence=float(y.mean()); bsref=prevalence*(1-prevalence)
    bsa=float(np.mean((pa-y)**2));bsh=float(np.mean((ph-y)**2))
    return dict(n=len(z),events=len(e),controls=len(c),bs_ai=bsa,bs_hrrr=bsh,bs_diff=bsa-bsh,
                bss_ai_1to1=1-bsa/bsref,bss_hrrr_1to1=1-bsh/bsref,
                hit_ai=hit_a,hit_hrrr=hit_h,hit_diff=hit_a-hit_h,
                false_ai=false_a,false_hrrr=false_h,false_diff=false_a-false_h,
                peak_ratio_median=float(np.median(ratios)),peak_ratio_sample=[float(v) for v in ratios])
point=metrics(out);assert point
rng=np.random.default_rng(20261016)
byday=defaultdict(list)
for x in out:byday[x['utc_day']].append(x)
days=list(byday);rep=[]; draws=[]
for _ in range(5000):
    ds=rng.choice(len(days),len(days),replace=True)
    draws.append(ds)
    m=metrics([x for j in ds for x in byday[days[j]]])
    if m is not None:rep.append({k:m[k] for k in ('bs_diff','hit_diff','false_diff','peak_ratio_median')})
assert len(rep)>=4900, len(rep)
ci={k:dict(lower05=float(np.percentile([v[k] for v in rep],5)),upper95=float(np.percentile([v[k] for v in rep],95))) for k in rep[0]}
# The peak ratio uses the prespecified central 90% bootstrap interval, also 5th/95th percentiles.
pass_bs=ci['bs_diff']['upper95']<0.02
pass_hit=ci['hit_diff']['lower05']>-0.15 and point['hit_diff']>=-0.05
pass_false=ci['false_diff']['upper95']<0.15 and point['false_diff']<=0.05
pass_peak=point['peak_ratio_median']>=0.9
false_distinguishable=not (point['false_ai']<=.05 and point['false_hrrr']<=.05 and ci['false_diff']['lower05']<=0<=ci['false_diff']['upper95'])  # prereg §1.3
# Development evaluation period: all 2022 + inclusive 2024-05-08 through 2024-06-15.
def dev(x):return x['utc_day'][:4]=='2022' or ('2024-05-08'<=x['utc_day']<='2024-06-15')
sensitivity=metrics([x for x in out if not dev(x)])
# Rank all units; primary key P and tie-breaker member median peak. HRRR deterministic fg10m.
topk={}
for label,ranked in [('ai',sorted(out,key=lambda x:(x['ai_p'],x['ai_median_ms']),reverse=True)),
                     ('hrrr',sorted(out,key=lambda x:x['hrrr_ms'],reverse=True))]:
    topk[label]={str(k):{'event_fraction':sum(x['kind']=='event' for x in ranked[:k])/k,
                          'event_count':sum(x['kind']=='event' for x in ranked[:k])} for k in (12,24,60,120)}
cover=sum(x['ai_min_ms']<=x['obs_ms']<=x['ai_upper_ms'] for x in out if x['kind']=='event')/120
# ROC AUC from ranks with 0.5 credit for ties.
a=vals([x for x in out if x['kind']=='event'],'ai_p');b=vals([x for x in out if x['kind']=='control'],'ai_p')
auc=float(np.mean((a[:,None]>b[None,:])+.5*(a[:,None]==b[None,:])))
reliability=[]
for lo,hi in ((0,.1),(.1,.3),(.3,.6),(.6,1.000001)):
    subset=[x for x in out if lo<=x['ai_p']<hi]
    reliability.append(dict(lo=lo,hi=hi,n=len(subset),mean_p=float(np.mean(vals(subset,'ai_p'))) if subset else None,
                            event_fraction=float(np.mean([x['kind']=='event' for x in subset])) if subset else None))
result=dict(definitions={'bs_diff':'mean[(P_AI-y)^2]-mean[(P_HRRR-y)^2], y=1 event, 0 control',
                         'hit_diff':'mean_event[1(P_AI>=0.3)]-mean_event[1(P_HRRR>=0.3)]',
                         'false_diff':'mean_control[1(P_AI>=0.3)]-mean_control[1(P_HRRR>=0.3)]',
                         'peak_ratio':'median_event[median_member(peak_AI)/peak_HRRR]',
                         'bss_1to1':'1-BS/[sample prevalence*(1-sample prevalence)]',
                         'bootstrap':'UTC day clusters, 5000 draws, numpy default_rng(20261016), percentile 5/95'},
            point=point,ci=ci,bootstrap_valid=len(rep),
            gates=dict(brier=pass_bs,hit=pass_hit,false_alarm=pass_false,peak=pass_peak,
                       false_alarm_distinguishable=false_distinguishable,
                       all_numerical=all((pass_bs,pass_hit,pass_false,pass_peak)),
                       verdict='未通过：BS、命中、峰值比不过；误报数值肢满足但两边接近0，按预注册§1.3记无区分力，不作通过证据'),
            topk=topk,coverage_event_minmax=cover,coverage_hazard='雷暴（仅一种灾种）',auc=auc,
            reliability=reliability,developer_period_excluded=dict(removed=sum(dev(x) for x in out),metrics=sensitivity),
            diagnostic=dict(nonmono_flagged=[x['unit_index'] for x in out if x['nonmono_flag']],
                            nonmono_fraction_median=float(np.median(vals(out,'nonmono_fraction'))),
                            narrow_ai_event_median=float(np.median(vals([x for x in out if x['kind']=='event'],'ai_narrow_median_ms'))),
                            narrow_hrrr_event_median=float(np.median(vals([x for x in out if x['kind']=='event'],'hrrr_narrow_ms'))),
                            any_member_hit_events=int(sum(x['any_member_hit'] for x in out if x['kind']=='event'))))
# Report-only, post-hoc variants use the identical 5000 daily cluster draws.
def alternative(z,name):
    if not z:return None
    y=np.array([int(x['kind']=='event') for x in z]);ev=y==1;ct=~ev
    if not ev.any() or not ct.any():return None
    pairs=[x[name] for x in z]
    pa=np.array([float(np.mean(a>=25.7)) for a,h in pairs]);ph=np.array([float(h>=25.7) for a,h in pairs])
    ratios=np.array([float(np.median(a)/h) for a,h in pairs])
    return dict(bs_diff=float(np.mean((pa-y)**2)-np.mean((ph-y)**2)),hit_ai=float(np.mean(pa[ev]>=.3)),hit_hrrr=float(np.mean(ph[ev]>=.3)),hit_diff=float(np.mean(pa[ev]>=.3)-np.mean(ph[ev]>=.3)),false_ai=float(np.mean(pa[ct]>=.3)),false_hrrr=float(np.mean(ph[ct]>=.3)),false_diff=float(np.mean(pa[ct]>=.3)-np.mean(ph[ct]>=.3)),peak_ratio_median=float(np.median(ratios[ev])),hit_ai_count=int(sum(pa[ev]>=.3)),hit_hrrr_count=int(sum(ph[ev]>=.3)),false_ai_count=int(sum(pa[ct]>=.3)),false_hrrr_count=int(sum(ph[ct]>=.3)))
assert len(variants)==len(out)
vdays=defaultdict(list)
for x in variants:vdays[x['utc_day']].append(x)
assert list(vdays)==days
report_only={}
for name in ('method_a','factor16777','hrrrcast_without_vvel','hrrr_same_formula','narrow'):
    vp=alternative(variants,name)
    bootstrap=[alternative([x for j in ds for x in vdays[days[j]]],name) for ds in draws]
    bootstrap=[m for m in bootstrap if m is not None]
    assert len(bootstrap)>=4900
    keys=('bs_diff','hit_ai','hit_hrrr','hit_diff','false_ai','false_hrrr','false_diff','peak_ratio_median')
    vci={k:dict(lower05=float(np.percentile([v[k] for v in bootstrap],5)),upper95=float(np.percentile([v[k] for v in bootstrap],95))) for k in keys}
    report_only[name]=dict(point=vp,ci=vci,bootstrap_valid=len(bootstrap))
expected={'method_a':(.0705,12,33,3,4,.863),'factor16777':(.0402,23,33,4,4,.907),'hrrrcast_without_vvel':(-.0277,46,33,16,4,1.161),'hrrr_same_formula':(.0621,12,32,3,5,.863)}
for name,(bs,ha,hh,fa,fh,peak) in expected.items():
    v=report_only[name]['point']
    assert abs(v['bs_diff']-bs)<.000051 and abs(v['peak_ratio_median']-peak)<.00051,(name,v)
    assert (v['hit_ai_count'],v['hit_hrrr_count'],v['false_ai_count'],v['false_hrrr_count'])==(ha,hh,fa,fh),(name,v)
assert all(report_only['method_a']['point'][k]==point[k] for k in ('bs_diff','hit_ai','hit_hrrr','hit_diff','false_ai','false_hrrr','false_diff','peak_ratio_median'))
assert all(report_only['method_a']['ci'][k]==ci[k] for k in ('bs_diff','hit_diff','false_diff','peak_ratio_median'))
corrected=json.loads((ROOT.parent/'score_cpu_corrected/score.json').read_text())
assert result['point']==corrected['point'] and result['ci']==corrected['ci']
assert all(result['gates'][k]==corrected['gates'][k] for k in ('brier','hit','false_alarm','peak','all_numerical'))
result['report_only']=report_only
result['report_only_status']='只报告、事后、不改判据；UTC日簇5000次seed=20261016，与主判据共用抽样日序列'
(ROOT/'score.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax=plt.subplots(1,2,figsize=(10,4))
px=[v['mean_p'] for v in reliability if v['n']]
py=[v['event_fraction'] for v in reliability if v['n']]
ax[0].plot([0,1],[0,1],'k--',linewidth=1)
ax[0].plot(px,py,'o-',label='AI; case-control sample')
ax[0].set(xlim=(0,1),ylim=(0,1),xlabel='Mean predicted P',ylabel='Event fraction',title='Reliability (not operational)')
ax[0].legend()
thresholds=sorted(set(float(x['ai_p']) for x in out),reverse=True)
roc=[(0.,0.)]
for th in thresholds:
    roc.append((float(np.mean(b>=th)),float(np.mean(a>=th))))
roc.append((1.,1.))
ax[1].plot([0,1],[0,1],'k--',linewidth=1)
ax[1].plot(*zip(*roc),marker='.',label=f'AI AUC={auc:.3f}')
ax[1].set(xlim=(0,1),ylim=(0,1),xlabel='False positive rate',ylabel='True positive rate',title='ROC')
ax[1].legend();fig.tight_layout();fig.savefig(ROOT/'reliability_roc.png',dpi=160);plt.close(fig)
# Compact report generated from score.json, not manually transcribed.
# Calculate at runtime: a script cannot embed its own fixed SHA-256 literal.
script_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
def fm(v):return f'{v:.6f}'
lines=['# R23.4b S2 结论草案（程序生成）','',
       '限定：StormCast V1 + HRRR 分析初值/ERA5 条件场 + 2 h 回报 + Benjamin 2020 方法a（含D4/D5）+10成员P≥0.3/成员中位聚合；冻结雷暴事件与配对对照，不是业务实时预报。',
       '数据与脚本：修正版 `s2_score_cpu_corrected_20261027.py` + 合并输入 `s2_merged_0_239_20261027.jsonl`；本定稿由 `s2_score_cpu_final_20261027.py` 生成 `score.json`、`unit_scores.csv`、`key_audit.json`。',
       f'新脚本 `s2_score_cpu_final_20261027.py` SHA-256：{script_sha256}。',
       '核对 corrected 版（逐位相同；点估计 [日簇5000次bootstrap 5/95区间]）：' + '；'.join(f"{label}={fm(point[k])} [{fm(ci[k]['lower05'])},{fm(ci[k]['upper95'])}]" for label,k in [('BS差','bs_diff'),('命中差','hit_diff'),('误报差','false_diff'),('峰值比','peak_ratio_median')]) + '；数值合取闸门逐位一致。',
       f"样本：事件 {point['events']}，对照 {point['controls']}，有效 bootstrap {len(rep)} / 5000；缺失/剔除 0。",'',
       'BS 差 = 事件与对照等权合并的 mean[(P_AI−y)²] − mean[(P_HRRR−y)²]，y=事件1/对照0。',
       f"BS_AI={fm(point['bs_ai'])}，BS_HRRR={fm(point['bs_hrrr'])}，差={fm(point['bs_diff'])}；单侧95%上界={fm(ci['bs_diff']['upper95'])}；界限 <+0.02：{'通过' if pass_bs else '不通过'}。",
       'BSS = 1 − BS / [样本事件率×(1−样本事件率)]，仅以本次人为1:1抽样作参照，不能视为业务气候概率技巧。',
       f"BSS_AI={fm(point['bss_ai_1to1'])}，BSS_HRRR={fm(point['bss_hrrr_1to1'])}。",
       '命中差 = 事件上 mean[1(P_AI≥0.3)] − mean[1(P_HRRR≥0.3)]。',
       f"命中率 AI/HRRR={fm(point['hit_ai'])}/{fm(point['hit_hrrr'])}，差={fm(point['hit_diff'])}，单侧95%下界={fm(ci['hit_diff']['lower05'])}；下界 >−0.15 且点估计 ≥−0.05：{'通过' if pass_hit else '不通过'}。",
       '误报差 = 对照上 mean[1(P_AI≥0.3)] − mean[1(P_HRRR≥0.3)]。',
       f"误报率 AI/HRRR={fm(point['false_ai'])}/{fm(point['false_hrrr'])}，差={fm(point['false_diff'])}，单侧95%上界={fm(ci['false_diff']['upper95'])}；上界 <+0.15 且点估计 ≤+0.05：数值肢{'满足' if pass_false else '不满足'}，但两边接近0，按预注册§1.3记无区分力，不作通过证据。",
       '峰值比 = 事件上 median[AI 十成员窗口峰值的中位数 / HRRR fg10m 窗口峰值]。',
       f"峰值比={fm(point['peak_ratio_median'])}，日簇 bootstrap 90% 区间=[{fm(ci['peak_ratio_median']['lower05'])},{fm(ci['peak_ratio_median']['upper95'])}]；阈值 ≥0.9：{'通过' if pass_peak else '不通过'}。",
       f"冻结合取：{result['gates']['verdict']}。BS区间[{fm(ci['bs_diff']['lower05'])},{fm(ci['bs_diff']['upper95'])}]整段高于+0.02；命中区间[{fm(ci['hit_diff']['lower05'])},{fm(ci['hit_diff']['upper95'])}]整段低于点估计门槛−0.05（但跨越−0.15）；峰值比仅点估计不过，90%区间跨越0.9。",'',
       'Top-k 捕获率 = 前 k 单元中事件数/k；AI 按 P 降序、同 P 按十成员中位峰值降序，HRRR 按 fg10m 峰值降序。']
for k in (12,24,60,120):
    lines.append(f"k={k}：AI {topk['ai'][str(k)]['event_count']}/{k}，HRRR {topk['hrrr'][str(k)]['event_count']}/{k}。")
lines += [f"雷暴单灾种事件覆盖率：十成员最小峰值 ≤ 实测阵风 ≤ 十成员最大峰值，比例={fm(cover)}（非标称置信区间）。",
          f"ROC AUC={fm(auc)}，分档可靠性详见 score.json（样本1:1，不代表真实业务发生率）。",
          f"去开发者评价期敏感性：删除 {sum(dev(x) for x in out)} 单元后，事件 {sensitivity['events']}、对照 {sensitivity['controls']}，BS差={fm(sensitivity['bs_diff'])}，命中差={fm(sensitivity['hit_diff'])}，误报差={fm(sensitivity['false_diff'])}，峰值比={fm(sensitivity['peak_ratio_median'])}；只报告，不改主判据。",
          f"D5 1 km 内层高不单调列占比 >20% 的单元：{result['diagnostic']['nonmono_flagged']}；并未据此剔除或更改阵风值。",
          '', '## 只报告项汇总',
          '五种口径只报告、事后、不改判据；每格为点估计 [UTC日簇5000次bootstrap 5/95区间]。事件/对照同日成簇，AI/HRRR成对；率差及BS差为配对区间，不是两边区间相减。',
          '| 口径 | BS差 | 命中AI/HRRR | 命中差 | 误报AI/HRRR | 误报差 | 峰值比 |',
          '|---|---|---|---|---|---|---|']
for name,label in [('method_a','方法a（主判据重列）'),('factor16777','1.6677系数'),('hrrrcast_without_vvel','HRRRCast无VVEL启发式'),('hrrr_same_formula','方法a对HRRR同公式副对照'),('narrow','窄窗（方法a/HRRR fg10m）')]:
    vp=report_only[name]['point'];vc=report_only[name]['ci']
    def cell(k):return f"{fm(vp[k])} [{fm(vc[k]['lower05'])},{fm(vc[k]['upper95'])}]"
    lines.append('| '+ ' | '.join((label,cell('bs_diff'),cell('hit_ai')+' / '+cell('hit_hrrr'),cell('hit_diff'),cell('false_ai')+' / '+cell('false_hrrr'),cell('false_diff'),cell('peak_ratio_median'))) + ' |')
lines += ['命中/误报计数（事件/对照各120）：方法a 12/33、3/4；1.6677 23/33、4/4；启发式 46/33、16/4；同公式副对照 12/32、3/5；窄窗 2/7、0/1。',
          '同公式副对照排查 HRRR 公式实现；同一批 AI 场换口径点估计变化大。无口径四项全过，启发式误报差 +0.10 > +0.05。剩余归因（AI 场偏弱 vs 方法a与AI低层结构的相互作用）未拆开，不否定其他阵风诊断。',
          '35 dBZ：事件侧样本与40 dBZ同一（S0 终态 578 条全过），主判据不变；对照未另配。',
          'key_audit.json 的 error_rows 只计合并输入的单元0重试错误10条；另有 VM1 单元120 的10条磁盘满失败，已单独标注，均不计成功键。',
          '']
lines += [
          '自查：结论仅限本样本/配置；上述差值和比值先定义后列数；判据为 BS 上界严格 <0.02，命中下界严格 >−0.15 且点估计 ≥−0.05，误报上界严格 <0.15 且点估计 ≤0.05，峰值比 ≥0.9，bootstrap 的5/95百分位。',
          '限制：模型输入为起报时刻 HRRR 分析与 ERA5 回报条件场，不应称为起报时刻可获得的业务实时条件场；受人为1:1事件/对照设计与非近阈对照限制。',
          '', '## 结论',f"本次冻结 V1 雷暴样本的 S2 主闸门：{result['gates']['verdict']}。停止类别记否定结果，严格限于上述含 Benjamin 2020 方法a 的冻结配置；剩余归因未拆开，不否定 StormCast V1 配其他阵风诊断，不能外推到业务实时预报或其他灾种。按预注册§6不跑S4，S3不自动开。"]
(ROOT/'S2_结论草案.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'units':len(out),'gates':result['gates'],'out':str(ROOT)},ensure_ascii=False),flush=True)
