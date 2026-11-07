#!/usr/bin/env python3
"""H5 event-held-out peak calibration; read-only source predictions."""
import csv, gzip, json, math
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
EXCLUDE = {'BQX','GVW','T89','BSM','F12','5R3'}
H3_OK = {'ne_20190128_wide','ne_20210114_wide','ks_20221202','tx_20191126'}
H4_OK = {'2024-05-28','2024-06-01','2025-06-09','2025-07-09'}
METHODS = ('raw','additive','linear','quantile')

def read_rows(path):
    op = gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',newline='') as f:
        yield from csv.DictReader(f)

def number(row,key):
    try:
        x=float(row[key]); return x if math.isfinite(x) else None
    except (ValueError,TypeError,KeyError): return None

def collect():
    data=[]; by=defaultdict(list)
    for r in read_rows(BASE/'predictions_r1_clean.csv.gz'):
        if r['station'] in EXCLUDE: continue
        by[(r['station'],r['date'])].append(r)
    for (station,day), rows in by.items():
        rows=[r for r in rows if all(number(r,k) is not None for k in ('obs','ok','era_resok','near_km'))]
        if not rows: continue
        near=float(np.median([float(r['near_km']) for r in rows]))
        # Model peak is its own maximum over exactly these observed hours.
        pred={'recommended':max(float(r['ok'] if near<50 else r['era_resok']) for r in rows),
              'ok75':max(float(r['ok']) for r in rows)}
        data.append(dict(category='fair',variable='sustained',event=day,station=station,
                         obs=max(float(r['obs']) for r in rows),pred=pred,near_km=near))
    for path in (BASE/'h2/peaks_clean_h2d.csv',BASE/'h2/peaks_francine_h2f.csv'):
        for r in read_rows(path):
            if r['pool']!='land': continue
            for var,obs,rec,ok in [('sustained','obs','holland_resok75','ok75'),
                                   ('gust','obs_gust','gust_holland_resok75','gust_ok75')]:
                y=number(r,obs); p=number(r,rec); q=number(r,ok)
                if None in (y,p,q): continue
                data.append(dict(category='hurricane',variable=var,event=r['event'],station=r['station'],obs=y,
                                 pred={'recommended':p,'ok75':q,'okfit':number(r,'okfit' if var=='sustained' else 'gust_okfit')}))
    for r in read_rows(BASE/'h3/peaks_h3.csv'):
        if r['event'] not in H3_OK: continue
        for var,obs,rec,ok in [('sustained','obs','okfit','ok75'),('gust','obs_gust','gust_okfit','gust_ok75')]:
            y=number(r,obs); p=number(r,rec); q=number(r,ok)
            if None in (y,p,q): continue
            data.append(dict(category='extratropical',variable=var,event=r['event'],station=r['station'],obs=y,
                             pred={'recommended':p,'ok75':q}))
    for r in read_rows(BASE/'h4/peaks_h4v3.csv'):
        if r['event'] not in H4_OK: continue
        for var,obs,rec,ok in [('sustained','obs','idw','ok75'),('gust','gust','gust_ok75','gust_ok75')]:
            y=number(r,obs); p=number(r,rec); q=number(r,ok)
            if None in (y,p,q): continue
            data.append(dict(category='thunderstorm',variable=var,event=r['event'],station=r['station'],obs=y,
                             pred={'recommended':p,'ok75':q}))
    return data

def quantile(train, rate=.8):
    arr=np.sort(np.abs(np.asarray(train,dtype=float)))
    return float(arr[min(len(arr)-1, math.ceil(rate*(len(arr)+1))-1)])

