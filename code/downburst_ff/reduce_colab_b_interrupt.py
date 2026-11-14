"""Reduce interrupted Colab B run; never upgrades partial data to six-seed conclusions."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
old=json.loads((P/'metrics_B_partial_20261014.json').read_text())
manifest=json.loads((P/'colab_manifest_1014.json').read_text())
new=[json.loads((P/f'colab_{g}_s112.json').read_text()) for g in ('G5','G6','G7','G8')]
assert old['completed']==26 and len(manifest)==144 and all(x['returncode']==0 for x in new)
key=lambda r:(r['case'],r['seed'],r['group'])
assert not set(map(key,old['metrics']))&set(map(key,new))
completed=old['metrics']+new
missing=[dict(case=m['case'],seed=m['seed'],group=m['group']) for m in manifest if key(m) not in set(map(key,completed))]
g0=next(x for x in old['metrics'] if key(x)==('I_near',112,'G0_50s'))['metrics']['tower_resultant_max_kNm']
g6=new[1]['metrics']['tower_resultant_max_kNm'];g7=new[2]['metrics']['tower_resultant_max_kNm']
red_g6=100*(g0-g6)/g0;red_g7=100*(g0-g7)/g0
assert red_g6>10 and red_g7<0
status=dict(status='STOPPED_IMPLEMENTATION_RED_FLAG; not six-seed result',expected=len(manifest),completed=len(completed),existing_p14=26,colab_new=4,validation_replay_not_double_counted=True,missing=missing,rows=completed,
  checks=dict(validation_seed112_G1_tower_difference_pct=0.0,case_I_seed112_G0_tower_kNm=g0,G6_tower_kNm=g6,G7_tower_kNm=g7,G6_reduction_pct=red_g6,G7_reduction_pct=red_g7,reason='G6 clearly beats matched-lead G7; stop as instructed; one seed only'),
  provenance=dict(colab_session='ideas-a3-b-colab-cpu-1014',colab_cpu_cores=2,software='OpenFAST 5.0.0; ROSCO 2.10.6 patched; local Linux binaries uploaded',input='Nguyen 2012 analytic plus modulated Kaimal/Veers approximated field, same seeds/code regenerated on Colab',preview='G5/G6 upstream filtered 0.10 Hz; G7/G8 rotor(t+Tlead(t)) filtered and buffered with same measured lead as G6/G5; implementation requires timing audit',pilot='exact match tower 84587.58301311133 kN m both Colab and 工作站',colab_run_note='stopped session immediately after seed112 comparison, no further batch'),gates={'stop_benefit':None,'pitch_benefit':None,'reason':'both require two paths and six seeds, and G6/G7 timing red flag'})
target=P/'metrics_B.json';assert not target.exists();target.write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n')
fig,axs=plt.subplots(3,1,figsize=(12,9),sharex=True)
for group,color in [('G6','tab:blue'),('G7','tab:orange')]:
 d=np.load(P/f'colab_{group}_s112.npz');t=d['Time']+220.5
 axs[0].plot(t,np.hypot(d['Wind1VelX'],d['Wind1VelY']),color=color,label=group,linewidth=.8)
 axs[1].plot(t,d['BldPitch1'],color=color,label=group,linewidth=.8)
 axs[2].plot(t,np.hypot(d['TwrBsMxt'],d['TwrBsMyt']),color=color,label=group,linewidth=.8)
for ax,ylabel in zip(axs,['hub horizontal wind [m/s]','collective pitch [deg]','tower-base resultant [kN m]']):ax.set_ylabel(ylabel);ax.grid(alpha=.2)
axs[0].legend();axs[-1].set_xlabel('Nguyen storm time [s]')
fig.suptitle('Seed 112, Case I: G6 vs G7 (timing red flag, not six-seed evidence)\nNguyen 2012 analytic + Kaimal/Veers approximation; OpenFAST 5.0.0 / patched ROSCO 2.10.6')
fig.tight_layout();fig.savefig(P/'colab_seed112_G6_G7_B.png',dpi=140);plt.close(fig)
print('old',len(old['metrics']),'new',len(new),'missing',len(missing),'G6 reduction',red_g6,'G7 reduction',red_g7)
