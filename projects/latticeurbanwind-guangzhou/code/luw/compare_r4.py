from pathlib import Path
import json,csv,sys,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
B=Path('./22_Lab/06_Logs/luw');sys.path.insert(0,str(B/'pydeps'));import xlrd
new=json.loads((B/'samples_r4.json').read_text());book=xlrd.open_workbook('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM/CaseE(Niigata).xls');ids=np.array([int(book.sheet_by_name('Geometry&Points').cell_value(i,1)) for i in range(2,82)]);assert [r['id'] for r in new['rows']]==ids.tolist()
assert book.sheet_by_name('Results (Before Construction)').cell_value(2,14)=='W'
obs={key:np.array([float(book.sheet_by_name(sheet).cell_value(i+1,14)) for i in range(2,82)]) for key,sheet in [('before','Results (Before Construction)'),('after','Results (After Construction)')]}
sim=np.array([r['linear_ratio'] for r in new['rows']]);metrics={}
for state,ref in obs.items():metrics[state]={'n':len(sim),'obs_mean':float(ref.mean()),'sim_mean':float(sim.mean()),'sim_over_obs_mean':float(sim.mean()/ref.mean()),'mae':float(np.mean(np.abs(sim-ref))),'r':float(np.corrcoef(sim,ref)[0,1])}
old=json.loads((B/'CaseE_N_metrics_r3.json').read_text());out={'source':'Han et al 2026 arXiv v2 sec 2.3.1 pp 11-12, Fig 1 p11; xls results W col14 2m / inflow 15.9m','assumption':'xls XY = raw STL XY, axes same; PF=raw+(1010.50008,1000.60004,-0.10)m; building construction state not certified','quantity':'norm(time mean velocity) interpolated z=2m / profile.dat interpolated U15.9=3.9286416m/s; xls W normalized 2m speed','r4':{'dx':new['dx'],'dim':new['dimensions'],'upstream':new['upstream'],'low_fluid_corner_count':sum(r['lower_fluid_corners']<4 for r in new['rows']),'high_fluid_corner_count':sum(r['upper_fluid_corners']<4 for r in new['rows'])},'r4_metrics':metrics,'r3_north_1p86m_context_only':old['metrics']['fine_linear_2m']}
(B/'CaseE_W_metrics_r4.json').write_text(json.dumps(out,indent=2))
with (B/'CaseE_W_points_r4.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['id','xls_x','xls_y','sim_w_ratio','before_W_ratio','after_W_ratio','lower_fluid_corners','upper_fluid_corners'])
 for i,row in enumerate(new['rows']):w.writerow([ids[i],*row['xls_xy'],sim[i],obs['before'][i],obs['after'][i],row['lower_fluid_corners'],row['upper_fluid_corners']])
fig,axs=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
for ax,(state,ref) in zip(axs,obs.items()):
 m=metrics[state];ax.scatter(ref,sim,s=25,alpha=.75,color='#2679ad',label=f'W 1m: MAE={m["mae"]:.3f}; r={m["r"]:.3f}; means={m["sim_over_obs_mean"]:.2f}')
 ax.plot([0,1.7],[0,1.7],color='black',lw=.7);ax.set(xlim=(0,1.7),ylim=(0,1.7),xlabel='Wind-tunnel W: U(2m)/Uin(15.9m)',ylabel='LUW west: |mean u|(2m)/Uin(15.9m)',title=f'{state} construction; assumed XY alignment');ax.legend(fontsize=9,loc='upper left')
fig.savefig(B/'CaseE_W_scatter_r4.png',dpi=150);plt.close(fig)
print(json.dumps(out,indent=2))
