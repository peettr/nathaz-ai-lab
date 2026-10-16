#!/usr/bin/env python3
"""F: frozen cost/loss replay of A1 station-paired forecasts, train 2022/test 2023."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
INPUT=ROOT.parent/'a1_lowalt_wind/asos_2022train_2023test_20261014'
SOURCES=['GRAP_v100_GFS','PANG_v100_GFS','FOUR_v200_GFS','GFS']
KEY=['station','init_utc','valid_utc','lead_h']
RATIOS=np.round(np.arange(1,100)/100,2)
METHODS=['P_multi','P_stack']+[f'P_{s}' for s in SOURCES]+['GFS_raw','GFS_corrected','GraphCast_corrected','persistence']
DETERMINISTIC=['GFS_raw','GFS_corrected','GraphCast_corrected']
SEED=20261014

def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
    if isinstance(v,(np.bool_,bool)):return bool(v)
    if isinstance(v,(np.integer,int)):return int(v)
    if isinstance(v,(np.floating,float)):return float(v) if np.isfinite(v) else None
    return v

def read(year):
    d=pd.read_csv(INPUT/f"paired_station_{'train' if year==2022 else 'test'}.csv.gz")
    d=d[d.lead_h.isin([24,48])].copy()
    for c in ['init_utc','valid_utc']: d[c]=pd.to_datetime(d[c],utc=True)
    assert not d.duplicated(KEY+['source']).any()
    # Initial-time gust persistence: only observed gust in A1 at this time, never future observations.
    g=d[d.source=='GFS'][['station','valid_utc','minute_gust']].drop_duplicates(['station','valid_utc'])
    g=g.rename(columns={'valid_utc':'init_utc','minute_gust':'gust_persistence'})
    d=d.merge(g,on=['station','init_utc'],how='left',validate='many_to_one')
    assert d.valid_utc.dt.year.eq(year).all()
    return d

def assemble(d,typ,threshold,lead,stack=None):
    q=d[d.lead_h.eq(lead)].copy();obs='metar_speed' if typ=='wind' else 'minute_gust'
    pc=f'prob_{typ}_{threshold}'
    columns=[pc,'raw_speed','corrected','pred_gust','metar_speed','minute_gust','persistence','gust_persistence']
    piv=q.pivot(index=KEY,columns='source',values=columns)
    a=pd.DataFrame(index=piv.index)
    a['obs']=piv[(obs,'GFS')]
    for src in SOURCES:
        if not np.allclose(piv[(obs,src)].fillna(-999),a.obs.fillna(-999)):
            raise ValueError('Observation disagreement across sources')
        a[f'P_{src}']=piv[(pc,src)]
    probcols=[f'P_{s}' for s in SOURCES]
    a['P_multi']=a[probcols].mean(axis=1,skipna=False)
    if stack is not None:
        valid=a[probcols].notna().all(axis=1)
        a['P_stack']=np.nan
        if valid.any():a.loc[valid,'P_stack']=stack.predict_proba(a.loc[valid,probcols])[:,1]
    a['GFS_raw']=piv[('raw_speed','GFS')]
    col='corrected' if typ=='wind' else 'pred_gust'
    a['GFS_corrected']=piv[(col,'GFS')]
    a['GraphCast_corrected']=piv[(col,'GRAP_v100_GFS')]
    a['persistence']=piv[('persistence' if typ=='wind' else 'gust_persistence','GFS')]
    # Gust GFS_raw compares raw 10m sustained speed to the gust threshold: proxy only.
    a=a.reset_index();a['day']=a.valid_utc.dt.floor('D')
    return a

def day_version(a):
    # Complete 00/12 UTC verifying day per station; keep two records and max probability/value.
    n=a.groupby(['station','day']).agg(n=('valid_utc','nunique'))
    good=n.index[n.n.eq(2)]
    a=a.set_index(['station','day']).loc[good].reset_index()
    agg={m:'max' for m in METHODS};agg['obs']='max'
    return a.groupby(['station','day'],as_index=False).agg(agg)

def compute(a,threshold,counts):
    # C=alpha, L=1; loss=alpha for action, 1 for event without action.
    o=(a.obs.to_numpy(dtype=float)>=threshold).astype(float)
    day,inv=np.unique(a.day.to_numpy(),return_inverse=True);D=len(day);R=len(RATIOS)
    if counts is None:
        rng=np.random.default_rng(SEED+threshold+len(a)+D)
        counts=rng.multinomial(D,np.ones(D)/D,size=1000)
    assert counts.shape==(1000,D)
    ones=np.bincount(inv,minlength=D)
    events=np.bincount(inv,weights=o,minlength=D)
    total=ones.sum();ev=events.sum();base_rate=ev/total
    ct=counts@ones;et=counts@events
    clim=np.minimum(RATIOS[None,:],(et/ct)[:,None])
    perfect=RATIOS[None,:]*(et/ct)[:,None]
    denom=clim-perfect
    pointden=np.minimum(RATIOS,base_rate)-RATIOS*base_rate
    if not np.all(denom>0):
        # Resamples without both classes cannot define V; retain null in corresponding CI.
        pass
    records={};sim={}
    for method in METHODS:
        x=a[method].to_numpy(dtype=float)
        assert np.isfinite(x).all(),method
        act=(x[:,None]>=RATIOS[None,:]) if method.startswith('P_') else np.broadcast_to((x>=threshold)[:,None],(len(x),R))
        cday=np.zeros((D,R));mday=np.zeros((D,R))
        np.add.at(cday,inv,act.astype(float))
        np.add.at(mday,inv,((~act)&(o[:,None]>0)).astype(float))
        expense=(RATIOS*(cday.sum(axis=0)/total)+mday.sum(axis=0)/total)
        point=(np.minimum(RATIOS,base_rate)-expense)/pointden
        ec=(counts@cday)/ct[:,None];em=(counts@mday)/ct[:,None]
        vv=np.divide(clim-RATIOS[None,:]*ec-em,denom,out=np.full_like(ec,np.nan),where=denom>0)
        sim[method]=vv
        records[method]={'V':point.tolist(),'ci95':np.nanquantile(vv,[.025,.975],axis=0).T.tolist(),
                         'mean_V_0.05_0.50':float(point[(RATIOS>=.05)&(RATIOS<=.5)].mean()),
                         'actions_at_C_over_L_0.10':int(cday[:,9].sum())}
    band=(RATIOS>=.05)&(RATIOS<=.5)
    pm=sim['P_multi'][:,band].mean(axis=1)
    best=np.stack([sim[m][:,band].mean(axis=1) for m in DETERMINISTIC],axis=1).max(axis=1)
    delta=pm-best
    bestpoint=max(records[m]['mean_V_0.05_0.50'] for m in DETERMINISTIC)
    gd=pm-sim['P_GFS'][:,band].mean(axis=1)
    guard_point=np.asarray(records['P_multi']['V'])-np.asarray(records['P_GFS']['V'])
    best_name=max(DETERMINISTIC,key=lambda m:records[m]['mean_V_0.05_0.50'])
    gate={'best_deterministic':best_name,'best_deterministic_mean_V':bestpoint,
          'multi_minus_best_mean_V':records['P_multi']['mean_V_0.05_0.50']-bestpoint,
          'multi_minus_best_ci95':np.nanquantile(delta,[.025,.975]).tolist(),
          'primary_pass':bool(records['P_multi']['mean_V_0.05_0.50']-bestpoint>=.05 and np.nanquantile(delta,.025)>0),
          'multi_minus_GFS_probability_mean_V':float(guard_point[band].mean()),
          'multi_minus_GFS_probability_ci95':np.nanquantile(gd,[.025,.975]).tolist(),
          'multi_minus_GFS_probability_min_pointwise':float(guard_point[band].min()),
          'guard_mean_pass':bool(guard_point[band].mean()>=-.02),
          'guard_pointwise_pass':bool(np.all(guard_point[band]>=-.02))}
    return {'cases':int(total),'events':int(ev),'event_rate':float(base_rate),'days':int(D),'methods':records,'gate':gate}

def draw(results,typ,lead,scale):
    fig,axes=plt.subplots(1,3,figsize=(16,4.6),sharex=True,sharey=True)
    for ax,t in zip(axes,[8,10,12] if typ=='wind' else [10,13,15]):
        r=results[f'{typ}_{t}_{lead}h_{scale}']
        for m in METHODS:
            y=r['methods'][m]['V'];ax.plot(RATIOS,y,label=m,linewidth=2 if m=='P_multi' else 1,alpha=1 if m=='P_multi' else .7)
        ax.axhline(0,color='gray',linewidth=.7);ax.set(title=f'{t} m/s: {r["events"]}/{r["cases"]} events',xlabel='C/L',xlim=(0,1))
        ax.axvspan(.05,.5,alpha=.06,color='orange');ax.grid(alpha=.15)
    axes[0].set_ylabel('Relative economic value V')
    axes[-1].legend(fontsize=6,bbox_to_anchor=(1.02,1),loc='upper left')
    fig.text(.02,.015,'Data: ASOS/IEM observations; GraphCast/Pangu/FourCastNet v2 via AWS AIWP; NOAA GFS AWS. 2022 calibration, 2023 verification.',fontsize=8)
    fig.tight_layout(rect=(0,.04,.82,1));out=ROOT/f'value_curves_{typ}_{lead}h_{scale}.png';fig.savefig(out,dpi=140);plt.close(fig)
    return out.name

def main():
    for fname in ['results.md','metrics.json']+[f'value_curves_{typ}_{lead}h_{scale}.png' for typ in ('wind','gust') for lead in (24,48) for scale in ('instant','daily')]:
        if (ROOT/fname).exists():raise FileExistsError(f'Refusing to overwrite {fname}')
    tr=read(2022);te=read(2023)
    fitted={};models={};traininfo={}
    for typ in ['wind','gust']:
        for t in ([8,10,12] if typ=='wind' else [10,13,15]):
            for lead in (24,48):
                a=assemble(tr,typ,t,lead);cols=[f'P_{s}' for s in SOURCES]
                a=a.dropna(subset=['obs']+cols)
                y=(a.obs>=t).astype(int)
                if y.sum()>=30 and (len(y)-y.sum())>=30:
                    mdl=LogisticRegression(C=1.,max_iter=1000,random_state=SEED)
                    mdl.fit(a[cols],y);models[typ,t,lead]=mdl
                    fitted[typ,t,lead]={'cases':len(y),'events':int(y.sum()),'coefficients':mdl.coef_[0].tolist(),'intercept':float(mdl.intercept_[0])}
                else:fitted[typ,t,lead]={'cases':len(y),'events':int(y.sum()),'omitted':'<30 events or non-events'}
                traininfo[typ,t,lead]=fitted[typ,t,lead]
    results={};plots=[]
    for typ in ['wind','gust']:
        for lead in (24,48):
            for t in ([8,10,12] if typ=='wind' else [10,13,15]):
                mdl=models.get((typ,t,lead))
                a=assemble(te,typ,t,lead,mdl)
                if mdl is None:a['P_stack']=a.P_multi # flagged omitted; no eligible fit
                a=a.dropna(subset=['obs']+METHODS).copy()
                for scale,b in [('instant',a),('daily',day_version(a))]:
                    key=f'{typ}_{t}_{lead}h_{scale}'
                    results[key]=compute(b,t,None)
                    results[key]['stack_training']=traininfo[typ,t,lead]
                    if mdl is None:results[key]['methods']['P_stack']['not_fitted']=True
            for scale in ('instant','daily'):plots.append(draw(results,typ,lead,scale))
    payload={'input_files':[str(INPUT/f'paired_station_{x}.csv.gz') for x in ('train','test')],
             'definitions':{'ratios':RATIOS.tolist(),'bootstrap':'1000 verifying-UTC-day grouped resamples, all stations/records together, seed 20261014 + threshold + n + n_days; percentile CI; case-specific complete-case pairing',
                            'V':'(min(C/L,o)-E_forecast)/(min(C/L,o)-(C/L)*o); L=1; expense=(C/L)*action + event*no_action',
                            'daily':'per station UTC verifying day, require both 00/12 UTC valid times; event and decision by maximum of two records',
                            'gust_raw':'GFS raw sustained speed compared to gust threshold: proxy, not gust forecast',
                            'cost_loss_band':'assumption 0.05..0.50; not measured operating costs'},'results':results,'plots':plots}
    (ROOT/'metrics.json').write_text(json.dumps(clean(payload),ensure_ascii=False,indent=2,allow_nan=False))
    main=results['wind_10_24h_instant'];g=main['gate']
    status='通过' if g['primary_pass'] else '未通过'
    lines=[f'一句结论：OKC 2023 配对回放，持续风 10 m/s／24 h 的多源概率经济价值主判{status}；这只是 ASOS 候选阈值的决策回放，不是吊装停工效益的实测证明。','',
      '# F：超越概率预警成本—损失回放','',
      '2022 训练／2023 测试的 A1 原始配对表，只在 工作站 CPU 重放决策，不重算预报。每一阈值/时效/尺度各使用所有方法都可用的同一批观测和预报；2023 未调概率阈值。',
      'P_multi 为四源（GraphCast、Pangu、FourCastNet v2、GFS）概率等权平均；四源均 GFS 初始化，共同误差相关，替代集合并非真正独立集合。P_stack 是仅 2022 数据拟合的四概率 logistic 叠加；2022 阳性/阴性少于 30 的档位不拟合，metrics.json 标记。各单源概率另列。',
      '静态 C/L：C 为停工防护成本、L 为未停工且事件发生的损失，损失单位化为 1；E_clim=min(C/L, 2023 同批样本事件频率)，E_perfect=(C/L)×事件频率，V=(E_clim−E_forecast)/(E_clim−E_perfect)。2023 气候频率只用于评分归一化而非训练决策；V 可为负数。对概率用 p≥C/L，确定性用预报量≥候选阈值，持续性为初始化观测≥阈值。全曲线 C/L=0.01..0.99 每隔 0.01；[0.05,0.50] 是冻结判据的假设区间，并非实测施工成本。',
      '', '## 主表：2023 年每站—验证时次，V 为假设 C/L 0.05–0.50 等权网格均值','',
      '|事件|提前量|配对数／事件数／验证日|P_multi|P_stack|GFS 概率|最佳确定性及其 V|持续性 V|多源−最佳确定性 (95% CI)|多源−GFS 概率|','|---|---:|---:|---:|---:|---:|---|---:|---|---:|']
    for typ in ('wind','gust'):
        for t in ([8,10,12] if typ=='wind' else [10,13,15]):
            for lead in (24,48):
                r=results[f'{typ}_{t}_{lead}h_instant'];gg=r['gate'];m=r['methods'];fmt=lambda x:f'{x:.3f}'
                lines.append(f'|{typ}≥{t} m/s|{lead} h|{r["cases"]}/{r["events"]}/{r["days"]}|{fmt(m["P_multi"]["mean_V_0.05_0.50"])}|{fmt(m["P_stack"]["mean_V_0.05_0.50"]) if "omitted" not in r["stack_training"] else "未拟合"}|{fmt(m["P_GFS"]["mean_V_0.05_0.50"])}|{gg["best_deterministic"]} {fmt(gg["best_deterministic_mean_V"])}|{fmt(m["persistence"]["mean_V_0.05_0.50"])}|{fmt(gg["multi_minus_best_mean_V"])} [{fmt(gg["multi_minus_best_ci95"][0])}, {fmt(gg["multi_minus_best_ci95"][1])}]|{fmt(gg["multi_minus_GFS_probability_mean_V"])}|')
    lines+=['','## 冻结判据（仅持续风 10 m/s，24 h，每站—时次）','',
      f'主判：多源平均 V−最佳确定性 {g["best_deterministic"]} = {g["multi_minus_best_mean_V"]:.4f}，按验证日整组 bootstrap 1000 次、95% CI [{g["multi_minus_best_ci95"][0]:.4f}, {g["multi_minus_best_ci95"][1]:.4f}]；须点估计≥0.05 且区间不跨 0：{status}。最佳确定性指在 2023 上取三项均值最大，bootstrap 每次重新取最大，不能理解为提前锁定的最优方案。',
      f'护栏：多源−GFS 单源概率，区间均值差 {g["multi_minus_GFS_probability_mean_V"]:.4f}，95% CI [{g["multi_minus_GFS_probability_ci95"][0]:.4f}, {g["multi_minus_GFS_probability_ci95"][1]:.4f}]；平均差不低于 −0.02：{"通过" if g["guard_mean_pass"] else "未通过"}；逐 C/L 点最小差 {g["multi_minus_GFS_probability_min_pointwise"]:.4f}，逐点口径 {"通过" if g["guard_pointwise_pass"] else "未通过"}。护栏单独报告，不作主判。',
      f'阵风 13 m/s 只报告：24 h {results["gust_13_24h_instant"]["cases"]} 配对、{results["gust_13_24h_instant"]["events"]} 事件（GOK/OKC/PWA）；不进入主判。',
      '', '## 假设：日尺度敏感性','',
      '每日每站要求 00/12 UTC 两个验证时刻齐全，事件是任一时刻超阈值；概率预警取当日两时刻最大概率，确定性与持续性取最大风速后判定。该日定义与作业窗口均是假设，非文献规定；每个验证 UTC 日整组重抽，站点／时次不当独立 bootstrap 单元。',
      '|事件|提前量|站日数／事件站日|P_multi 平均 V|最佳确定性平均 V|多源−最佳 (95% CI)|', '|---|---:|---:|---:|---:|---|']
    for typ in ('wind','gust'):
        for t in ([8,10,12] if typ=='wind' else [10,13,15]):
            for lead in (24,48):
                r=results[f'{typ}_{t}_{lead}h_daily'];gg=r['gate']
                lines.append(f'|{typ}≥{t}|{lead} h|{r["cases"]}/{r["events"]}|{r["methods"]["P_multi"]["mean_V_0.05_0.50"]:.3f}|{gg["best_deterministic_mean_V"]:.3f}|{gg["multi_minus_best_mean_V"]:.3f} [{gg["multi_minus_best_ci95"][0]:.3f}, {gg["multi_minus_best_ci95"][1]:.3f}]|')
    lines+=['','## 图与局限','',
      '图：'+', '.join(plots)+'。全 99 点、所有方案的 V 和逐点 bootstrap 95% 区间在 metrics.json。',
      '持续风实测为 ASOS METAR 2 min，阵风为 3 站 IEM 1 min 数据所构造的验证时刻中心 1 h 最大阵风；持续性阵风使用初始化时刻可得的同站阵风，若缺则排除配对。GFS raw 对阵风没有相应产品，本回放用 raw_speed（持续风）与阵风阈值比较，仅作粗糙代理；订正的 GFS 与 GraphCast 阵风用 A1 的 pred_gust。',
      '验证时刻只在 00/12 UTC（当地早晚），未验证作业时段中午、全天连续超限、提前停工是否可操作。ASOS 测高未逐站核实；站点地面风不等于吊臂顶风，阈值是候选档而非已核实的具体吊机作业阈值。成本/损失区间与每日两时次取最大均是假设；需要实际停工与损失调查才可转为货币效益。',
      'A1 2022 仅各月前 15 天约 00/12 UTC 训练，概率经单站/时效回归；极端阈值训练和 2023 事件稀少。无空间外推/业务更新验证；同源 GFS 初值与后处理相关，不能视四个独立成员。',
      '', '来源：A1 run_verify_revised.py 与同目录 paired_station_{train,test}.csv.gz；NOAA NCEI ASOS 经 IEM，NOAA/CIRA GraphCast/Pangu/FourCastNet v2 via AWS AIWP，NOAA GFS AWS。方法：Richardson (2000), QJRMS 126(563), 649–667, https://doi.org/10.1002/qj.49712656313；REV 公式核对 https://scores.readthedocs.io/en/stable/tutorials/Relative_Economic_Value_Score.html 。']
    (ROOT/'results.md').write_text('\n'.join(lines)+'\n')
    print('DONE',status,'MAIN',json.dumps(clean(g),ensure_ascii=False),'PLOTS',len(plots))

if __name__=='__main__':main()
