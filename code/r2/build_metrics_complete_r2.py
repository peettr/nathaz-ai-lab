"""Non-destructive compact old/new comparison companion to full raw metrics."""
import json
import statistics
from pathlib import Path
p = Path(__file__).resolve().parent
new = json.loads((p/'metrics_D_yawfix.json').read_text())
old = json.loads((p.parent.parent/'metrics_D.json').read_text())
assert (new['completed_storm'],new['completed_stationary']) == (360,36)
keys=('tower_top_yaw_absmax_kNm','tower_fore_aft_negative_magnitude_kNm','blade_root_negative_magnitude_kNm')
d={'source_new':'metrics_D_yawfix.json','source_old':'../../metrics_D.json',
   'completed_storm':360,'completed_stationary':36,'stationary_secant_max_deg_s':new['stationary_yaw_max_deg_s'],
   'stationary_secant_over_limit_count':len(new['stationary_rate_exceptions']),
   'storm_secant_over_limit':new['rate_exceptions'], 'paths':{}}
for c in ('I_near','III_kzm05','III_kzm00'):
    d['paths'][c]={'gate_old':old['gates'][c],'gate_new':new['gates'][c],'groups':{}}
    for g in new['rules']:
        a,b=old['summaries'][c][g],new['summaries'][c][g]
        ar=[x['yaw_rate_max_deg_s'] for x in old['records'][c] if x['group']==g]
        br=[x['yaw_rate_max_deg_s'] for x in new['records'][c] if x['group']==g]
        assert len(ar)==len(br)==12
        d['paths'][c]['groups'][g]={
            'paired_reduction_median_pct_old':{k:a['metrics'][k]['median_reduction_pct'] for k in keys},
            'paired_reduction_median_pct_new':{k:b['metrics'][k]['median_reduction_pct'] for k in keys},
            'paired_wilcoxon_two_sided_p_old':{k:a['metrics'][k]['wilcoxon_p'] for k in keys},
            'paired_wilcoxon_two_sided_p_new':{k:b['metrics'][k]['wilcoxon_p'] for k in keys},
            'false_stop_old':a['false_stop_count'],'false_stop_new':b['false_stop_count'],
            'secant_deg_s_old':{'median':statistics.median(ar),'max':max(ar),'over_0p31':sum(x>.31 for x in ar)},
            'secant_deg_s_new':{'median':statistics.median(br),'max':max(br),'over_0p31':sum(x>.31 for x in br)},
            'yaw_error_at_trigger_median_deg_old':None,
            'yaw_error_at_trigger_median_deg_new':b['yaw_error_at_trigger_median_deg']}
d['method_note']='Old ASCII secants not high-precision equivalent; old I_near s112 G1 0.813 inconsistent with rerun. G1 new yaw error is at scheduled comparison time, not an actual shutdown.'
d['rate_gate_note']='Revision 2 is post-hoc: 16 S3_30 failures remain; do not call all-run rate limit passed. Stationary rules np.gradient instantaneous yaw_max_rate_deg_s is not the 1 s secant gate.'
out=p/'metrics_D_yawfix_complete_r2.json'
assert not out.exists(), 'Existing output immutable'
out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print(out)