def fit(x,y,method):
    x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
    if method=='raw': return {'kind':'raw'}
    if method=='additive': return {'kind':'additive','offset':float(np.mean(y-x))}
    if method=='linear':
        slope=float(np.sum((x-x.mean())*(y-y.mean()))/np.sum((x-x.mean())**2)) if np.var(x)>1e-12 else 0.
        return {'kind':'linear','intercept':float(y.mean()-slope*x.mean()),'slope':slope}
    # Equal-spaced empirical quantiles of sorted arrays; np.interp averages neither tied predictions nor duplicates.
    # Collapse tied x to mid-rank mapped value for monotonic, deterministic interpolation.
    sx=np.sort(x); sy=np.sort(y)
    ux,inv,cnt=np.unique(sx,return_inverse=True,return_counts=True)
    start=np.cumsum(cnt)-cnt
    uy=np.array([np.mean(sy[s:s+n]) for s,n in zip(start,cnt)])
    return {'kind':'quantile','x':ux.tolist(),'y':uy.tolist()}

def apply(x,param):
    x=np.asarray(x,dtype=float); kind=param['kind']
    if kind=='raw': z=x
    elif kind=='additive': z=x+param['offset']
    elif kind=='linear': z=param['intercept']+param['slope']*x
    else: z=np.interp(x,param['x'],param['y'])
    return np.maximum(0,z)

def score(records):
    p=np.array([r['prediction'] for r in records]); y=np.array([r['observation'] for r in records]);
    return dict(n=len(records),bias=float(np.mean(p-y)),rmse=float(np.sqrt(np.mean((p-y)**2))),
                coverage80=float(np.mean([r['lower']<=r['observation']<=r['upper'] for r in records])),
                mean_width80=float(np.mean([r['upper']-r['lower'] for r in records])))

def verdict(before,after):
    b=abs(before['bias']); a=abs(after['bias']); ratio=after['rmse']/before['rmse']
    if a<=.5 and ratio<=1.02: return '校正有效'
    if ratio>1.10: return '无效'
    if (b>1e-12 and a<=b/2) or 1.02<ratio<=1.10: return '部分有效'
    return '无效'

def validate(data,cross=False):
    result={}; predictions=[]
    strata=sorted(set((r['category'],r['variable']) for r in data))
    for category,var in strata:
        subset=[r for r in data if r['category']==category and r['variable']==var]
        # Only sustained has all three other category training pools.
        if cross and var!='sustained': continue
        folds=[category] if cross else sorted(set(r['event'] for r in subset))
        result[f'{category}/{var}']={}
        for feature in sorted(set(k for r in subset for k in r['pred'])):
            if cross and feature not in ('recommended','ok75'): continue
            usable=[r for r in subset if r['pred'].get(feature) is not None]
            fold_metrics={}; allout=defaultdict(list)
            for event in folds:
                test=[r for r in usable if cross or r['event']==event]
                if cross:
                    training=[r for r in data if r['category']!=category and r['variable']==var and r['pred'].get(feature) is not None]
                else:
                    training=[r for r in usable if r['event']!=event]
                if not training or not test: continue
                tx=[r['pred'][feature] for r in training]; ty=[r['obs'] for r in training]
                vx=[r['pred'][feature] for r in test]; vy=[r['obs'] for r in test]
                fold_metrics[event]={'train_n':len(tx),'test_n':len(vx),'calibrations':{}}
                for method in METHODS:
                    param=fit(tx,ty,method)
                    residual=np.array(ty)-apply(tx,param)
                    radius=quantile(residual)
                    corrected=apply(vx,param)
                    out=[dict(category=category,variable=var,feature=feature,method=method,
                              event=r['event'],station=r['station'],observation=float(y),prediction=float(p),
                              lower=float(max(0,p-radius)),upper=float(p+radius)) for r,y,p in zip(test,vy,corrected)]
                    predictions.extend(out); allout[method].extend(out)
                    fold_metrics[event]['calibrations'][method]={'metrics':score(out),'radius80':radius,'parameters':param}
            if not fold_metrics: continue
            combined={m:score(allout[m]) for m in METHODS}
            base=combined['raw']
            for method in METHODS[1:]: combined[method]['verdict']=verdict(base,combined[method]); combined[method]['rmse_change_pct']=100*(combined[method]['rmse']/base['rmse']-1)
            result[f'{category}/{var}'][feature]={'folds':fold_metrics,'combined':combined}
    return result,predictions

