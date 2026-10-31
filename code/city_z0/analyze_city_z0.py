from pathlib import Path
import json,csv,statistics
R=Path(__file__).resolve().parent
B=json.loads((R.parents[1]/'wp1b_ibm/inflow_ti/B2_offset_samples.json').read_text())
D=json.loads((R/'Gz2_offset_samples_a_r10.json').read_text())
ref={x['id']:x for x in B['rows']}; q={x['id']:x for x in D['rows']}
assert set(ref)==set(q)==set(range(1,81))
fast={7,8,17,20,23,25,26,27,45,68};wall={50,51,52,54};open_ids={23,25,37,17}
slow={i for i in ref if ref[i]['sample']['plus_dx']['sim_ratio']/ref[i]['after']<.8}
def stats(d,ids):
 a=[d[i]['sample']['plus_dx'] for i in sorted(ids)];y=[d[i]['after'] for i in sorted(ids)]
 return {p:{'MAE':statistics.mean(abs(t[p]-o) for t,o in zip(a,y)), 'r':statistics.correlation([t[p] for t in a],y),'mean_ratio':statistics.mean(t[p] for t in a)/statistics.mean(y)} for p in ('sim_ratio','exp_ratio')}
change=[]
for i in sorted(ref):
 y=q[i]['after'];v=q[i]['sample']['plus_dx']['exp_ratio'];b=ref[i]['sample']['plus_dx']['exp_ratio']
 change.append({'id':i,'W':y,'B2_Sstar':b,'Gz2_Sstar':v,'improve':abs(v-y)<abs(b-y),'worse':abs(v-y)>abs(b-y),'delta_error':abs(v-y)-abs(b-y)})
with (R/'point_changes.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(change[0]));w.writeheader();w.writerows(change)
trace=list(csv.DictReader((R/'Gz2_trace.csv').open()));assert trace and int(trace[-1]['step'])==31000
metrics={'groups':{name:{'Gz2':stats(q,ids),'B2':stats(ref,ids)} for name,ids in [('all',set(ref)),('wall',wall),('open',open_ids),('fast10',fast),('slow_B2_S_over_W_below_0.8',slow)]},'changes':{'improved':sum(x['improve'] for x in change),'worse':sum(x['worse'] for x in change),'same':sum(not x['improve'] and not x['worse'] for x in change)},'upwind':{'Gz2':{str(t['x_local_m']):t['fraction_input'] for t in D['upstream'] if t['z_m']==2. and t['x_local_m'] in (25.,42.)},'B2':{str(t['x_local_m']):t['fraction_input'] for t in B['upstream'] if t['z_m']==2. and t['x_local_m'] in (25.,42.)}},'trace':{'rows':len(trace),'end':int(trace[-1]['step']),'max_u':max(float(t['max_u_lattice']) for t in trace),'rho_post3000':[min(float(t['min_rho']) for t in trace if int(t['step'])>=3000),max(float(t['max_rho']) for t in trace if int(t['step'])>=3000)],'nonfinite':sum(bool(t['first_nonfinite_xyz_component']) for t in trace)},'wall_points':{str(i):{'obs':q[i]['after'],'B2':ref[i]['sample']['plus_dx']['exp_ratio'],'Gz2':q[i]['sample']['plus_dx']['exp_ratio']} for i in sorted(wall)}}
(R/'metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+'\n');print(json.dumps(metrics,indent=2))
