#!/usr/bin/env python3
"""T3 frozen metrics from host-verified thin fields; no solver on 工作站."""
import pathlib,hashlib,json,math,statistics
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path(__file__).resolve().parent
xs=[1.,2.,5.,10.,25.,50.,75.,100.,125.,150.,175.,200.,225.,252.1485175,275.,300.,325.,340.,400.,450.,500.,540.]
CASES=('dx1p0_s103','dx0p5_s103','dx1p0_s104','dx0p5_s104')
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def analyze(case):
 p=R/f'{case}_thin.npz';sha=(R/f'{case}_thin.sha256').read_text().strip();assert digest(p)==sha
 with np.load(p,allow_pickle=False) as data:
  u=data['u_avg'];fluid=data['fluid'];m=json.loads(str(data['metadata']))
 assert m['case']==case and u.shape[:3]==fluid.shape and u.shape[3]==3
 man=json.loads((R/'stage_fixed/stage_manifest.json').read_text())
 assert m['config_sha256']==man['cases'][case]['conf_sha256']
 dx=m['dx'];ox,oy,oz=m['origin'];ki=m['k_start'];ys=m['y_indices'];nx=m['dims'][0];wall_index=m['wall_index_from_origin']
 # First-fluid label is wall_index+1 (verified against archived native flags).
 center=np.flatnonzero((oy+np.asarray(ys)*dx>=40-1e-6)&(oy+np.asarray(ys)*dx<=60+1e-6))
 assert len(center)>=20
 first_fluid_k=next(k for k in range(ki,ki+fluid.shape[0]) if np.all(fluid[k-ki,center,round(252/dx)]>.5))
 wall=oz+(first_fluid_k-.5)*dx
 assert len(ys)==fluid.shape[1] and nx==fluid.shape[2]
 def sample(x,h,band='center'):
  i=round((x-ox)/dx);zf=(wall+h-oz)/dx;k=math.floor(zf);a=zf-k;ka=k-ki
  rec={'x_m':x,'actual_x_m':ox+i*dx,'height_agl_m':h,'k_support':[k,k+1],'fluid_support':[],'invalid':[],'G_mps':None}
  if not (0<=i<nx and 0<=ka<fluid.shape[0]-1):
   rec['invalid'].append({'x_m':x,'k':[k,k+1],'reason':'outside archived support'});return rec
  ff0=fluid[ka,:,i];ff1=fluid[ka+1,:,i]
  selected=np.flatnonzero((oy+np.asarray(ys)*dx>=40-1e-6)&(oy+np.asarray(ys)*dx<=60+1e-6)) if band=='center' else np.array([int(np.argmin(abs(oy+np.asarray(ys)*dx-float(band))))])
  rec['fluid_support']=[{'y_m':float(oy+j*dx),'k0':float(v0),'k1':float(v1)} for j,v0,v1 in zip(np.asarray(ys)[selected],ff0[selected],ff1[selected])]
  for j,v0,v1 in zip(np.asarray(ys)[selected],ff0[selected],ff1[selected]):
   if not (np.isfinite(v0) and np.isfinite(v1) and v0>.5 and v1>.5):rec['invalid'].append({'x_index':i,'x_m':ox+i*dx,'y_index':j,'y_m':oy+j*dx,'k':[k,k+1],'fluid':[float(v0),float(v1)],'reason':'nonfluid support'})
  if rec['invalid']:return rec
  vec=(1-a)*u[ka,selected,i,:].astype('f8')+a*u[ka+1,selected,i,:].astype('f8')
  speeds=np.linalg.norm(vec,axis=1)
  if not np.all(np.isfinite(speeds)):
   rec['invalid'].append({'x_m':x,'k':[k,k+1],'reason':'nonfinite velocity'});return rec
  rec['G_mps']=float(speeds.mean());return rec
 # Inspect the entire archived streamwise axis: first full-fluid 2-m support after x=0.
 entry_candidates=[sample(ox+i*dx,2.) for i in range(1,nx)]
 inlet=next((r for r in entry_candidates if r['G_mps'] is not None),None)
 first_dx=entry_candidates[0]
 curve=[sample(dx if x is None else x,2.) for x in xs]
 vertical=[sample(252.1485175,h*.5) for h in range(41)]
 result={'case':case,'thin_npz':str(p),'thin_sha256':sha,'metadata':m,'wall_m':wall,'inlet_x_m':5.,'inlet_G2_at_x5_mps':sample(5.,2.)['G_mps'],'first_full_fluid_x_m':inlet['actual_x_m'] if inlet else None,'inlet_G2_mps':inlet['G_mps'] if inlet else None,'first_x_dx_diagnostic':first_dx,'G_curve':curve,'vertical_at_xc':vertical,'xc_G2_mps':curve[13]['G_mps'],'invalid_points':[{'x_m':v['x_m'],'height_agl_m':v['height_agl_m'],'reasons':v['invalid']} for v in curve+vertical if v['invalid']]}
 result['first_fluid_k_at_xc']=first_fluid_k
 for y in (5.,95.):
  result[f'side_y{int(y)}_at_xc']=sample(252.1485175,2.,y)
  result[f'side_y{int(y)}_G_over_center']=result[f'side_y{int(y)}_at_xc']['G_mps']/result['xc_G2_mps'] if result[f'side_y{int(y)}_at_xc']['G_mps'] is not None and result['xc_G2_mps'] else None
 out=R/f'{case}_metrics_wall_corrected.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v: v.item() if isinstance(v,np.generic) else (_ for _ in ()).throw(TypeError(type(v).__name__)))+'\n');return result
