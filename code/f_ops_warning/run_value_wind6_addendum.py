#!/usr/bin/env python3
"""Additive, immutable 6 m/s replay; leaves original F deliverables unchanged."""
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run_value as f

T = 6
OUT = Path(__file__).resolve().parent

def main():
    target = OUT/'metrics_wind6_addendum.json'
    plots = [OUT/f'value_curves_wind6_{lead}h_{scale}.png' for lead in (24,48) for scale in ('instant','daily')]
    for p in [target]+plots:
        if p.exists(): raise FileExistsError(f'Refusing overwrite: {p}')
    tr, te = f.read(2022), f.read(2023)
    results = {}
    for lead in (24,48):
        train=f.assemble(tr,'wind',T,lead)
        cols=[f'P_{s}' for s in f.SOURCES]
        train=train.dropna(subset=['obs']+cols)
        y=(train.obs>=T).astype(int)
        info={'cases':len(y),'events':int(y.sum())}
        mdl=None
        if y.sum()>=30 and len(y)-y.sum()>=30:
            mdl=LogisticRegression(C=1.,max_iter=1000,random_state=f.SEED)
            mdl.fit(train[cols],y)
            info.update(coefficients=mdl.coef_[0].tolist(), intercept=float(mdl.intercept_[0]))
        else: info['omitted']='<30 events or non-events'
        a=f.assemble(te,'wind',T,lead,mdl)
        if mdl is None: a['P_stack']=a.P_multi
        a=a.dropna(subset=['obs']+f.METHODS).copy()
        for scale,b in [('instant',a),('daily',f.day_version(a))]:
            key=f'wind_{T}_{lead}h_{scale}'
            results[key]=f.compute(b,T,None)
            results[key]['stack_training']=info
            if mdl is None: results[key]['methods']['P_stack']['not_fitted']=True
            r=results[key]
            fig,ax=plt.subplots(figsize=(9,5))
            for m in f.METHODS:
                ax.plot(f.RATIOS,r['methods'][m]['V'],label=m,linewidth=2 if m=='P_multi' else 1,alpha=1 if m=='P_multi' else .7)
            ax.axhline(0,color='gray',linewidth=.7)
            ax.axvspan(.05,.5,alpha=.06,color='orange')
            ax.set(xlim=(0,1),xlabel='C/L',ylabel='Relative economic value V',title=f'Wind ≥6 m/s, {lead}h, {scale}; {r["events"]}/{r["cases"]} events')
            ax.grid(alpha=.15)
            ax.legend(fontsize=7,ncol=2)
            fig.text(.02,.015,'Data: ASOS/IEM; GraphCast/Pangu/FourCastNet v2 via AWS AIWP; NOAA GFS AWS. 2022 calibration, 2023 test.',fontsize=7)
            fig.tight_layout(rect=(0,.04,1,1))
            fig.savefig(OUT/f'value_curves_wind6_{lead}h_{scale}.png',dpi=140)
            plt.close(fig)
    payload={'input_files':[str(f.INPUT/f'paired_station_{x}.csv.gz') for x in ('train','test')],
             'definitions':{'ratios':f.RATIOS.tolist(),'bootstrap':'1000 verifying UTC-day grouped resamples; same method as run_value.py',
                            'daily':'assumption: per station UTC verifying day, both 00/12 UTC observations; max event and decision',
                            'cost_loss_band':'assumption C/L 0.05..0.50; report-only wind 6 m/s; primary gate stays wind 10 m/s, 24 h'},
             'results':results,'plots':[p.name for p in plots]}
    target.write_text(json.dumps(f.clean(payload),ensure_ascii=False,indent=2,allow_nan=False))
    for k,r in results.items():
        m=r['methods'];g=r['gate']
        print(k,'cases/events/days',r['cases'],r['events'],r['days'],'P_multi',m['P_multi']['mean_V_0.05_0.50'],
              'P_stack',m['P_stack']['mean_V_0.05_0.50'],'P_GFS',m['P_GFS']['mean_V_0.05_0.50'],
              'best',g['best_deterministic'],g['best_deterministic_mean_V'], 'delta',g['multi_minus_best_mean_V'],g['multi_minus_best_ci95'])
    print('WRITTEN',target,*plots)

if __name__=='__main__': main()
