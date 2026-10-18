"""Seventh-round Case E paired-point comparisons and scatter plot."""
from pathlib import Path
import csv, json, statistics, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent
new=json.loads((p/'offset_samples_r7.json').read_text())
old={int(r['id']):r for r in csv.DictReader((p/'CaseE_W_points_r5.csv').open())}
long={int(r['id']):r for r in csv.DictReader((p/'CaseE_W_points_r6b.csv').open())}
rows=sorted(new['rows'],key=lambda r:r['id'])
assert [r['id'] for r in rows]==list(range(1,81)) and len(old)==len(long)==80
obs=[r['after'] for r in rows]
assert all(abs(r['after']-float(old[r['id']]['after']))<1e-10 and abs(r['after']-float(long[r['id']]['after']))<1e-10 for r in rows)
assert all(abs(r['sample']['plus_dx']['sim_ratio']-float(old[r['id']]['sim_best_xy_plus_dx_z0']))<1 for r in rows)
def metrics(y):
    return {'n':len(y),'mae':statistics.mean(abs(a-b) for a,b in zip(obs,y)),
            'r':statistics.correlation(obs,y),'sim_mean':statistics.mean(y),
            'obs_mean':statistics.mean(obs),'sim_over_obs_mean':statistics.mean(y)/statistics.mean(obs)}
columns={
    'r5_old_S_CFD':[float(old[r['id']]['sim_best_xy_plus_dx_z0']) for r in rows],
    'r6b_S_CFD':[float(long[r['id']]['sim_plus_dx']) for r in rows],
    'r7_S_CFD':[r['sample']['plus_dx']['sim_ratio'] for r in rows],
    'r7_S_exp':[r['sample']['plus_dx']['exp_ratio'] for r in rows],
}
assert all(math.isfinite(v) for arr in columns.values() for v in arr)
output={'definition':'After W / Uin(15.9 m), 80 aligned id, x/y +1 m, z +0 m. S_CFD=|<u>|, S_exp=sqrt(S_CFD^2+2k); k from mean VTK velocity second moments.','metrics':{key:metrics(y) for key,y in columns.items()},'upstream':new['upstream'],'dimensions':new['dimensions'],'uref_mps':new['uref'],'paired':{}}
for key,a,b in [('window_r7_minus_r5','r7_S_CFD','r5_old_S_CFD'),('domain_r6b_minus_r7','r6b_S_CFD','r7_S_CFD'),('scalar_r7_Sexp_minus_SCFD','r7_S_exp','r7_S_CFD')]:
    diff=[x-y for x,y in zip(columns[a],columns[b])]
    output['paired'][key]={'mean_delta':statistics.mean(diff),'median_delta':statistics.median(diff),'mean_abs_delta':statistics.mean(map(abs,diff)),'negative_points':sum(d<0 for d in diff),'positive_points':sum(d>0 for d in diff)}
with (p/'CaseE_W_points_r7.csv').open('w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['id','xls_x','xls_y','after_W','r5_S_CFD','r6b_S_CFD','r7_S_CFD','r7_S_exp','r7_tke_m2s2','r7_fluid_corners','r7_minus_r5','r6b_minus_r7','r7_Sexp_minus_SCFD'])
    for j,row in enumerate(rows):
        a=row['sample']['plus_dx']
        w.writerow([row['id'],*row['xls_xy'],obs[j],*[columns[key][j] for key in columns],a['tke_m2s2'],a['fluid_corners'],columns['r7_S_CFD'][j]-columns['r5_old_S_CFD'][j],columns['r6b_S_CFD'][j]-columns['r7_S_CFD'][j],columns['r7_S_exp'][j]-columns['r7_S_CFD'][j]])
(p/'CaseE_W_metrics_r7.json').write_text(json.dumps(output,indent=2))
fig,axs=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
for ax,key in zip(axs,['r7_S_CFD','r7_S_exp']):
    y=columns[key];m=output['metrics'][key]
    ax.scatter(obs,y,s=22,alpha=.75)
    ax.plot([0,1.7],[0,1.7],color='black',lw=.8)
    ax.set(xlim=(0,1.7),ylim=(0,1.7),xlabel='Wind tunnel After W / Uin(15.9m)',ylabel=key+'/ Uin(15.9m)',title=f'{key}: MAE={m["mae"]:.3f}; r={m["r"]:.3f}; mean ratio={m["sim_over_obs_mean"]:.3f}')
fig.savefig(p/'CaseE_W_scatter_r7.png',dpi=150)
print(json.dumps({'metrics':output['metrics'],'paired':output['paired']},indent=2))
