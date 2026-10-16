#!/usr/bin/env python3.10
"""Add-on only: provenance and 1-km land-cover strata; never rerun r1 fits."""
import csv,gzip,json,math,random,collections
from pathlib import Path
R=Path(__file__).resolve().parent
OUT=R/'metrics_r1_addendum.json'; REPORT=R/'results_r1_addendum.md'
assert not OUT.exists() and not REPORT.exists(), 'Do not overwrite existing results'
M=json.loads((R/'metrics_r1_clean.json').read_text())
LC={x['station']:x for x in csv.DictReader((R/'landcover_r1_addendum.csv').open())}
S=M['station'];assert len(S)==137 and set(S)<=set(LC)
methods=['idw','ok','era','era_resok','hrrr','hrrr_resok','gbt','gbt_resok']
acc=collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0.,0.,0.]))
byday=collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0.]))
with gzip.open(R/'predictions_r1_clean.csv.gz','rt') as f:
    for row in csv.DictReader(f):
        group=LC[row['station']]['group'];assert group!='no_data',row['station']
        obs=float(row['obs'])
        for method in methods:
            err=float(row[method])-obs
            for cat in (group,'all'):
                a=acc[cat][method];a[0]+=1;a[1]+=err**2;a[2]+=abs(err);a[3]+=err
            b=byday[row['date']][method];b[0]+=1;b[1]+=err**2

def summarize(g):
    return {m:{'n':v[0],'rmse':math.sqrt(v[1]/v[0]),'mae':v[2]/v[0],'bias':v[3]/v[0]} for m,v in acc[g].items()}
G={g:summarize(g) for g in acc}
assert G['all']['ok']['n']==M['n_observations']
for m in methods:assert abs(G['all'][m]['rmse']-M['methods'][m]['rmse'])<1e-10
counts=collections.Counter(LC[s]['group'] for s in S)
wins={g:{m:sum(S[s][m]['rmse']<S[s]['ok']['rmse'] for s in S if LC[s]['group']==g) for m in ['era_resok','hrrr_resok','gbt','gbt_resok']} for g in counts}
days=sorted(byday); rng=random.Random(2718); boots=[]
for _ in range(2000):
    draw=[days[rng.randrange(len(days))] for k in days]
    def rmse(method):
        n=sum(byday[d][method][0] for d in draw);se=sum(byday[d][method][1] for d in draw)
        return math.sqrt(se/n)
    boots.append(1-rmse('era_resok')/rmse('ok'))
boots.sort();ci=[boots[49],boots[1949]]
primary_gain=1-G['all']['era_resok']['rmse']/G['all']['ok']['rmse']
output={'source_metrics':'metrics_r1_clean.json','source_predictions':'predictions_r1_clean.csv.gz','landcover':'landcover_r1_addendum.csv','group_def':'ESA WorldCover 2021, 1 km radius circular footprint; dominant pixel class 50=built, other=nonbuilt','groups':G,'station_counts':dict(counts),'station_wins_vs_ok':wins,'primary_era_resok_gain':primary_gain,'primary_era_resok_gain_ci95':ci,'primary_station_wins':sum(v['era_resok'] for v in wins.values()),'primary_station_total':len(S),'provenance':{'era':'ERA5 land-station assimilation pending Lead audit','hrrr':'upstream analysis assimilated stations even for f01; LOO optimistic','gbt_and_gbt_resok':'training features include HRRR u/v, same upstream contamination','observation':'IEM METAR sknt, reported 2-min mean at an hourly timestamp, no gust; all timestamps UTC'}}
OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
lines=['# H r1 三处口径补充（不覆盖原结果）','','本文件与 `results_r1.md` 合读；不修改 r1 预定判据或原始分数。原结果表中 HRRR 直接、HRRR+残差 OK、GBT、GBT+残差 OK 四行在此统一标记为“上游已用该站，留一偏乐观”；GBT 特征包含 HRRR u/v，亦受影响。HRRR f01 并非站点独立预报，其初始分析场已吸收地面观测；ERA5 陆地 10 m 风是否同化地面站：待 Lead 核查，不把 ERA5 写成已证明独立。','','## 原表方法的留一污染标记','', '| 方法 | 原表 RMSE (m/s) | 口径 |','|---|---:|---|']
for m, label in [('idw','IDW²'),('ok','普通克里金'),('era','ERA5 直接'),('era_resok','ERA5+残差 OK'),('hrrr','HRRR f01 直接'),('hrrr_resok','HRRR f01+残差 OK'),('gbt','梯度提升树（含 HRRR 特征）'),('gbt_resok','梯度提升树+残差 OK（含 HRRR 特征）')]:
    flag='上游已用该站，留一偏乐观' if m.startswith('hrrr') or m.startswith('gbt') else 'ERA5 陆地站点同化待核' if m.startswith('era') else '仅其它站观测'
    lines.append(f"| {label} | {G['all'][m]['rmse']:.3f} | {flag} |")
