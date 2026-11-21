#!/usr/bin/env python3.10
"""Read-only T9a post-processing; frozen definitions in 04_Decisions/R21.4a_T9*."""
import csv, hashlib, itertools, json, math
from pathlib import Path
import numpy as np
R=Path('./24_Urban_Wind_LBM/06_Logs')
O=R/'R21.4a_T9a_narrow_split'
U=3.9286416
T=R/'tacc_feasibility'
SRC=T/'T2c_post/out_3694005/points_all_heights.json'
WIDTH=T/'T2c_post/widths.csv'
THIN=R/'R21.4a_T5_caseE_WM_retry2/evidence/E_s102_off_thin.npz'
NEAR=(50,51,52,54,55,74)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def load_points(p,kind):
 d=json.loads(p.read_text()); rows=d['rows'] if kind=='t5' else d['heights']['2.0']['points']
 assert len(rows)==80 and len({int(q['id']) for q in rows})==80
 return {int(q['id']): {'Su':q['Su'] if kind=='t5' else q['new']['Su'], 'obs':q['obs']} for q in rows}
def ratio(rows, ids):
 return sum(rows[i]['Su']/U for i in ids)/sum(rows[i]['obs'] for i in ids)
def val(rows,ids):
 assert ids and all(rows[i]['obs']>0 and math.isfinite(rows[i]['baseline_1m']['Su']) and math.isfinite(rows[i]['fine']['primary']['Su']) for i in ids)
 return {'count':len(ids),'r_1m':ratio({i:{'Su':rows[i]['baseline_1m']['Su'],'obs':rows[i]['obs']} for i in ids},ids), 'r_0p5m':ratio({i:{'Su':rows[i]['fine']['primary']['Su'],'obs':rows[i]['obs']} for i in ids},ids)}
def sample(thin,xyz,shift):
 x,y,z=xyz;x+=shift[0];y+=shift[1]
 q=(x,y,z+20); ijk=tuple(math.floor(a) for a in q);w=tuple(a-i for a,i in zip(q,ijk));i,j,k=ijk
 assert 0<=i<499 and 0<=j<499 and 20<=k<46
 su=solid=0.;corners=0
 for dz,dy,dx in itertools.product((0,1),repeat=3):
  weight=(w[0] if dx else 1-w[0])*(w[1] if dy else 1-w[1])*(w[2] if dz else 1-w[2]); idx=(k+dz-20,j+dy,i+dx)
  fluid=thin['fluid'][idx]>.5
  su+=weight*float(thin['speed_mean'][idx]);solid+=weight*(not fluid);corners+=int(fluid)
 return {'Su_over_Uref':su/U,'fluid_corners':corners,'solid_weight':solid}
def nearest_solid(thin,xyz):
 # Native solid nodes on the two vertical interpolation levels; nearest Euclidean node distance in 1m cells.
 x,y,z=xyz;i,j,k=(math.floor(x),math.floor(y),math.floor(z+20));radius=40
 ii=np.arange(max(0,i-radius),min(499,i+radius)+1);jj=np.arange(max(0,j-radius),min(499,j+radius)+1)
 kk=[k-20,k+1-20];a=thin['fluid'][kk][:,jj[:,None],ii[None,:]]<=.5
 where=np.where(a)
 if len(where[0])==0:return {'distance_cells':None,'definition':'nearest solid native node at either vertical interpolation layer, search radius 40 cells'}
 dist=np.sqrt((ii[where[2]]-x)**2+(jj[where[1]]-y)**2+(np.asarray(kk)[where[0]]+20-(z+20))**2)
 n=int(np.argmin(dist))
 return {'distance_cells':float(dist[n]),'native_ijk':[int(ii[where[2][n]]),int(jj[where[1][n]]),int(np.asarray(kk)[where[0][n]]+20)],'definition':'nearest solid native node at either vertical interpolation layer, search radius 40 cells; not surface distance'}
