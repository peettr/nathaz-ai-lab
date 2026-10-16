"""Compare old r2 baseline with r3 under identical hypothesized registration."""
from pathlib import Path
import json,csv,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
B=Path('./22_Lab/06_Logs/luw');sys.path.insert(0,str(B/'pydeps'))
import xlrd
new=json.loads((B/'samples_r3.json').read_text());old=np.load(B/'caseE_N_avg_z2_slice.npz');u=old['u'];org=old['origin'];dx=float(old['spacing']);uref=new['uref']
book=xlrd.open_workbook('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM/CaseE(Niigata).xls');sh=book.sheet_by_name('Geometry&Points');xy=np.array([[sh.cell_value(i,j) for j in (2,3)] for i in range(2,82)],dtype=float);ids=np.array([int(sh.cell_value(i,1)) for i in range(2,82)])
assert [r['id'] for r in new['rows']]==ids.tolist()
obs={key:np.array([float(book.sheet_by_name(sheet).cell_value(i+1,2)) for i in range(2,82)]) for key,sheet in [('before','Results (Before Construction)'),('after','Results (After Construction)')]}
shift=np.array([1010.50008,1000.60004]);oldsim=[]
for x,y in xy+shift:
 i=int(np.floor((x-org[0])/dx));j=int(np.floor((y-org[1])/dx));a=(x-org[0])/dx-i;b=(y-org[1])/dx-j
 v=(1-a)*(1-b)*u[j,i]+a*(1-b)*u[j,i+1]+(1-a)*b*u[j+1,i]+a*b*u[j+1,i+1]
 oldsim.append(float(np.linalg.norm(v)/uref))
oldsim=np.array(oldsim);fine=np.array([r['linear_ratio'] for r in new['rows']]);above=np.array([r['above_fluid']['ratio'] if r['above_fluid'] else np.nan for r in new['rows']]);series={'old_3p39m_linear_2m':oldsim,'fine_linear_2m':fine,'fine_first_fullfluid_node_ge2m':above}
metrics={}
for name,sim in series.items():
 metrics[name]={}
 for state,ref in obs.items():
  ok=np.isfinite(sim)&np.isfinite(ref); metrics[name][state]={'n':int(ok.sum()),'obs_mean':float(ref[ok].mean()),'sim_mean':float(sim[ok].mean()),'sim_over_obs_mean':float(sim[ok].mean()/ref[ok].mean()),'mae':float(np.mean(np.abs(sim[ok]-ref[ok]))),'r':float(np.corrcoef(sim[ok],ref[ok])[0,1])}
print(json.dumps(metrics,indent=2))
(B/'CaseE_N_metrics_r3.json').write_text(json.dumps({'assumption':'xls XY = raw STL XY, same axes; PF = raw + (1010.50008,1000.60004,-0.10) m; no verified building state','quantity':'norm(time mean velocity)/U_inflow(15.9m), Uref 3.9286416 m/s; xls N wind 2m U/U15.9','fine':{k:new[k] for k in ['dimensions','origin','dx','k_above_2m','z_above_m','upstream']},'old_dx':dx,'metrics':metrics,'fine_fullfluid_method':'all four bilinear horizontal corners of first vertical level >=2m have nonzero norm >1e-7 in mean VTK; solid proxy, not explicit voxel flags'},indent=2))
with (B/'CaseE_N_points_r3.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','xls_x_m','xls_y_m','old_linear_2m','fine_linear_2m','fine_first_fullfluid_node_ge2m','above_height_m','before_N','after_N','fine_low_fluid_corners','fine_high_fluid_corners'])
 for i,row in enumerate(new['rows']):w.writerow([ids[i],*xy[i],oldsim[i],fine[i],above[i],row['above_fluid']['z_m'] if row['above_fluid'] else '',obs['before'][i],obs['after'][i],row['linear_lo_fluid_corners'],row['linear_hi_fluid_corners']])
fig,axs=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
for ax,(state,ref) in zip(axs,obs.items()):
 for name,sym,col in [('old_3p39m_linear_2m','o','#6b7280'),('fine_linear_2m','^','#e59529'),('fine_first_fullfluid_node_ge2m','x','#2679ad')]:
  s=series[name];m=metrics[name][state];ax.scatter(ref,s,marker=sym,s=19,alpha=.64,color=col,label=f'{name}: MAE {m["mae"]:.3f}, r {m["r"]:.2f}, mean ratio {m["sim_over_obs_mean"]:.2f}')
 ax.plot([0,1.7],[0,1.7],color='black',lw=.7);ax.set(xlim=(0,1.7),ylim=(0,1.7),xlabel='Tunnel U(2m)/Uin(15.9m)',ylabel='LUW |mean u|/Uin(15.9m)',title=f'{state} construction, N (assumed XY registration)');ax.legend(fontsize=7,loc='upper left')
fig.savefig(B/'CaseE_N_scatter_r3.png',dpi=150);plt.close(fig)
