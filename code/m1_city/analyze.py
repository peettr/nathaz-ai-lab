from pathlib import Path
import json,csv,zipfile,statistics,io,math
R=Path(__file__).resolve().parent
base=json.loads(Path('./24_Urban_Wind_LBM/06_Logs/wp1_nearwall/city_stab/stage6noT_offset_samples_a_r10.json').read_text())
ref={r['id']:r for r in base['rows']};assert len(ref)==80
out={};points=[]
for tag in ('H1','H2'):
 p=R/(tag+'_evidence.zip')
 if not p.exists():continue
 with zipfile.ZipFile(p) as z:
  names=z.namelist();entry=lambda suffix:next((x for x in names if x.endswith(suffix)),None)
  trace=list(csv.DictReader(io.StringIO(z.read(entry('city_stability.csv')).decode())));f0=list(csv.DictReader(io.StringIO(z.read(entry('f0_minimum.csv')).decode())))
  t={'rows':len(trace),'last_step':int(trace[-1]['step']),'max_speed':max(float(v['max_u_lattice']) for v in trace),'rho_after3000':[min(float(v['min_rho']) for v in trace if int(v['step'])>=3000),max(float(v['max_rho']) for v in trace if int(v['step'])>=3000)],'nonfinite':sum(bool(v['first_nonfinite_xyz_component']) for v in trace),'f0_rows':len(f0),'min_f0':min(float(v['min_f0']) for v in f0),'f0_nonfinite':sum(not math.isfinite(float(v['min_f0'])) for v in f0),'exit':z.read('solver.exit').decode(),'reason':z.read('stop_reason.txt').decode()}
  (R/(tag+'_trace.csv')).write_bytes(z.read(entry('city_stability.csv')))
  (R/(tag+'_f0.csv')).write_bytes(z.read(entry('f0_minimum.csv')))
  out[tag]={'trace':t}
  if not entry('offset_samples_a_r10.json'):continue
  d=json.loads(z.read(entry('offset_samples_a_r10.json')));(R/(tag+'_offset_samples_a_r10.json')).write_text(json.dumps(d,ensure_ascii=False))
  q={r['id']:r for r in d['rows']};assert set(q)==set(ref)
  for group,ids in [('all',set(ref)),('wall',{50,51,52,54}),('wall_without_52',{50,51,54}),('point52',{52}),('open',{23,25,37,17})]:
   out[tag][group]={}
   for kind in ('sim_ratio','exp_ratio'):
    s=[q[i]['sample']['plus_dx'][kind] for i in sorted(ids)];y=[q[i]['after'] for i in sorted(ids)]
    out[tag][group][kind]={'MAE':statistics.mean(abs(x-z) for x,z in zip(s,y)),'r':statistics.correlation(s,y) if len(ids)>1 else None,'mean_ratio':statistics.mean(s)/statistics.mean(y)}
  out[tag]['upstream']={str(x['x_local_m']):x['fraction_input'] for x in d['upstream'] if x['z_m']==2.0 and x['x_local_m'] in (25.,42.)}
  changes=[]
  for i in sorted(ref):
   x=q[i]['sample']['plus_dx']['exp_ratio'];b=ref[i]['sample']['plus_dx']['exp_ratio'];y=q[i]['after']
   v={'tag':tag,'id':i,'obs':y,'S':q[i]['sample']['plus_dx']['sim_ratio'],'Sstar':x,'baseline_Sstar':b,'delta_abs_error':abs(x-y)-abs(b-y)}
   points.append(v);changes.append(v)
  out[tag]['change_counts']={'improved':sum(v['delta_abs_error']<0 for v in changes),'worse':sum(v['delta_abs_error']>0 for v in changes),'same':sum(v['delta_abs_error']==0 for v in changes)}
(R/'metrics.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
if points:
 with (R/'point_changes.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(points[0]));w.writeheader();w.writerows(points)
print(json.dumps(out,indent=2,ensure_ascii=False))
