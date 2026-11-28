import csv,json,statistics,collections
from pathlib import Path
P=Path(__file__).resolve().parent
D=P.parent
rows=list(csv.DictReader((P/'a_v3_r2_main.csv').open()))
stations=list(csv.DictReader((D/'run_a/inputs_v2/stations.csv').open()))
parallel={(r['event'],r['station']) for r in stations if r['parallel_eligible']=='yes_unverified_height'}
events=sorted({r['event'] for r in stations})
summary=json.loads((P/'v3_summary.json').read_text()); main=summary['main']
assert len(events)==15 and len(rows)==len(stations)==79
assert len(parallel)==61 and main['exit']=='0'

def fmt(x): return '—' if x is None else f'{x*100:+.2f}%' 
lines=['# R23.3a-04 v3 (a) 链结果（BEST；仅本配置和 15 个事件）','',
'定义：e = pred_peak_10m/obs_peak_10m − 1；B = median_station(e)；M = median_station(|e|)。分母为同站 10 m 高度订正的小时持续风观测峰，非阵风。先满足 15 个意向事件各≥3 个共同可评站，才能用 B 的 ±20%（含边界）判 (a)；只跑 (a) 还不能声称三链共同站已核。8–12 m 只描述。所有事件日风速计高度仍是 2025 清单代理，历史高度未证实。','',
'冻结：`../prereg_v3/FREEZE_v3.md`、`FREEZE_v3_SHA256.txt`，先于任何 v3 配对。原冻结脚本第一次运行在 QC 变量名遮蔽处错误退出；实现修补、失败尝试见 `POST_FREEZE_CHANGES.md` 与 `post_freeze_r1.diff`，未更改资格和判据。成功运行脚本 `../prereg_v3/chain_a_v3_r1.py`；Colab CPU `a_v3_r2_main.exit=0`，逐站 `a_v3_r2_main.csv`。','',
'主池元数据 79 站–事件、15/15 例各≥3；实际 (a) 可评 69 站–事件，只有 13/15 例各≥3（HELENE 2、IDA 1）。因此 15×3 必要条件不满足，主 B/M 的闸门值与 ±20% 判词均为“不判闸”，绝非“未过 ±20%”。候选 69 站的非判闸描述 B='+fmt(main['stats']['primary']['B'])+'、M='+fmt(main['stats']['primary']['M'])+'；不得以此放行或宣布未过。由于 (b)(c) 未运行，三链共同交集也未验证。','',
'8–12 m 并列池元数据 61 站–事件、13/15 例各≥3；实际可评 '+str(main['stats']['parallel']['n'])+' 站–事件，'+str(main['stats']['parallel']['events_ge3'])+'/15 例各≥3；仅描述 B='+fmt(main['stats']['parallel']['B'])+'、M='+fmt(main['stats']['parallel']['M'])+'，不判闸。','',
'| 事件 | 主元数据 | 主有效 | 并列元数据 | 并列有效 | RMW 一/二/三/四级节点 | 无效站及原因（观测峰下界，原高 kt；无有限上界） |','|---|---:|---:|---:|---:|---|---|']
for e in events:
    rr=[r for r in rows if r['event']==e];p=[r for r in rr if (e,r['station']) in parallel]
    tiers=main['tiers'][e];tier='/'.join(str(tiers.get(str(i),0)) for i in range(1,5))
    reasons=[]
    for r in rr:
        if r['error']:continue
        q=json.loads(r['qc']); reasons.append(r['station']+': '+','.join(k for k in ('coverage','edge','peak_window','invalid_reports') if (q[k]<18 if k=='coverage' else not q[k] if k in ('edge','peak_window') else q[k]>0))+'; 下界 '+str(q['obs_peak_lower_bound']))
    lines.append('| '+e+' | '+str(len(rr))+' | '+str(sum(bool(r['error']) for r in rr))+' | '+str(len(p))+' | '+str(sum(bool(r['error']) for r in p))+' | '+tier+' | '+('<br>'.join(reasons) if reasons else '—')+' |')
lines+=['','逐站 QC 字典另见 CSV：覆盖率、首末窗口、模型峰四格、物理异常报告、扩窗与截尾。截尾站只给已经观测到的原高持续风峰下界，不能换成有限上界；不纳入误差。','',
'## 仅报告的输入敏感性（不修改闸门，不据误差择优）','',
'| 设定 | 执行状态 | 主池候选数 | B（非闸门） | M（非闸门） | 并列池 B / M（仅描述） |','|---|---|---:|---:|---:|---|']
for tag,label in [('main','12h, 权重0.25'),('hours6','6h'),('hours18','18h'),('weight01','先验权重0.1'),('weight1','先验权重1'),('bdeck','b-deck RMW 第19栏')]:
 s=summary[tag]
 if s.get('stats'):
    a=s['stats']['primary'];b=s['stats']['parallel'];lines.append('| '+label+' | exit '+s['exit']+' | '+str(a['n'])+' | '+fmt(a['B'])+' | '+fmt(a['M'])+' | '+fmt(b['B'])+' / '+fmt(b['M'])+' |')
 else:lines.append('| '+label+' | exit '+str(s.get('exit'))+'（'+str(s.get('reason',''))[:80].replace('|','/')+'） | — | — | — | — |')
lines+=['','v2 冻结版并列读法：BEST 风圈逐节点至少两阈值，12/15 事件在 ±19h 输入内有不合格节点，因此 (a) 不判闸；不采纳 A1 时 HELENE 只有两站，仍不判闸。v3 是本次新输入分级假设，不能把 v2 的缺圈阻断或本次缺站阻断说成模型优劣。没有运行 (b)(c)，不放行。']
(P/'RESULTS_a_v3.md').write_text('\n'.join(lines)+'\n')
print('wrote',P/'RESULTS_a_v3.md')
