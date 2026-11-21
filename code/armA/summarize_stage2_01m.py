"""Postprocess L26.22-01m point files; read-only analysis, no simulation."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent/'run_01m/stage2'
TM,TV=35840,74240
rows=[]
for i in range(5):
    f=ROOT/f'point_{i}.jsonl'
    if not f.exists(): raise SystemExit(f'missing {f}')
    entries=[json.loads(s) for s in f.read_text().splitlines() if s.strip()]
    if not any(r.get('type')=='complete' for r in entries): raise SystemExit(f'incomplete {f}')
    rows += [r for r in entries if r.get('type')=='result']
seen={(r['point'],r['dtype'],r['metric'],r['T'],r['fd_step_fraction']) for r in rows}
if len(seen)!=len(rows) or len(rows)!=5*2*2*4+2*2*2*4: raise SystemExit(f'duplicate/missing rows: {len(rows)} {len(seen)}')
lines=['# L26.22-01m BGK 五点梯度汇总','', '数据源：run_01m/stage2/point_0..4.jsonl；源自 CRC A10 BGK/Re_H=1000 起转终态 1755011。', '', '|目标|窗 T|FD 1% FP64 AD合格点|FD 0.5% FP64 AD合格点(2点)|FP32/FP64 AD 有限点|FP64 范数 log(T) 对数线性 R²|', '|---|---:|---:|---:|---:|---:|']
for kind,Tfull in [('mean',TM),('var',TV)]:
    for T in [Tfull//8,Tfull//4,Tfull//2,Tfull]:
        group=[r for r in rows if r['metric']==kind and r['T']==T]
        f64=[r for r in group if r['dtype']=='float64' and r['fd_step_fraction']==.01]
        half=[r for r in group if r['dtype']=='float64' and r['fd_step_fraction']==.005]
        good=lambda r:r['finite'] and isinstance(r['cos'],(int,float)) and r['cos']>=.95 and r['relative_difference']<=.10
        finite=sum(r['finite'] for r in group if r['fd_step_fraction']==.01)
        xs=np.log([Tfull//8,Tfull//4,Tfull//2,Tfull]); yy=[]
        for t in [Tfull//8,Tfull//4,Tfull//2,Tfull]:
            q=[r for r in rows if r['point']==0 and r['dtype']=='float64' and r['metric']==kind and r['T']==t and r['fd_step_fraction']==.01][0]
            yy.append(np.log(q['ad_norm']) if isinstance(q['ad_norm'],(int,float)) and q['ad_norm']>0 else np.nan)
        if np.isfinite(yy).all():
            fit=np.polyval(np.polyfit(xs,yy,1),xs); r2=1-float(np.sum((yy-fit)**2))/float(np.sum((yy-np.mean(yy))**2)) if np.ptp(yy)>0 else float('nan')
        else:r2=float('nan')
        lines.append(f'|{kind}|{T}|{sum(map(good,f64))}/5|{sum(map(good,half))}/2|{finite}/10|{r2:.6g}|')
lines += ['', '原方案的“梯度准”须在可靠 FD 点中至少 4/5；0.5% 与 1% FD 相对差超 0.05 的点应从分母剔除，且超过 2/5 不判。下表未代替该剔除核对。']
for kind,T in [('mean',TM),('var',TV)]:
    for i in range(2):
        a=[r for r in rows if r['point']==i and r['metric']==kind and r['T']==T and r['dtype']=='float64']
        one=next(r for r in a if r['fd_step_fraction']==.01); half=next(r for r in a if r['fd_step_fraction']==.005)
        f=np.asarray(one['fd']); h=np.asarray(half['fd']); d=float(np.linalg.norm(f-h)/np.linalg.norm(f)) if np.linalg.norm(f) else float('nan')
        lines.append(f'- {kind} 点{i} 全窗 FD 0.5%/1% 相对差 {d:.8g}')
lines += ['', '分段平均梯度及截断偏差：仅在方案 §2.1 条件触发时报告；原始文件还含单点短窗与全窗 FD 对照描述量，不把短前缀冒充各段平均。']
print('\n'.join(lines))
