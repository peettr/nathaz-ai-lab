#!/usr/bin/env python3.10
"""T7 frozen group-total gate and supplementary point metrics."""
import pathlib,json,csv,hashlib,math
R=pathlib.Path(__file__).resolve().parent;E=R/'evidence';L=R.parent
BASE={'101':L/'R21.4a_T5_caseE_WM_retry1/evidence','102':L/'R21.4a_T5_caseE_WM_retry2/evidence'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(folder,label):
 p=folder/(label+'_points80.json');h=sha(p);assert (folder/(p.name+'.sha256')).read_text().strip()==h
 d=json.loads(p.read_text());assert d['label']==label and d['uref']==3.9286416
 rr={int(x['id']):x for x in d['rows']};assert len(rr)==80 and set(rr)==set(range(1,81))
 assert all(math.isfinite(x['Su_ratio']) and x['obs']>0 for x in rr.values())
 return rr,h
def metrics(rows,ids):
 a=[rows[i] for i in ids];return {'ratio_total':sum(x['Su_ratio'] for x in a)/sum(x['obs'] for x in a),'FAC2':sum(.5<=x['Su_ratio']/x['obs']<=2 for x in a)/len(a),'n':len(a)}
width={int(x['id']):x for x in csv.DictReader((R/'widths.csv').open())};assert len(width)==80
wide=[i for i in range(1,81) if width[i]['width_min_m'] and float(width[i]['width_min_m'])>=15.];other=[i for i in range(1,81) if i not in wide];assert len(wide)==64 and len(other)==16
result={'definition':{'delta_r_wide':'sum(T7 Su/Uref)/sum(obs) - sum(T5 off Su/Uref)/sum(obs), width>=15m N=64','wide_delta_point_ratio':'mean((T7-T5 off) Su/Uref/obs), width>=15m','delta_mae':'MAE(T7)-MAE(T5 off), all 80'},'seeds':{}}
for seed in ('101','102'):
 label=f'E_s{seed}_off';a,ah=load(BASE[seed],label);b,bh=load(E,label)
 assert all(a[i]['obs']==b[i]['obs'] and a[i]['xyz_m']==b[i]['xyz_m'] for i in a)
 m0=sum(abs(a[i]['Su_ratio']-a[i]['obs']) for i in a)/80;m1=sum(abs(b[i]['Su_ratio']-b[i]['obs']) for i in b)/80
 r0=metrics(a,wide);r1=metrics(b,wide)
 stability=E/(label+'_city_stability.csv');rows=list(csv.DictReader(stability.open()));assert rows
 result['seeds'][seed]={'T5_off_points80_sha256':ah,'T7_points80_sha256':bh,'T7_points80_path':str(E/(label+'_points80.json')),'T5_off_MAE':m0,'T7_MAE':m1,'delta_MAE':m1-m0,'T5_wide':r0,'T7_wide':r1,'delta_r_wide':r1['ratio_total']-r0['ratio_total'],'wide_delta_point_ratio':sum((b[i]['Su_ratio']-a[i]['Su_ratio'])/a[i]['obs'] for i in wide)/64,'T5_narrow_near16':metrics(a,other),'T7_narrow_near16':metrics(b,other),'T7_all80':metrics(b,range(1,81)),'city_stability_last':{k:rows[-1][k] for k in ('step','max_u_lattice','flux_west','flux_east','flux_south','flux_north','flux_top','flux_net_out')},'city_stability_path':str(stability)}
d=[v['delta_r_wide'] for v in result['seeds'].values()]
result['verdict']='有可分辨贡献' if all(x<=-.03 for x in d) else '未见贡献' if all(abs(x)<.03 for x in d) else '反向' if all(x>=.03 for x in d) else '不判'
p=R/'T7_verdict.json';assert not p.exists();p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