def table(result):
    lines=['|类别/变量/基础方法|样本|原始偏差/RMSE|校正|LOEO 偏差/RMSE|RMSE变动|80%覆盖|判定|','|---|---:|---:|---|---:|---:|---:|---|']
    for key,features in result.items():
        for feature,entry in features.items():
            c=entry['combined']; raw=c['raw']
            for m in METHODS[1:]:
                s=c[m]; lines.append(f'|{key}/{feature}|{s["n"]}|{raw["bias"]:+.3f}/{raw["rmse"]:.3f}|{m}|{s["bias"]:+.3f}/{s["rmse"]:.3f}|{s["rmse_change_pct"]:+.1f}%|{s["coverage80"]:.1%}|{s["verdict"]}|')
    return '\n'.join(lines)

def report(result,cross,data):
    text=['# H5 按事件留一的峰值低估校正（UTC）','',
      '主检验使用既有站点留一预测，绝不把当前站/事件的峰值用于校正拟合。事件折内训练池按站事件等权；评分按留出站事件合并，因此覆盖率不等于事件等权。良态按日留一。主判定只针对推荐方法；其余为 OK 固定版统一对照（飓风另示 OKfit）。预登记见 `prereg_h5.md`。',
      '', '## 类内留一：各法合并指标（m/s）',table(result),'',
      '注意：阵风与持续风分开。原始方法和每个校正法的 80% 区间宽度及各折训练参数见 `metrics_h5.json`；区间用训练事件的已拟合残差计算，偏乐观，不是事件独立的严格保覆盖承诺。',
      '', '## 推荐方法每折（原始→加性/线性/分位数；偏差、RMSE、覆盖率）']
    for key,features in result.items():
        if 'recommended' not in features: continue
        lines=['|留出事件|n|原始|加性|线性|分位数|','|---|---:|---|---|---|---|']
        for event, fold in features['recommended']['folds'].items():
            c=fold['calibrations']; vals=[]
            for m in METHODS:
                x=c[m]['metrics']; vals.append(f'{x["bias"]:+.2f}/{x["rmse"]:.2f}/{x["coverage80"]:.0%}')
            lines.append(f'|{event}|{fold["test_n"]}|'+ '|'.join(vals)+'|')
        text.extend(['',f'### {key}',*lines])
    text.extend(['','## 跨类外推（其余三类持续风训练）',table(cross),
       '', '阵风：良态缺阵风、仅两类另有阵风数据，无法按其余三类阵风训练，跨类外推不可评；没有借用持续风参数。跨类结果为基础方法/测量时间定义混合的一套参数，仅是压力测试。',
       '', '## 样本及参数来源表',
       '|项目|来源与限定|','|---|---|',
       '|良态|`predictions_r1_clean.csv.gz`；删除 BQX/GVW/T89/BSM/F12/5R3 后，每站每天共同有效小时分别取观测和模型峰值。站距用当天有效小时 `near_km` 中位数，<50 km OK，其他 ERA5+残差 OK；是本次协议落实假设，并非 r2c 稀疏重抽预测。|',
       '|飓风|`h2/peaks_clean_h2d.csv` + `h2/peaks_francine_h2f.csv` 陆地池；Beryl 附加事件计入 LOEO，Francine 单独事件；Holland+残差固定75 km，OK75 对照，OKfit 增列。Holland 链 2 min/5 s 时距换算及 500 m 参考高度均为 B 节点预登记假设（`b_tc/v1/PREREG_v1.md`），非文献取值；近眼断报幸存者偏差。|',
       '|温带|`h3/peaks_h3.csv`；只留 ne_20190128_wide、ne_20210114_wide、ks_20221202、tx_20191126；ks_20180306 有 VCTS 不合规。推荐 OKfit。|',
       '|雷暴|`h4/peaks_h4v3.csv`；排除不可评 2025-03-04。推荐持续风 IDW，阵风 OK75；均只对有效分钟的事件峰值。|',
       '|校正/区间|加性均值、OLS 线性、经验分位排序映射（外推截断）、非负裁剪；80% 区间用训练折内绝对残差分位，均为 H5 预登记假设，不做复杂模型或事后调参。|',
       '', '## 已知局限',
       '留出事件数少，事件差异大；训练残差用于拟合又校准区间，覆盖率可能乐观。良态资料为小时 METAR，雷暴为1分钟；飓风与温带是不同事件站网。推荐方法按协议固定，不将表中事后更优校正挑成最终方法。站点留一不证明对无站损失点有效，事件峰值在断报时可能截尾。所有时间 UTC；对风向、阵风/持续风不交叉借参。外部输入未更新，无新增外部数据。',
       '', '## 结论'])
    for key in ('fair/sustained','hurricane/sustained','extratropical/sustained','thunderstorm/sustained','hurricane/gust','extratropical/gust','thunderstorm/gust'):
        if key not in result: continue
        c=result[key]['recommended']['combined']
        verdicts='；'.join(f'{m} {c[m]["verdict"]}（偏差{c[m]["bias"]:+.2f}、RMSE{c[m]["rmse"]:.2f}）' for m in METHODS[1:])
        text.append(f'{key}：原始偏差 {c["raw"]["bias"]:+.2f}、RMSE {c["raw"]["rmse"]:.2f} m/s；{verdicts}。')
    return '\n'.join(text)+'\n'