if __name__=='__main__':
 cases={k:analyze(k) for k in CASES}
 Qs={str(s):cases[f'dx0p5_s{s}']['xc_G2_mps']/cases[f'dx1p0_s{s}']['xc_G2_mps'] if all(cases[f'dx{d}_s{s}']['xc_G2_mps'] is not None for d in ('0p5','1p0')) else None for s in (103,104)}
 inlet={str(s):abs(cases[f'dx0p5_s{s}']['inlet_G2_at_x5_mps']/cases[f'dx1p0_s{s}']['inlet_G2_at_x5_mps']-1) if all(cases[f'dx{d}_s{s}']['inlet_G2_at_x5_mps'] is not None for d in ('0p5','1p0')) else None for s in (103,104)}
 vals=[cases[f'dx{d}_s{s}']['xc_G2_mps'] for d in ('0p5','1p0') for s in (103,104)]
 Q=statistics.mean(vals[:2])/statistics.mean(vals[2:]) if all(v is not None for v in vals) else None
 if any(v is None for v in inlet.values()) or Q is None: verdict='无有效完整支撑，不应用冻结科学判据'
 elif max(inlet.values())>.02:verdict='入口映射不一致，不判'
 elif abs(Qs['103']-Qs['104'])>.02:verdict='不判：种子差 >0.02；本轮不判，交 Lead 决策'
 elif Q>=1.06:verdict='相容：仅本配置下地面侧是相容解释，不排除建筑贡献'
 elif Q<=1.03:verdict='不足：本配置下空场近地差异不足；转查建筑相关来源'
 else:verdict='不判：1.03 < Q < 1.06；本轮不判，交 Lead 决策'
 summary={'Q':Q,'Q_seed':Qs,'seed_difference':abs(Qs['103']-Qs['104']) if all(v is not None for v in Qs.values()) else None,'inlet_relative_difference_each_seed':inlet,'inlet_x_m':5.,'side_G_over_center_at_xc':{k:{'y5':v['side_y5_G_over_center'],'y95':v['side_y95_G_over_center']} for k,v in cases.items()},'verdict':verdict,'invalid_counts':{k:len(v['invalid_points']) for k,v in cases.items()}}
 (R/'RESULT_T3_t3b_wall_corrected.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 fig,ax=plt.subplots(figsize=(9,5))
 for k,m in cases.items():ax.plot([r['actual_x_m'] for r in m['G_curve']],[float('nan') if r['G_mps'] is None else r['G_mps'] for r in m['G_curve']],'.-',label=k)
 ax.axvline(252.1485175,ls=':',color='k');ax.set(xlabel='x (m)',ylabel='G(x), mean_y |time-mean u| (m/s)',title='Empty-ground true 2 m AGL (invalid points omitted)');ax.legend();fig.tight_layout();fig.savefig(R/'G_along_x_t3b_wall_corrected.png',dpi=170);plt.close(fig)
 fig,ax=plt.subplots(figsize=(7,5))
 for k,m in cases.items():ax.plot([float('nan') if r['G_mps'] is None else r['G_mps'] for r in m['vertical_at_xc']],[r['height_agl_m'] for r in m['vertical_at_xc']],'.-',label=k)
 ax.set(xlabel='G (m/s)',ylabel='Height above numerical wall (m)',ylim=(0,20),title='x_c vertical (invalid points omitted)');ax.legend();fig.tight_layout();fig.savefig(R/'xc_vertical_0_20m_t3b_wall_corrected.png',dpi=170);plt.close(fig)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