lines+=['','主口径仅看 ERA5 背景 + 残差 OK 与纯插值的比较；GBT 两法因 HRRR 特征不作为独立候选。ERA5 同化状态待核，故主口径也不是已证实的无站点背景。',f"纯插值较优者 OK RMSE {G['all']['ok']['rmse']:.3f} m/s；ERA5+残差 OK {G['all']['era_resok']['rmse']:.3f} m/s，下降 {primary_gain:.2%}（逐日 2000 次 bootstrap 95% 区间 {ci[0]:.2%}–{ci[1]:.2%}），逐站 {output['primary_station_wins']}/{len(S)} 改善。按事先判据仍为“插值够用”。原 r1 的 5.50% 与 87/137 为含 HRRR 特征学习法的并列参考，不作主判。",'','## 观测时效与变量','','真值只用 IEM METAR `sknt`，对应报文的持续/平均风速（ASOS 通常是 2 分钟平均），不取 `gust`、不混用几秒阵风；这里的“小时”是按整点最近 ±30 min 抽一条 METAR，不是整小时风速平均。时间字段、筛选日期和配准全用 UTC。IEM 站点包括 ASOS/AWOS，个别站具体平均时长未逐站查证，不把全体无条件等同于 ASOS。依据 NOAA ASOS Wind Sensor https://www.weather.gov/asos/WindSensor.html 与 IEM API `sknt` https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help= 。','','## 站点周边下垫面分层','','ESA WorldCover 2021 v200 的 10 m 类别图，经 Microsoft Planetary Computer STAC/裁切 API，只读抽取站点中心 1 km 半径圆内有效像元，按众数分层：50=建成区主类（城区环境代理），其它众数=非建成区（机场/开阔环境的粗代理，但包括树地/水体/农地，不证明测风仪本身开阔）。有效像元不足 100 的站记缺失；145 候选站中 GVX 为缺失但未受评，137 个受评站全部可归组。类别取 2021 地表，对 2020 日有时差。比较的是预测误差与观测之间，站点周边 1 km 下垫面不同造成的空间代表性也是误差组成，不能全归于算法。','','| 1 km 周边主类 | 受评站 | 站时 | OK RMSE | ERA+残差 OK RMSE | HRRR+残差 OK RMSE（偏乐观） | GBT+残差 OK RMSE（偏乐观） | ERA+残差逐站胜 OK |','|---|---:|---:|---:|---:|---:|---:|---:|']
for g,label in [('built_majority_class','建成区主类'),('nonbuilt_majority_class','非建成区主类')]:
    q=G[g];lines.append(f"| {label} | {counts[g]} | {q['ok']['n']} | {q['ok']['rmse']:.3f} | {q['era_resok']['rmse']:.3f} | {q['hrrr_resok']['rmse']:.3f} | {q['gbt_resok']['rmse']:.3f} | {wins[g]['era_resok']}/{counts[g]} |")
lines+=['','补充参数来源表：METAR `sknt` → IEM API（风速节），ASOS 2 分钟 → NOAA Wind Sensor（AWOS 单站未核）；最近整点 ±30 min → r1 既定假设；UTC → IEM 请求 `tz=UTC` 与预测记录 ISO `+00:00`；WorldCover 2021 类别 50 → ESA v200 STAC item 的 classification；1 km 半径、圆内众数、有效像元至少 100 → 本补充预设的假设，只用于分层、不进入训练。', '', '外部数据：ESA WorldCover Consortium (2022), ESA WorldCover 2021 v200, https://doi.org/10.5281/zenodo.7254221 ; Microsoft Planetary Computer `esa-worldcover` STAC https://planetarycomputer.microsoft.com/dataset/esa-worldcover 。NOAA/NWS ASOS Wind Sensor, https://www.weather.gov/asos/WindSensor.html 。原观测/背景数据来源见 `results_r1.md` [1]–[4]。工作仅限 `06_Logs/obs_fusion/`，本页新增引用尚须由 Lead 补到 `PUBLIC_CITATIONS.md`。', '', '未覆盖 `results_r1.md`、`metrics_r1_clean.json` 等既有结果；分层及统计分别见 `landcover_r1_addendum.csv`、`metrics_r1_addendum.json`，复现脚本为 `landcover_r1_addendum.py` 和 `make_r1_addendum.py`。']
REPORT.write_text('\n'.join(lines)+'\n')
print('saved',OUT,REPORT,'primary_gain',primary_gain,'wins',output['primary_station_wins'],'groups',counts,'rows',sum(G[g]['ok']['n'] for g in counts))
