from pathlib import Path
import json,math,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parent
P=json.loads((R/'parameters.json').read_text());u0=P['ustar_mps'];z0=P['z0_m'];kappa=P['kappa'];Uin=lambda z:u0/kappa*math.log((z+z0)/z0)
inputs={'off':R/'profile_off.json','on_wrong_index':R/'profile_on.json','on_corrected':R/'corrected_profile_on_corrected.json'}
data={name:{(q['x'],q['z']):q for q in json.loads(p.read_text())['rows']} for name,p in inputs.items()}
summary={'config':P,'ratios':{},'proxy_not_actual_wall_force':{},'mean_model_source':'solver_wallmodel_cont5_final.diff + cont4 setup index initialization','flux_closure_percent':None,'actual_time_mean_ustar_ratio':None}
for name,d in data.items():
 summary['ratios'][name]={}
 for x in (100,200,300,400):
  at=lambda z:d[(x,z)]['speed'];u159=at(15)+(at(16)-at(15))*.9
  summary['ratios'][name][x]={'U2':at(2)/Uin(2),'U5':at(5)/Uin(5),'U15_9':u159/Uin(15.9),'TI2':d[(x,2)]['TI']}
  if name=='on_corrected':
   u1=at(1);proxy=kappa*u1/math.log((.5+z0)/z0)
   summary['proxy_not_actual_wall_force'][x]={'sqrt_stress_from_mean_U1_mps':proxy,'ratio_to_inlet_ustar':proxy/u0}
plt.figure(figsize=(6,5))
for name,label,style in [('off','No wall model','--'),('on_corrected','First-layer wall model','-')]:
 d=data[name];plt.semilogy([d[(300,z)]['speed'] for z in range(2,61)],range(2,61),style,label=label)
plt.semilogy([Uin(z) for z in range(2,61)],range(2,61),':',label='Inlet log law')
plt.ylabel('z (m)');plt.xlabel('Mean |U| (m/s)');plt.title('Equilibrium-log inlet, x=300 m; averaging window 20,000 steps')
plt.grid(True,which='both',alpha=.3);plt.legend(fontsize=8);plt.tight_layout();plt.savefig(R/'eqlog_x300_profile_v2.png',dpi=160);plt.close()
(R/'eqlog_summary_v2.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
print(json.dumps(summary,indent=2,ensure_ascii=False))
