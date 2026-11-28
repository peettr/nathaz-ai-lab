import csv, hashlib, json, math, pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=pathlib.Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'wall_gate0.csv').open()))
assert [int(r['step']) for r in rows]==list(range(2001))
def col(name): return [float(r[name]) for r in rows]
px=col('px'); mass=col('ddf_mass_offset_all_cells'); rho=col('rho_mass'); force=col('wall_fx_sum')
g9,g16,t15,t10=[col(x) for x in ('ground9_delta','ground16_delta','top15_delta','top10_delta')]
res=[]; acc=0.0
with (p/'residual_2000.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(['step','px','ground_force','cumulative_ground_force','px_residual_ground_only','ground9_delta','ground16_delta','top15_delta','top10_delta','ground_signed_delta_vs_native','top_signed_delta_vs_native'])
 for i in range(2001):
  if i: acc+=force[i]
  v=px[i]-px[0]-acc;res.append(v)
  w.writerow([i,px[i],force[i],acc,v,g9[i],g16[i],t15[i],t10[i],g9[i]-g16[i],t15[i]-t10[i]])
pulse=list(csv.DictReader((p/'wall_gate0_pulse.csv').open()));assert [int(x['parity']) for x in pulse]==[0,1]
pulses=[{'parity':int(x['parity']),'injected':float(x['perturbed_slot'])-float(x['base_slot']),'target':float(x['perturbed_target'])-float(x['base_target']),'ddf_before':float(x['perturbed_ddf_before'])-float(x['base_ddf_before']),'ddf_after':float(x['perturbed_ddf_after'])-float(x['base_ddf_after'])} for x in pulse]
slope=math.fsum((i-1000)*y for i,y in enumerate(rho))/math.fsum((i-1000)**2 for i in range(2001))
out={'fixture':'try9_fix2','rows':len(rows),'mass0':mass[0],'ddf_max_rel':max(abs(v-mass[0])/abs(mass[0]) for v in mass),'ddf_pass':max(abs(v-mass[0])/abs(mass[0]) for v in mass)<=1e-6,'rho_initial':rho[0],'rho_final':rho[-1],'rho_min':min(rho),'rho_max':max(rho),'rho_slope_per_step':slope,'px0':px[0],'px_tol':1e-4*abs(px[0]),'max_abs_residual_step_1_20':max(abs(v) for v in res[1:21]),'residual_selected':{str(i):res[i] for i in (1,2,10,20,100,2000)},'first_step_link_differences':{'ground9':g9[1],'ground16':g16[1],'top15':t15[1],'top10':t10[1]},'pulses':pulses,'eligible_step1':int(rows[1]['eligible'])}
with (p/'metrics_try9.json').open('x') as f: json.dump(out,f,indent=2)
fig,ax=plt.subplots(figsize=(8,4));ax.plot(range(2001),res,lw=1);ax.axhline(out['px_tol'],color='red',ls='--');ax.axhline(-out['px_tol'],color='red',ls='--');ax.set(xlabel='step',ylabel='Delta px - sum ground force',title='Fixture A: ground-only px residual (not full wall ledger)');fig.tight_layout();fig.savefig(p/'residual_2000.png',dpi=150);plt.close(fig)
print(json.dumps(out,indent=2));print('sha256',hashlib.sha256((p/'wall_gate0.csv').read_bytes()).hexdigest())