def plot(predictions):
    groups=['fair','hurricane','extratropical','thunderstorm']
    fig,axs=plt.subplots(2,4,figsize=(15,7),sharex=False,sharey=False)
    for j,group in enumerate(groups):
        for i,var in enumerate(['sustained','gust']):
            ax=axs[i,j]; rows=[r for r in predictions if r['category']==group and r['variable']==var and r['feature']=='recommended']
            raw=[r for r in rows if r['method']=='raw']; cor=[r for r in rows if r['method']=='additive']
            if not raw: ax.axis('off'); continue
            for rs,color,label in [(raw,'#7f8c8d','raw'),(cor,'#dc593a','additive LOEO')]:
                ax.scatter([r['observation'] for r in rs],[r['prediction'] for r in rs],s=8,alpha=.37,color=color,label=label)
            lim=max(max(r['observation'],r['prediction']) for r in rows)*1.05
            ax.plot([0,lim],[0,lim],'k--',lw=.8); ax.set_xlim(0,lim); ax.set_ylim(0,lim)
            ax.set_title(f'{group} / {var} (n={len(raw)})'); ax.set_xlabel('Observed peak (m/s)'); ax.set_ylabel('Predicted peak (m/s)')
            if j==0 and i==0: ax.legend(fontsize=8)
    fig.suptitle('IEM ASOS/AWOS station peaks; existing H1/H2/H3/H4 leave-station-out predictions; event-held-out calibration')
    fig.tight_layout(); fig.savefig(ROOT/'peak_scatter_h5.png',dpi=145); plt.close(fig)

def main():
    data=collect(); result,predictions=validate(data); cross,crosspred=validate(data,cross=True)
    metrics={'protocol':'prereg_h5.md','input_counts':dict(('/'.join(k),sum(1 for r in data if (r['category'],r['variable'])==k)) for k in sorted(set((r['category'],r['variable']) for r in data))),
             'within_type_LOEO':result,'cross_type':cross}
    (ROOT/'metrics_h5.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'results_h5.md').write_text(report(result,cross,data))
    plot(predictions)
    print('input_counts',metrics['input_counts'])
    for k,v in result.items():
        if 'recommended' in v:
            x=v['recommended']['combined']; print(k,[(m,round(x[m]['bias'],3),round(x[m]['rmse'],3),x[m].get('verdict')) for m in METHODS])
    print('saved',ROOT/'results_h5.md',ROOT/'metrics_h5.json',ROOT/'peak_scatter_h5.png')
if __name__=='__main__': main()
