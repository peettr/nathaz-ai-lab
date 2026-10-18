"""A3-D postprocess: paired reductions, preregistered gate, Wilcoxon, figures."""
import json,math,sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.stats import wilcoxon
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path('/content/a3_d_1015');R=P/'results';seeds=[112,203,317,419,523,631,733,827,941,1051,1163,1277]
rules=['G1','G2L','G2','S1','S2_23','S2_24','S3_30','S3_20','S4_05','S4_1']
keys=['tower_top_yaw_absmax_kNm','tower_resultant_max_kNm','tower_fore_aft_positive_max_kNm','tower_fore_aft_negative_magnitude_kNm','blade_root_positive_max_kNm','blade_root_negative_magnitude_kNm','rotor_speed_overshoot_vs_12p1_pct']
stationary=json.loads((R/'stationary_rules_all.json').read_text());assert len(stationary)==36
false={g:sum(int(x['rules'][g]['false_stop']) for x in stationary) for g in rules}
false_by_mean={str(m):{g:sum(int(x['rules'][g]['false_stop']) for x in stationary if x['mean_mps']==m) for g in rules} for m in (18,20,22)}
records={};summaries={};gates={}
for case in ('I_near','III_kzm05','III_kzm00'):
 rec={}
 for seed in seeds:
  for g in rules:
   f=R/f'{case}_s{seed}_{g}.json';assert f.exists(),str(f)
   d=json.loads(f.read_text());assert d['returncode']==0 and len(d['metrics'])==7,(f,d.get('error_tail'))
   if case=='I_near' and seed==112 and g=='G1':
    zz=np.load(R/'I_near_s112_G1_yaw.npz');tt=zz['t'];yy=zz['yaw'];ii=np.searchsorted(tt,tt+1);vv=ii<len(tt)
    d['yaw_rate_max_deg_s']=float(np.max(np.abs((yy[ii[vv]]-yy[vv])/(tt[ii[vv]]-tt[vv]))))
   rec[(seed,g)]=d
 records[case]=[rec[k] for k in sorted(rec)]
 summaries[case]={}
 base=np.array([rec[(s,'G1')]['metrics']['tower_top_yaw_absmax_kNm'] for s in seeds]);assert np.all(base>0)
 for g in rules:
  sample=[rec[(s,g)] for s in seeds]
  rel={}
  for key in keys:
   b=np.array([rec[(s,'G1')]['metrics'][key] for s in seeds]);v=np.array([x['metrics'][key] for x in sample]);valid=b>0
   pct=np.full(len(b),np.nan);pct[valid]=100*(b[valid]-v[valid])/b[valid]
   differences=v-b
   try:pval=float(wilcoxon(differences,zero_method='wilcox',alternative='two-sided').pvalue) if np.any(differences!=0) else 1.
   except ValueError:pval=None
   rel[key]=dict(paired_reduction_pct=[float(x) if np.isfinite(x) else None for x in pct],median_reduction_pct=float(np.nanmedian(pct)) if np.any(valid) else None,
                 median_abs=float(np.median(v)),range_abs=[float(v.min()),float(v.max())],wilcoxon_p=pval)
  summaries[case][g]=dict(n=12,metrics=rel,median_lead_s=float(np.median([x['actual_lead_s'] for x in sample if x.get('actual_lead_s') is not None])) if g!='G1' and any(x.get('actual_lead_s') is not None for x in sample) else None,
    trigger_count=sum(x['trigger_abs_s'] is not None for x in sample),yaw_rate_max_deg_s=max(float(x['yaw_rate_max_deg_s']) for x in sample),false_stop_count=false[g])
 yaw=summaries[case]['G2L']['metrics']['tower_top_yaw_absmax_kNm']['median_reduction_pct']
 fore=summaries[case]['G2L']['metrics']['tower_fore_aft_negative_magnitude_kNm']['median_reduction_pct']
 blade=summaries[case]['G2L']['metrics']['blade_root_negative_magnitude_kNm']['median_reduction_pct']
 qualifying=[g for g in rules if g.startswith('S') and summaries[case][g]['metrics']['tower_top_yaw_absmax_kNm']['median_reduction_pct']>=.8*yaw]
 condition_a=yaw>=10;condition_b=fore>=-10 and blade>=-10
 condition_c=all(false[g]>false['G2L'] for g in qualifying)
 gates[case]=dict(a=condition_a,b=condition_b,c=condition_c,passes=bool(condition_a and condition_b and condition_c),yaw_reduction_pct=yaw,fore_aft_negative_reduction_pct=fore,blade_negative_reduction_pct=blade,qualifying_simple=qualifying,disqualifying_simple=[g for g in qualifying if false[g]<=false['G2L']],yaw_rate_max_deg_s=max(summaries[case][g]['yaw_rate_max_deg_s'] for g in rules))
