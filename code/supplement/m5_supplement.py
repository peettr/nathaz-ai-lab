#!/usr/bin/env python3
"""Post-hoc M5 secondary diagnostics; archived predictions/observations read-only.

Daily UTC verifying-day network-block bootstrap, 1000 draws. Event IDs are defined
on the complete native 10-minute observations, NOT the 6-hourly scoring subset.
"""
from pathlib import Path
import io, math, tarfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PRED = ROOT/'review_m5/score_stage/output/swiss_predictions_delay4.parquet'
OBS = ROOT/'pairs/train_complete_20261027.tgz'
FROZEN = ROOT/'review_m5/score_stage/output/swiss_scores_delay4.csv'
METHODS = ('R','T0','D1','D2','M','M+D1')
LEADS = (6,12,24,48)
KS = (.01,.05,.10)
DRAWS = 1000
SEED = 23050304


def event_map(pred):
    """Group threshold exceedance runs by station on full ten-minute record.

    Two exceeding ten-minute periods with timestamp gap <=40 minutes have at
    most 30 minutes of intervening non-exceedance; missing timestamps break
    only when the gap is >40 min (report this observational limitation).
    """
    if not OBS.exists():
        return None, {'observation_archive':'missing'}
    threshold = pred.groupby('site').threshold_p95.first()
    if not (pred.groupby('site').threshold_p95.nunique()==1).all():
        raise ValueError('site training threshold varies across leads')
    records = []
    audit = {}
    with tarfile.open(OBS, 'r:gz') as tf:
        names = set(tf.getnames())
        for site, th in threshold.items():
            name=f'obs/obs_{site}.csv'
            if name not in names:
                raise ValueError('missing native observation '+name)
            data=pd.read_csv(io.BytesIO(tf.extractfile(name).read()))
            data['time_utc']=pd.to_datetime(data.time_utc,utc=True)
            data=data.sort_values('time_utc')
            if data.time_utc.duplicated().any():raise ValueError('duplicated native timestamps '+site)
            times=data.time_utc
            if not ((times.diff().dropna()==pd.Timedelta(minutes=10)).all()):
                audit[site+'_missing_or_irregular_intervals']=int((times.diff().dropna()!=pd.Timedelta(minutes=10)).sum())
            eligible=data.loc[data.speed_ms>=th,['time_utc']].copy()
            starts=eligible.time_utc.diff().gt(pd.Timedelta(minutes=40)).fillna(True)
            if len(starts):starts.iloc[0]=True
            eligible['event_id']=[f'{site}:{int(i)}' for i in starts.cumsum().to_numpy()]
            eligible['site']=site
            records.append(eligible)
            audit[site+'_native_rows']=len(data)
            audit[site+'_native_events']=int(starts.sum())
    lookup=pd.concat(records,ignore_index=True)
    if lookup.duplicated(['site','time_utc']).any():raise ValueError('duplicate event lookup')
    audit['observation_archive']=str(OBS)
    return lookup,audit


def top_indices(scores,site,init,k):
    # Frozen scorer: score descending, site/init ascending, stable mergesort.
    return np.lexsort((init,site,-scores))[:max(1,math.ceil(len(scores)*k))]


def point_and_boot(frame, fhr):
    frame=frame.sort_values(['valid_end_utc','site','init_utc']).reset_index(drop=True)
    n=len(frame)
    obs=frame.obs.to_numpy()
    event=obs>=frame.threshold_p95.to_numpy()
    ids=frame.event_id.fillna('').to_numpy(dtype=str)
    if bool(np.any(event & (ids==''))) or bool(np.any(~event & (ids!=''))):
        raise ValueError('native event mapping mismatches scoring event flags')
    sites=frame.site.to_numpy(); inits=frame.init_utc.to_numpy()
    y={m:frame[m].to_numpy() for m in METHODS}
    day=frame.valid_end_utc.dt.floor('D')
    groups=[np.flatnonzero((day==d).to_numpy()) for d in day.unique()]
    rng=np.random.default_rng(SEED+fhr)
    indices=[np.arange(n)]
    for _ in range(DRAWS):
        indices.append(np.concatenate([groups[i] for i in rng.integers(len(groups),size=len(groups))]))
    records=[]
    for draw,idx in enumerate(indices):
        e=event[idx]; eid=ids[idx]
        denom=int(e.sum()); unique=np.unique(eid[e]); en=len(unique)
        if denom==0 or en==0:raise ValueError('empty scored event sample')
        site=sites[idx]; init=inits[idx]
        mae={m:float(np.abs(y[m][idx]-obs[idx]).mean()) for m in METHODS}
        metrics={f'MAE_{m}':v for m,v in mae.items()}
        for m in ('D1','D2'):
            metrics[f'{m}_vs_R_relative']=(mae[m]-mae['R'])/mae['R']
        for k in KS:
            count=max(1,math.ceil(len(idx)*k))
            metrics[f'random_row_top{int(100*k)}']=count/len(idx)
            # For an event of m scored positive rows among N, miss probability
            # is C(N-m,count)/C(N,count), evaluated as product for stability.
            sizes=pd.Series(eid[e]).value_counts().to_numpy()
            miss=np.array([np.prod(1-s/(len(idx)-np.arange(count))) if s<=len(idx)-count else 0 for s in sizes])
            metrics[f'random_event_top{int(100*k)}']=float(np.mean(1-miss))
        for m in METHODS:
            pred=y[m][idx]
            for k in KS:
                selected=top_indices(pred,site,init,k)
                captured=e[selected].sum()
                metrics[f'row_top{int(100*k)}_{m}']=float(captured/denom)
                metrics[f'event_top{int(100*k)}_{m}']=float(len(np.unique(eid[selected][e[selected]]))/en)
        for metric,value in metrics.items():
            records.append((draw,fhr,metric,value,n,len(groups),denom,en))
    raw=pd.DataFrame(records,columns=['draw','fhr','metric','value','n','days','event_rows','scored_events'])
    out=[]
    for metric,g in raw.groupby('metric',sort=True):
        p=g.loc[g.draw==0].iloc[0]; boot=g.loc[g.draw>0,'value'].to_numpy()
        out.append({'fhr':fhr,'metric':metric,'point':p.value,'lo':np.quantile(boot,.025),'hi':np.quantile(boot,.975),'n':n,'days':len(groups),'event_rows':int(p.event_rows),'scored_events':int(p.scored_events),'bootstrap_valid':len(boot)})
    return out


