"""Strictly aggregate stage-two metrics; never classify an incomplete matrix.
Input rows must have test subgroup per-case R2/RMSE from frozen raw evaluator.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
SIZES=(50,100,200,371)
SEEDS=(17,42,73)
CATEGORIES=('all','ideal','real')


def power_fit(ns, errors):
    """Fit positive a,b,c by bounded grid on b,c; least-squares a."""
    x=np.asarray(ns,dtype=float)
    y=np.asarray(errors,dtype=float)
    best=None
    for b in np.linspace(0.025,2.5,300):
        z=x**(-b)
        a,c=np.linalg.lstsq(np.column_stack((z,np.ones_like(z))),y,rcond=None)[0]
        if a < 0 or c < 0:
            continue
        err=float(np.sum((a*z+c-y)**2))
        if best is None or err<best[0]: best=(err,float(a),float(b),float(c))
    if best is None: raise ValueError('positive monotone power law unsupported by these observations')
    return {'a':best[1],'b':best[2],'c':best[3],'sse':best[0]}


def aggregate(rows, subset):
    names=list(subset)
    r2=[rows[c]['r2'] for c in names]
    sq=sum(rows[c]['rmse']**2*rows[c]['n'] for c in names)
    n=sum(rows[c]['n'] for c in names)
    return {'median_r2':float(np.median(r2)), 'pooled_rmse':float(math.sqrt(sq/n)), 'cases':len(names)}


def analyze(payload, manifest):
    test=manifest['test_cases']
    types=payload['type_by_case']
    assert set(types)==set(test) and sum(types[c]=='ideal' for c in test)==40
    assert sum(types[c]=='real' for c in test)==60
    partitions={'all':test,'ideal':[c for c in test if types[c]=='ideal'],
                'real':[c for c in test if types[c]=='real']}
    results={}
    for size in SIZES:
        for seed in SEEDS:
            key=f'{size}_{seed}'
            row=payload['models'][key]
            assert set(row['test'])==set(test), key
            # First-stage seed17 saved only a validation median, not per-case errors.
            if row.get('val') is not None:
                assert set(row['val'])==set(manifest['val_cases']), key
            results[key]={part:aggregate(row['test'],cases) for part,cases in partitions.items()}
            results[key]['val']=(aggregate(row['val'],manifest['val_cases'])
                                 if row.get('val') is not None else None)
    baselines={}
    for name in ('B0','B1','B2'):
        rows=payload['baselines'][name]
        assert set(rows['test'])==set(test) and set(rows['val'])==set(manifest['val_cases'])
        baselines[name]={part:aggregate(rows['test'],cases) for part,cases in partitions.items()}
        baselines[name]['val']=aggregate(rows['val'],manifest['val_cases'])
    actual={f'{size}_{seed}': manifest['seeds'][str(seed)]['all' if size==371 else str(size)]['actual_cases']
            for size in SIZES for seed in SEEDS}
    fits={}
    for part in CATEGORIES:
        fits[part]=power_fit([actual[f'{size}_{seed}'] for size in SIZES for seed in SEEDS],
                             [results[f'{size}_{seed}'][part]['pooled_rmse'] for size in SIZES for seed in SEEDS])
    # Literal gate on measured all-test raw-pixel pooled RMSE, not a fitted decrease.
    r200=np.array([results[f'200_{s}']['all']['pooled_rmse'] for s in SEEDS])
    rall=np.array([results[f'371_{s}']['all']['pooled_rmse'] for s in SEEDS])
    drop=float(np.mean(r200)-np.mean(rall))
    dispersion=float(2*np.sqrt((np.var(r200,ddof=1)+np.var(rall,ddof=1))/2))
    # Separately fit 1 - observed median per-case R2; never convert pooled
    # RMSE into R2. Power-law extrapolation is model-dependent, not measured.
    r2_extrapolation={}
    for part in CATEGORIES:
        r2_values=[np.mean([results[f'{size}_{seed}'][part]['median_r2'] for seed in SEEDS]) for size in SIZES]
        r2_fit=power_fit([actual[f'{size}_{seed}'] for size in SIZES for seed in SEEDS],
                         [1-results[f'{size}_{seed}'][part]['median_r2'] for size in SIZES for seed in SEEDS])
        projected_r2=1-(r2_fit['a']*1600**(-r2_fit['b'])+r2_fit['c'])
        r2_extrapolation[part]={'fit_1_minus_median_r2':r2_fit,
                                'mean_observed_full_r2':float(r2_values[-1]),
                                'projected_r2_1600':float(projected_r2),
                                'projected_r2_gain':float(projected_r2-r2_values[-1])}
    r2_fit=r2_extrapolation['all']['fit_1_minus_median_r2']
    projected_r2=r2_extrapolation['all']['projected_r2_1600']
    r2_gain=r2_extrapolation['all']['projected_r2_gain']
    criterion1={'observed_rmse_drop':drop,'twice_seed_sd':dispersion,
                'twice_sd_200':float(2*np.std(r200,ddof=1)),
                'twice_sd_all':float(2*np.std(rall,ddof=1)),
                'rmse_condition':bool(drop>dispersion),'r2_fit_1_minus_median':r2_fit,
                'projected_r2_1600':projected_r2,'projected_r2_gain':r2_gain,
                'r2_1600_condition':bool(r2_gain>=.03),
                'pass':bool(drop>dispersion and r2_gain>=.03)}
    b=min(baselines,key=lambda name:baselines[name]['all']['pooled_rmse'])
    deep=np.mean([results[f'371_{s}']['all']['pooled_rmse'] for s in SEEDS])
    wins=[]
    for case in test:
        rmse=np.mean([payload['models'][f'371_{s}']['test'][case]['rmse'] for s in SEEDS])
        wins.append(rmse < payload['baselines'][b]['test'][case]['rmse'])
    geometry={}
    for case in test:
        geometry.setdefault(case.rsplit('_d',1)[0],[]).append(case)
    assert len(geometry)==80, len(geometry)
    geometry_wins={}
    for group,cases in geometry.items():
        def pooled(rows):
            return math.sqrt(sum(rows[c]['rmse']**2*rows[c]['n'] for c in cases)/sum(rows[c]['n'] for c in cases))
        deep_group=np.mean([pooled(payload['models'][f'371_{s}']['test']) for s in SEEDS])
        geometry_wins[group]=bool(deep_group<pooled(payload['baselines'][b]['test']))
    criterion2={'best_baseline':b,'deep_rmse':float(deep),
                'baseline_rmse':baselines[b]['all']['pooled_rmse'],
                'gain_fraction':float(1-deep/baselines[b]['all']['pooled_rmse']),
                'case_wins':int(sum(wins)),'case_count':len(wins),
                'geometry_wins':sum(geometry_wins.values()),'geometry_count':len(geometry),
                'geometry_threshold':math.ceil(2*len(geometry)/3),
                'geometry_wins_by_name':geometry_wins,
                'pass':bool(deep<=.8*baselines[b]['all']['pooled_rmse'] and
                            sum(geometry_wins.values())>=math.ceil(2*len(geometry)/3))}
    verdict={(True,True):'值得造数据',(True,False):'数据有用但先查经典方法',
             (False,True):'已到平台',(False,False):'不值得'}[(criterion1['pass'],criterion2['pass'])]
    return {'models':results,'baselines':baselines,'fits':fits,'r2_extrapolation':r2_extrapolation,
            'actual_cases':actual,'criterion1':criterion1,
            'criterion2':criterion2,'verdict':verdict,
            'warning':'N=1600 median R2 is model-dependent extrapolation from 1-median-R2, not measurement'}


def plot(result, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for category in ('ideal','real'):
        fig,ax=plt.subplots(figsize=(6,4))
        vals=np.array([[result['models'][f'{size}_{seed}'][category]['pooled_rmse'] for seed in SEEDS] for size in SIZES])
        xx=np.array([[result['actual_cases'][f'{size}_{seed}'] for seed in SEEDS] for size in SIZES])
        ax.errorbar(xx.mean(axis=1),vals.mean(axis=1),yerr=[vals.mean(axis=1)-vals.min(axis=1),vals.max(axis=1)-vals.mean(axis=1)],
                    marker='o',capsize=4,label='R11 mean ± seed range')
        for name,row in result['baselines'].items():
            ax.axhline(row[category]['pooled_rmse'],label=name,linestyle='--')
        ax.set(xlabel='training cases N',ylabel='raw valid-pixel RMSE',title=f'{category} held-out cohort')
        ax.legend();fig.tight_layout()
        filename=path/f'v6s2_curve_{category}.png'
        assert not filename.exists()
        fig.savefig(filename,dpi=160);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('metrics',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert not a.output.exists()
    manifest=json.loads((ROOT/'v6_nested_subsets.json').read_text())
    result=analyze(json.loads(a.metrics.read_text()),manifest)
    a.output.write_text(json.dumps(result,indent=2))
    plot(result,a.output.parent)
    print('ANALYZED',a.output,'verdict',result['verdict'])