def main():
 assert O.is_dir() and not (O/'T9a_result.json').exists()
 widths={int(q['id']):q for q in csv.DictReader(WIDTH.open())};assert set(widths)==set(range(1,81))
 all_rows=json.loads(SRC.read_text());p={int(q['id']):q for q in all_rows if q['h_wall_m']==2.0};assert set(p)==set(widths)
 n=sorted(i for i in p if float(widths[i]['width_min_m'])<15);assert len(n)==16
 close=[i for i in n if float(widths[i]['wall_m'])<1.];far=[i for i in n if i not in close]
 groups={name:val(p,ids) for name,ids in [('N',n),('N_close',close),('N_far',far)]}
 for v in groups.values():v['delta_r']=v['r_0p5m']-v['r_1m']
 delta=lambda ids:sum((p[i]['fine']['primary']['Su']-p[i]['baseline_1m']['Su'])/U for i in ids)
 contribution=delta(close)/delta(n)
 files={'B2u_s100':(SRC,'t2c'),'T2d_s101':(T/'T2d_a/result_3694067.json','t2d'),'T2d_s102':(T/'T2d_a3/result_3701540.json','t2d'),'T2d_s103':(T/'T2d_a3/result_3701541.json','t2d'),'T5_s101_off':(R/'R21.4a_T5_caseE_WM_retry2/evidence/E_s101_off_points80.json','t5'),'T5_s102_off':(R/'R21.4a_T5_caseE_WM_retry2/evidence/E_s102_off_points80.json','t5')}
 seed={};provenance=[]
 for name,(path,kind) in files.items():
  assert path.is_file(); q={i:{'Su':p[i]['baseline_1m']['Su'],'obs':p[i]['obs']} for i in n} if kind=='t2c' else load_points(path,kind)
  assert all(math.isclose(q[i]['obs'],p[i]['obs'],abs_tol=1e-10) for i in n)
  seed[name]=ratio(q,n);provenance.append({'label':name,'path':str(path),'sha256':sha(path),'r_N':seed[name]})
 R_seed=max(seed.values())-min(seed.values());dr=groups['N_far']['delta_r']
 # Frozen table order: check first condition before second, preserving overlap visibly if any.
 if dr>=.10 and dr>=3*R_seed:verdict='分辨率效应为主'
 elif dr<.05 or contribution>=2/3:verdict='取样配准为主'
 else:verdict='中间'
 with np.load(THIN) as f:
  thin={k:f[k] for k in ('fluid','speed_mean')};meta=json.loads(str(f['metadata']))
 assert meta['k_start']==20 and meta['origin']==[0.,0.,-20.]
 points=[];shift=[]
 for i in n:
  q=p[i];a=q['baseline_1m'];b=q['fine']['primary'];xyz=a['xyz_m'];s=sample(thin,xyz,(0,0))
  # T5 s102 off is a different seed from T2c B2u; comparison is only to its own points80 below.
  points.append({'id':i,'wall_m':float(widths[i]['wall_m']),'width_min_m':float(widths[i]['width_min_m']),'obs':q['obs'],'Su_over_Uref_1m':a['Su']/U,'Su_over_Uref_0p5m':b['Su']/U,'fluid_corners_1m':a['fluid_corners'],'solid_weight_1m':a['solid_weight'],'fluid_corners_0p5m':b['fluid_corners'],'solid_weight_0p5m':b['solid_weight'],'nearest_solid_1m_T5_s102':nearest_solid(thin,xyz),'T5_s102_center_check':s,'exclude_if_mixed':a['fluid_corners']<8 or b['fluid_corners']<8})
  shift.append({'id':i,'wall_m':float(widths[i]['wall_m']),'center':s,**{f'{axis}{sign:+g}m':sample(thin,xyz,(sign,0) if axis=='x' else (0,sign)) for axis in ('x','y') for sign in (-.5,.5)}})
 remaining=[i for i in n if not next(row for row in points if row['id']==i)['exclude_if_mixed']]
 filtered={name:val(p,[i for i in ids if i in remaining]) for name,ids in [('N',n),('N_close',close),('N_far',far)] if any(i in remaining for i in ids)}
 for v in filtered.values():v['delta_r']=v['r_0p5m']-v['r_1m']
 filt_contrib=delta([i for i in close if i in remaining])/delta(remaining) if delta(remaining) else None
 near=[]
 for seednum in (101,102):
  on_path=(R/('R21.4a_T5_caseE_WM_retry1' if seednum==101 else 'R21.4a_T5_caseE_WM')/'evidence'/f'E_s{seednum}_on_points80.json')
  if not on_path.exists():
   on_path=R/'R21.4a_T5_caseE_WM_retry1/evidence'/f'E_s{seednum}_on_points80.json'
  on=load_points(on_path,'t5');off=load_points(files[f'T5_s{seednum}_off'][0],'t5')
  for i in NEAR:
   near.append({'seed':seednum,'id':i,'obs':p[i]['obs'],'one_m_off':off[i]['Su']/U,'one_m_T5_on':on[i]['Su']/U,'half_m_T2c_primary':p[i]['fine']['primary']['Su']/U,'wall_m':float(widths[i]['wall_m'])})
 result={'definition':'r_G=sum(Su/Uref)/sum(obs); delta_r=r_0p5m-r_1m; N width_min_m<15; close wall_m<1; Uref=3.9286416','groups':groups,'N_ids':n,'N_close_ids':close,'N_far_ids':far,'N_close_contribution':contribution,'R_seed':R_seed,'seed_r_N':seed,'seed_files':provenance,'verdict':verdict,'verdict_tests':{'far_ge_0p10':dr>=.1,'far_ge_3Rseed':dr>=3*R_seed,'far_lt_0p05':dr<.05,'close_ge_2thirds':contribution>=2/3},'filtered_report_only':{'excluded_ids':[i for i in n if i not in remaining],'groups':filtered,'N_close_contribution':filt_contrib,'verdict_unchanged':verdict},'offset_note':'T5 s102 off thin at z=2.5 m; x/y offsets independently ±0.5 m from T5 primary coordinates; same trilinear interpolation including solid nodes; not the T2c B2u seed','source_sha256':{'T2c_points':sha(SRC),'widths':sha(WIDTH),'thin':sha(THIN)}}
 (O/'T9a_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 (O/'narrow16.json').write_text(json.dumps(points,ensure_ascii=False,indent=2)+'\n')
 (O/'offsets.json').write_text(json.dumps(shift,ensure_ascii=False,indent=2)+'\n')
 (O/'near6.json').write_text(json.dumps(near,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'groups':groups,'contribution':contribution,'R_seed':R_seed,'seed':seed,'verdict':verdict,'filtered':result['filtered_report_only'],'on_paths':'see near6','center_checks':[(v['id'],v['T5_s102_center_check']) for v in points]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
