"""Read-only R5 RMW-stratified descriptive bins; write only new supplement outputs."""
import csv, json, collections, statistics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
rows=list(csv.DictReader((P/'r5_buildings_audit.csv').open()))
assert len(rows)==1114 and len({(r['area'],r['building_id']) for r in rows})==1114
BINS={'ian_harlem':[73.9,74,74.1,74.2,74.3], 'idalia_jena':[55,56,57,58,59,60,61]}
GROUPS=('<1','1-3','>3','unknown')
SEED=20261014
rng=np.random.default_rng(SEED)
out={}
fig,axes=plt.subplots(2,2,figsize=(12,8))
for i,(area,edges) in enumerate(BINS.items()):
    eligible=[r for r in rows if r['area']==area and r['eligible_label']=='True']
    assert len(eligible)==(912 if area=='ian_harlem' else 112)
    out[area]={}
    for group in GROUPS:
        selected=[r for r in eligible if r['rmw_bin_at_gust_peak']==group]
        ratios=[float(r['rmw_ratio_at_gust_peak']) for r in selected]
        assert all((x<1 if group=='<1' else 1<=x<=3 if group=='1-3' else x>3) for x in ratios)
        blocks=sorted({r['block_500m'] for r in selected})
        byblock={b:[r for r in selected if r['block_500m']==b] for b in blocks}
        result={'n':len(selected),'blocks':len(blocks),'ratio_min':min(ratios) if ratios else None,'ratio_max':max(ratios) if ratios else None,'strict_water_excluded_n':sum(r['water_risk_proxy']=='False' for r in selected),'bins':[]}
        for lo,hi in zip(edges[:-1],edges[1:]):
            members=[r for r in selected if lo<=float(r['model_gust_mps'])<hi]
            entry={'low_mps':lo,'high_mps':hi,'n':len(members),'blocks':len({r['block_500m'] for r in members})}
            for threshold in ('minor','major'):
                key='damage_ge_'+threshold
                entry[threshold+'_n']=sum(int(r[key]) for r in members)
                entry[threshold+'_rate']=entry[threshold+'_n']/len(members) if members else None
                draws=[]
                if blocks and members:
                    for _ in range(600):
                        sampled=[r for ix in rng.integers(0,len(blocks),len(blocks)) for r in byblock[blocks[ix]] if lo<=float(r['model_gust_mps'])<hi]
                        if sampled: draws.append(sum(int(r[key]) for r in sampled)/len(sampled))
                entry[threshold+'_ci_2p5']=float(np.quantile(draws,.025)) if draws else None
                entry[threshold+'_ci_97p5']=float(np.quantile(draws,.975)) if draws else None
            result['bins'].append(entry)
        out[area][group]=result
        for j,threshold in enumerate(('minor','major')):
            ax=axes[i,j]
            nonempty=[q for q in result['bins'] if q['n']]
            if not nonempty:continue
            mid=[(q['low_mps']+q['high_mps'])/2 for q in nonempty]
            vals=[q[threshold+'_rate'] for q in nonempty]
            lo=[v-q[threshold+'_ci_2p5'] for v,q in zip(vals,nonempty)]
            hi=[q[threshold+'_ci_97p5']-v for v,q in zip(vals,nonempty)]
            ax.errorbar(mid,vals,yerr=[lo,hi],fmt='o-',capsize=3,label=f'{group} RMW (n={len(selected)})')
            for x,y,q in zip(mid,vals,nonempty):ax.annotate(f"n={q['n']}; c={q['blocks']}",(x,y),xytext=(2,5),textcoords='offset points',fontsize=7)
    for j,threshold in enumerate(('minor','major')):
        ax=axes[i,j]
        ax.set(xlabel='H2 reconstructed P2 gust (m/s; not measured)',ylabel=f'Visible damage >= {threshold} fraction',title=f'{area}: RMW-stratified, water-risk included')
        ax.set_ylim(-.06,1.08);ax.grid(alpha=.2)
        ax.legend(title='No data: <1, >3, unknown',fontsize=8)
    assert sum(out[area][g]['n'] for g in GROUPS)==len(eligible)
fig.text(.5,.005,'CRASAR-U-DROIDs (CC BY 4.0); H2 Holland+residual / NHC best track. All usable buildings lie in 1–3 RMW; no <1 or >3 comparison.\nSuspected water exposure included; no water-screened sample. Reconstructed wind may be biased; <1 RMW station validation underestimates by ~2 m/s (not observed here).',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.06,1,1))
fig.savefig(P/'r5_damage_probability_rmw_supplement.png',dpi=160)
plt.close(fig)
(P/'r5_rmw_summary.json').write_text(json.dumps({'source':'r5_buildings_audit.csv','seed':SEED,'bootstrap':'600 resamples within area/RMW of 500m spatial clusters; conditional labels only','areas':out},indent=2))
for area,data in out.items():
    print(area, [(g,data[g]['n'],data[g]['ratio_min'],data[g]['ratio_max'],data[g]['strict_water_excluded_n']) for g in GROUPS])
    for q in data['1-3']['bins']:
        if q['n']:print(q['low_mps'],q['high_mps'],q['n'],q['minor_n'],q['major_n'])
# Sensitivity: if DAT numeric values were kt rather than mph, re-evaluate signed event medians.
dat=list(csv.DictReader((P/'dat_hurricane_points_r3.csv').open()))
for event in ('IDA','IDALIA','HELENE'):
    a=[r for r in dat if r['event']==event and r['dat_windspeed_numeric_assume_mph'] not in ('','-99') and float(r['dat_windspeed_numeric_assume_mph'])>0]
    if a:
        mph=[float(r['dat_windspeed_numeric_assume_mph'])-float(r['model_gust_mps'])*2.2369362921 for r in a]
        kt=[float(r['dat_windspeed_numeric_assume_mph'])*1.150779448-float(r['model_gust_mps'])*2.2369362921 for r in a]
        print(event,'DAT comparable n',len(a),'mph assumed median',statistics.median(mph),'if kt median',statistics.median(kt))