def main():
    pred=pd.read_parquet(PRED)
    assert set(pred.fhr)==set(LEADS)
    assert len(pred)==17432 and len(pred.site.unique())==12
    assert (pred.R==pred.raw).all()
    frozen=pd.read_csv(FROZEN)
    for fhr in LEADS:
        f=pred[pred.fhr==fhr].copy()
        assert len(f)==4358
        for m in METHODS:
            val=float(np.abs(f[m]-f.obs).mean())
            target=float(frozen[(frozen.fhr==fhr)&(frozen.metric=='MAE_'+m)].point.iloc[0])
            if abs(val-target)>1e-10:raise ValueError(f'frozen MAE mismatch {fhr} {m}')
        for k in KS:
            for m in METHODS:
                selected=f.sort_values([m,'site','init_utc'],ascending=[False,True,True],kind='mergesort').iloc[:math.ceil(len(f)*k)]
                ours=float((selected.obs>=selected.threshold_p95).sum()/(f.obs>=f.threshold_p95).sum())
                target=float(frozen[(frozen.fhr==fhr)&(frozen.metric==f'Top{int(k*100)}_{m}')].point.iloc[0])
                if abs(ours-target)>1e-10:raise ValueError(f'frozen Top-k mismatch {fhr} {m} {k}')
    lookup,audit=event_map(pred)
    if lookup is None:
        pred['event_id']=pd.NA
    else:
        pred=pred.merge(lookup,left_on=['site','valid_end_utc'],right_on=['site','time_utc'],how='left',validate='many_to_one').drop(columns='time_utc')
    # Only event scoring requires the native archive; relative and station results still available.
    station=pred.groupby(['site','fhr'],sort=True).apply(lambda g: pd.Series({'n':len(g),**{f'MAE_{m}':float(np.abs(g[m]-g.obs).mean()) for m in METHODS}}),include_groups=False).reset_index()
    station['D2_vs_R']=np.where(station.MAE_D2<station.MAE_R,'better',np.where(station.MAE_D2>station.MAE_R,'worse','tie'))
    station.to_csv(OUT/'station_mae.csv',index=False)
    if lookup is not None:
        results=[]
        for fhr in LEADS:
            results.extend(point_and_boot(pred[pred.fhr==fhr].copy(),fhr))
        metrics=pd.DataFrame(results)
        metrics.to_csv(OUT/'supplement_metrics.csv',index=False)
    else:
        raise ValueError('native observations missing: event metrics unavailable; use row-only fallback')
    import json, hashlib
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    def val(fhr,metric):
        a=metrics[(metrics.fhr==fhr)&(metrics.metric==metric)].iloc[0]
        return f'{a.point:.3f} [{a.lo:.3f}, {a.hi:.3f}]'
    lines=['# R23.2-03 M5 副指标补算（事后实现）','',
        '事后实现 10-27，主判不变。按原判据的读法：冻结 `m5_score.py` 的主判仅比较 D2 对 T0，瑞士四档 D(L) 的日块 95% 上界均小于零，满足至少一档通过；R 优于 T0，故该主判不能解释为 D2 对原始 R 的优势。以下是检验结果已见后的补充诊断，不把其区间充作预注册主判证据。', '',
        f'输入：`{PRED}`（sha256 {hashlib.sha256(PRED.read_bytes()).hexdigest()}）；完整原生 10 分钟观测：`{OBS}`（sha256 {hashlib.sha256(OBS.read_bytes()).hexdigest()}），归档中的 `obs/obs_<站>.csv`；未读新源，未重跑瑞士评分。脚本 `m5_supplement.py` sha256 `{sha}`。冻结评分器原有逐行 MAE、按条 Top-k 点值已逐档逐法复算，一致容差 1e-10。', '',
        '事件口径：各站训练期 P95；原生 10 分钟序列的超阈值行，相邻超阈时刻相差 ≤40 分钟（中间非超阈时段 ≤30 分钟）合为一事件。检验期每档 4,358 条评分行、91 个 UTC 检验日；事件分母仅为这些评分行中至少出现一条超阈行的原生事件（每档 151 个），不是检验期所有原生事件。仅有非超阈评分行的原生事件不进入分母。按条分母为评分行中的超阈条数。原生记录各站相邻时间均按 10 分钟核验，详见 audit.json。', '',
        '每档按 `valid_end_utc` 的 UTC 日整块、有放回重抽全部站同日评分行 1000 次，种子 `23050304+fhr`；同次抽样同步比较各方法，百分位 2.5/97.5。原生事件 ID 固定，跨日或重复抽中的同一原生事件不拆分、不重复计事件分母；重抽的评分行则按次数计入排序候选。排序同分按 site、init_utc 升序并保持稳定。区间是抽样波动描述，不覆盖跨季节/跨站迁移不确定性。', '',
        '## 相对原始 R 的 MAE 差', '',
        '定义 `(MAE_x−MAE_R)/MAE_R`；负值为在本次配对集合中 MAE 更小。', '',
        '| fhr h | D1 对 R [95%] | D2 对 R [95%] | D2 优于/差于 R 站数 |', '|---:|---:|---:|---:|']
    for fhr in LEADS:
        ss=station[station.fhr==fhr].D2_vs_R.value_counts()
        lines.append(f'| {fhr} | {val(fhr,"D1_vs_R_relative")} | {val(fhr,"D2_vs_R_relative")} | {ss.get("better",0)}/{ss.get("worse",0)} |')
    lines+=['', '## 强风 Top-k 捕获率：按条/按事件', '',
        '每格为点值 [95% 日块区间]。k% 按 `ceil(N*k)` 条选择；事件只要至少一条超阈评分行入选即捕获。六方法、四时效、三个 k 的完整逐格表在 supplement_metrics.csv。', '']
    for k in (1,5,10):
        lines += [f'### k={k}%', '', '| fhr | 方法 | 按条 | 按事件 |', '|---:|---|---:|---:|']
        for fhr in LEADS:
            for m in METHODS:
                lines.append(f'| {fhr} | {m} | {val(fhr,f"row_top{k}_{m}")} | {val(fhr,f"event_top{k}_{m}")} |')
        lines+=['']
    lines+=['## 随机排序期望', '',
        '按条：恰好选 `ceil(N*k)` 条的随机排序期望是 `ceil(N*k)/N`，因此分别约为 k%，不是按条超阈比例。按事件：对同一检验集合，每事件有 m_e 条超阈评分行，N 条评分行取 n=ceil(N*k)，随机捕获概率 `1−C(N−m_e,n)/C(N,n)`；对 151 个评分中出现的事件取均值。它是解析随机排序期望（无需模拟 1000 次），未把完整原生事件中的未评分行当候选。', '',
        '| fhr | 按条随机 1/5/10% | 按事件随机 1/5/10% |', '|---:|---:|---:|']
    for fhr in LEADS:
        row='/'.join(f'{float(metrics[(metrics.fhr==fhr)&(metrics.metric==f"random_row_top{k}")].point.iloc[0]):.3f}' for k in (1,5,10))
        evt='/'.join(f'{float(metrics[(metrics.fhr==fhr)&(metrics.metric==f"random_event_top{k}")].point.iloc[0]):.3f}' for k in (1,5,10))
        lines.append(f'| {fhr} | {row} | {evt} |')
    lines+=['', '## 分站 MAE', '',
        '12 站 × 4 档 × 六方法的逐格原值见 station_mae.csv（单位 m/s），每站每档以相同配对行比较；站数未据 12 站做独立同分布推断。', '',
        '## delay6 与限制', '',
        'M5 的 init 与 fhr 固定，延迟只改 issue 标签，delay6 预测与 delay4 逐值相同（Lead 已核 np.allclose=True），该敏感性按构造无信息量；fhr=6 在 delay6 下提前量为 0。',
        '事件数取决于本站 P95、原生 10 分钟观测及评分行能否命中事件；按条与按事件不是同一个分母。原生连续序列若有缺测，不能凭缺测间隔认定事件连续；本次归档逐站时间步长无缺口。全体 12 站的 P95 是训练期本站值，事件阈值不用于拟合。日块区间不证明模型因果改进；R 优于 T0 的现象必须与冻结 T0 主判并列，不以 T0 作唯一原始基线。', '']
    (OUT/'supplement.md').write_text('\n'.join(lines),encoding='utf-8')
    print('DONE',len(station),len(results),audit)

if __name__=='__main__':main()
