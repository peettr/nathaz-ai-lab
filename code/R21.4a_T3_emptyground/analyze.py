#!/usr/bin/env python3
"""Read-only four-result verification, preregistered T3 judgment and figures."""
import json,zipfile,hashlib,pathlib,statistics,math
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path(__file__).resolve().parent
cases={}
for dx in ('1p0','0p5'):
 for seed in (101,102):
  key=f'dx{dx}_s{seed}';p=R/(key+'.zip')
  assert p.is_file(),key
  with zipfile.ZipFile(p) as z:
   assert z.testzip() is None
   manifest=json.loads(z.read(key+'_manifest.json'))
   for n,record in manifest.items():assert len(z.read(n))==record['size'] and hashlib.sha256(z.read(n)).hexdigest()==record['sha256'],(key,n)
   m=json.loads(z.read(key+'_metrics.json'));e=json.loads(z.read(key+'_exit.json'))
   assert e['solver_exit']==0 and m['case']==key
   assert m['config_sha256']==json.loads((R/'stage_manifest.json').read_text())['cases'][key]['conf_sha256']
   cases[key]=m
Q_seed={s:cases[f'dx0p5_s{s}']['xc_G2_mps']/cases[f'dx1p0_s{s}']['xc_G2_mps'] for s in (101,102)}
Q=statistics.mean(cases[f'dx0p5_s{s}']['xc_G2_mps'] for s in (101,102))/statistics.mean(cases[f'dx1p0_s{s}']['xc_G2_mps'] for s in (101,102))
inlet={s:abs(cases[f'dx0p5_s{s}']['inlet_G2_mps']/cases[f'dx1p0_s{s}']['inlet_G2_mps']-1) for s in (101,102)}
# Predeclared center band may not be side-independent: assess profile at three x stations.
side=[]
for key,m in cases.items():
 for section in m['side_profiles']:
  cols={r['y_m']:r['U2_mps'] for r in section['columns']};mid=cols[15]
  side.append({'case':key,'x_m':section['x_m'],'relative_edge_center_at_y10':abs(cols[10]/mid-1),'relative_edge_center_at_y20':abs(cols[20]/mid-1)})
side_ok=all(max(s['relative_edge_center_at_y10'],s['relative_edge_center_at_y20'])<=.02 for s in side)
if max(inlet.values())>.02:verdict='入口映射不一致，不判'
elif abs(Q_seed[101]-Q_seed[102])>.02:verdict='不判：种子差 >0.02；按冻结判据加种子 103 再判'
elif Q>=1.06:verdict='相容：本配置下无建筑时 0.5/1 m 近地 2 m 风速比与 Case E 宽组差异（约 1.086）量级一致；地面一侧近地分辨是宽组差异的相容解释（不排除建筑侧贡献）'
elif Q<=1.03:verdict='不足：本配置下无建筑时近地差异不足以解释宽组差异；转查与建筑相关的来源'
else:verdict='不判：1.03 < Q < 1.06；按冻结判据加种子 103 再判'
if not side_ok:verdict+='；警示：中心带侧边界剖面差 >2%，不能将本窄盒 Q 单独归因为近壁分辨'
result={'Q':Q,'Q_seed':Q_seed,'seed_difference':abs(Q_seed[101]-Q_seed[102]),'inlet_relative_difference_each_seed':inlet,'side_profiles':side,'side_ok_2pct_diagnostic':side_ok,'verdict':verdict,'zip_sha256':{k:hashlib.sha256((R/(k+'.zip')).read_bytes()).hexdigest() for k in cases}}
with (R/'RESULT_T3.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
fig,ax=plt.subplots(figsize=(9,5))
for k,m in cases.items():ax.plot([r['x_m'] for r in m['G_curve']],[r['G_mps'] for r in m['G_curve']],marker='.',label=k)
ax.axvline(next(iter(cases.values()))['x_c_m'],ls=':',c='k',label='x_c');ax.set(xlabel='x (m)',ylabel='G(x) = mean_y |time-mean velocity| (m/s)',title='Empty-ground true 2 m AGL');ax.legend();fig.tight_layout();fig.savefig(R/'G_along_x.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,5))
for k,m in cases.items():
 v=m['vertical_at_xc'][1:];ax.plot([r['G_mps'] for r in v],[r['height_agl_m'] for r in v],marker='.',label=k)
ax.set(xlabel='Mean speed magnitude (m/s)',ylabel='Height above numerical wall (m)',ylim=(0,20),title='Vertical profile at x_c');ax.legend();fig.tight_layout();fig.savefig(R/'xc_vertical_0_20m.png',dpi=170);plt.close(fig)
print(json.dumps(result,ensure_ascii=False,indent=2))
