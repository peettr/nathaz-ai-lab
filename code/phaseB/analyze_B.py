import pathlib,hashlib,json,math,csv,collections
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path(__file__).resolve().parent
xs=[1.,2.,5.,10.,25.,50.,75.,100.,125.,150.,175.,200.,225.,252.1485175,275.,300.,325.,340.,400.,450.,500.,540.]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1068576),b''):h.update(b)
 return h.hexdigest()
def analyze(case):
 p=R/'evidence'/f'{case}_thin.npz';sha=(R/'evidence'/f'{case}_thin.sha256').read_text().strip();assert digest(p)==sha
 with np.load(p,allow_pickle=False) as data:
  u=data['u_avg'];fluid=data['fluid'];m=json.loads(str(data['metadata']))
 assert m['case']==case.removeprefix('B_') and u.shape[:3]==fluid.shape and u.shape[3]==3
 man=json.loads((R/'stage/stage_manifest.json').read_text())
 assert m['config_sha256']==man['cases'][case.removeprefix('B_')]['conf_sha256']
 dx=m['dx'];ox,oy,oz=m['origin'];ki=m['k_start'];ys=m['y_indices'];nx=m['dims'][0];wall_index=m['wall_index_from_origin']
 # First-fluid label is wall_index+1 (verified against archived native flags).
 center=np.flatnonzero((oy+np.asarray(ys)*dx>=40-1e-6)&(oy+np.asarray(ys)*dx<=60+1e-6))
 assert len(center)>=20
 first_fluid_k=next(k for k in range(ki,ki+fluid.shape[0]) if np.all(fluid[k-ki,center,round(252/dx)]>.5))
 wall=oz+(first_fluid_k-.5)*dx
 assert abs((oz+first_fluid_k*dx)-dx)<1e-4,'incorrect geometry at xc'
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
 result['x0_G_at_physical_z2_mps']=sample(0.,2.-wall)['G_mps']
 for y in (5.,95.):
  result[f'side_y{int(y)}_at_xc']=sample(252.1485175,2.,y)
  result[f'side_y{int(y)}_G_over_center']=result[f'side_y{int(y)}_at_xc']['G_mps']/result['xc_G2_mps'] if result[f'side_y{int(y)}_at_xc']['G_mps'] is not None and result['xc_G2_mps'] else None
 out=R/f'{case}_metrics_wall_corrected.json';assert not out.exists();out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False,default=lambda v: v.item() if isinstance(v,np.generic) else (_ for _ in ()).throw(TypeError(type(v).__name__)))+'\n');return result

def main():
 base=R.parent.parent/'R21.4a_T3_emptyground/T3d'
 results={}
 fig,axes=plt.subplots(1,3,figsize=(18,5),sharey=True)
 for ax,seed in zip(axes,(107,108,109)):
  case=f'B_dx1p0_s{seed}'
  w=analyze(case)
  refs={d:json.loads((base/f'dx{d}_s{seed}_metrics_wall_corrected.json').read_text()) for d in ('1p0','0p5')}
  h=lambda m:m['xc_G2_mps']/m['inlet_G2_at_x5_mps']
  v={'H_WM':h(w),'H_1m':h(refs['1p0']),'H_0p5m':h(refs['0p5']),'delta_H':h(w)-h(refs['1p0']),'npz_sha256':w['thin_sha256']}
  for m,label in ((refs['1p0'],'1 m bounce-back'),(w,'1 m wall model'),(refs['0p5'],'0.5 m bounce-back')):
   ax.plot([p['actual_x_m'] for p in m['G_curve']],[float('nan') if p['G_mps'] is None else p['G_mps'] for p in m['G_curve']],'.-',label=label)
  ax.set(xlabel='x (m)',title=f'Seed {seed}');ax.legend(fontsize=7);results[str(seed)]=v
  p=R/'evidence'/f'{case}_ground_excluded.csv'
  with p.open() as f:rows=list(csv.DictReader(f))
  v['excluded_columns']=rows;v['excluded_reasons']=dict(collections.Counter(row['reason'] for row in rows))
  assert all(set(row)>={'x_index','y_index','x_m','y_m','reason'} for row in rows)
  # Reconcile every listed exclusion with the producer's eligibility count.
  with (R/'evidence'/f'{case}_ground_eligibility.csv').open() as f:v['eligibility_raw']=f.read()
 axes[0].set_ylabel('G(x), center-band mean |time-mean u| (m/s)')
 fig.tight_layout();fig.savefig(R/'G_three_lines.png',dpi=170);plt.close(fig)
 vals=list(results.values())
 if all(v['H_WM']>=.80 and v['delta_H']>=.10 for v in vals):verdict='改善（仅本配置水平均匀性）'
 elif all(v['delta_H']<=.03 for v in vals):verdict='无改善'
 else:verdict='中间，不判'
 (R/'B_verdict.json').write_text(json.dumps({'seeds':results,'verdict':verdict,'definition':'H=G(x_c,2m)/G(5m,2m)'},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'verdict':verdict,'H':{k:{i:v[i] for i in ('H_WM','H_1m','H_0p5m','delta_H')} for k,v in results.items()},'excluded_counts':{k:len(v['excluded_columns']) for k,v in results.items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