output=dict(expected_storm=3*12*len(rules),completed_storm=sum(len(x) for x in records.values()),expected_stationary=36,completed_stationary=len(stationary),seeds=seeds,rules=rules,metrics_keys=keys,records=records,summaries=summaries,gates=gates,false_stop_total=false,false_stop_by_mean=false_by_mean,stationary_records=stationary,
 notes=['three blades maximized per time/seed; ASCII 0.01 deg NacYaw yaw rate measured as 1 s secant','G2L moving analytic point at -D nacelle axis, inherited 3x3 fixed upstream turbulent residual: not a true moving-point cross-spectral interpolation','case III kzm 0/.05 both retained; PDF p113 text .05 vs p114 Table4.4 0','trigger offline replay; stationary 600 s count is not operational false-stop probability'])
(R/'metrics_D.json').write_text(json.dumps(output,indent=2,ensure_ascii=False))
fig,axs=plt.subplots(1,3,figsize=(19,6),sharey=True)
for ax,case in zip(axs,('I_near','III_kzm05','III_kzm00')):
 for j,g in enumerate(rules):
  d=summaries[case][g]['metrics']['tower_top_yaw_absmax_kNm'];v=d['median_reduction_pct'];arr=d['paired_reduction_pct']
  ax.scatter(false[g]+np.linspace(-.19,.19,12),arr,s=12,alpha=.4);ax.scatter(false[g],v,marker='D',s=55,label=g);ax.annotate(g,(false[g],v),xytext=(3,3),textcoords='offset points',fontsize=7)
 ax.set(xlabel='False-stop windows / 36 (600 s each)',title=case,xlim=(-1,37));ax.axhline(0,c='k',lw=.6);ax.grid(alpha=.2)
axs[0].set_ylabel('Paired yaw peak reduction vs G1 [%]')
fig.suptitle('A3-D: Nguyen 2012 analytic + translation-scaled Kaimal/Veers approx; OpenFAST 5 / ROSCO 2.10.6 | diamonds median; dots 12 seeds')
fig.tight_layout();fig.savefig(R/'tradeoff_D.png',dpi=160);plt.close(fig)
fig,axs=plt.subplots(2,3,figsize=(17,9))
for j,case in enumerate(('I_near','III_kzm05','III_kzm00')):
 for i,key in enumerate(('tower_fore_aft_negative_magnitude_kNm','blade_root_negative_magnitude_kNm')):
  ax=axs[i,j]
  for g in ('G2L','G2','S2_23','S3_30','S4_05'):
   vals=summaries[case][g]['metrics'][key]['paired_reduction_pct'];ax.scatter([g]*12,vals,s=14,alpha=.5)
   ax.scatter([g],[np.median(vals)],marker='_',c='k',s=200)
  ax.axhline(-10,c='r',ls='--',lw=.8);ax.set(title=case,ylabel=key+' reduction vs G1 [%]');ax.tick_params(axis='x',rotation=25);ax.grid(alpha=.2)
fig.suptitle('A3-D three-blade negative flapwise / tower fore-aft | Nguyen 2012 approx + OpenFAST/ROSCO; points seeds, black medians')
fig.tight_layout();fig.savefig(R/'negative_load_D.png',dpi=160);plt.close(fig)
print('D_ANALYSIS',json.dumps({'counts':[output['completed_storm'],output['completed_stationary']], 'false':false,'gates':gates},ensure_ascii=False),flush=True)
