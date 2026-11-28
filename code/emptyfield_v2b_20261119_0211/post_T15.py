#!/usr/bin/env python3
"""T15 frozen G1/G2/G3 postprocess; only host-verified remote evidence."""
import csv,hashlib,json,math,pathlib,re,statistics
import numpy as np
R=pathlib.Path(__file__).resolve().parent
D=next(p for p in R.glob('session_luw-t15-a100-*/evidence') if (p/'run.done').exists())
O=R/'postprocess_v2b_fix1';O.mkdir(exist_ok=False)
T3=R.parents[1]/'R21.4a_T3_emptyground/T3d'
PROFILE=R.parents[1]/'R21.4a_T4_groundWM/phaseB_v2/stage/dx1p0_s107/wind_bc/profile.dat'
SRC=R/'stage/FluidX3D_on/src/lbm.cpp'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def verified(name):
 p=D/name;assert p.is_file() and sha(p)==(D/(name+'.sha256')).read_text().strip(),name
 return p
def save(name,data):
 p=O/name
 with p.open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
 (O/(name+'.sha256')).write_text(sha(p)+'\n')
 return str(p)
# Frozen T15 source sets physical z0 = 0.024 m at dx=1m; nominal inlet profile
# interpolated to 1.5m determines inlet design u* by T15's formula.
s=SRC.read_text();z0s=re.findall(r'experimental_ground_z0_lattice\s*=\s*0\.024f',s)
assert z0s,'z0 source not found';z0=.024;kap=.4
pts=[tuple(map(float,row.strip().split())) for row in PROFILE.read_text().splitlines()[1:]]
za,ua=max((z,u) for z,u in pts if z<=1.5);zb,ub=min((z,u) for z,u in pts if z>=1.5)
U_design=ua+(ub-ua)*(1.5-za)/(zb-za)
u_design=kap*U_design/math.log((1.5+z0)/z0)
def seed_metrics(label):
 name=label+'_thin.npz';p=verified(name);q=verified(label+'_profile_upper.npz')
 with np.load(p,allow_pickle=False) as a,np.load(q,allow_pickle=False) as b:
  lo_u=a['u_avg'];lo_f=a['fluid'];hi_u=b['u_avg'];hi_f=b['fluid'];m=json.loads(str(a['metadata']));mh=json.loads(str(b['metadata']))
  assert lo_u.shape==(28,100,550,3) and lo_f.shape==(28,100,550)
  assert hi_u.shape==(6,100,550,3) and hi_f.shape==(6,100,550)
  assert m['k_start']==20 and mh['k_start']==48 and m['origin']==mh['origin'] and m['spacing']==mh['spacing']
  u=np.concatenate([lo_u,hi_u]);f=np.concatenate([lo_f,hi_f]);wall=.5;oz=m['origin'][2]
  ys=np.arange(40,61);xc=252.1485175
  def sample(x,h):
   i=round(x);zf=(wall+h-oz);k=int(math.floor(zf));alpha=zf-k;ik=k-20
   if not(np.all(f[ik,ys,i]>.5) and np.all(f[ik+1,ys,i]>.5)):raise ValueError('nonfluid support '+label+str((x,h)))
   vec=(1-alpha)*u[ik,ys,i].astype('f8')+alpha*u[ik+1,ys,i].astype('f8')
   return float(np.linalg.norm(vec,axis=1).mean())
  rows=[]
  for h in np.arange(5.,30.0001,.5):
   p0=sample(5,h);px=sample(xc,h);rows.append({'z_agl_m':float(h),'G_x5_mps':p0,'G_xc_mps':px,'relative_deviation':abs(px/p0-1.)})
  g_in=sample(5,2);g_xc=sample(xc,2)
 with verified(label+'_wall_tau_actual.csv').open() as fh:tau=list(csv.DictReader(fh))
 for c in ('tau_abs_over_rho_lattice','fx_over_rho_lattice','fy_over_rho_lattice','ustar_mps','count'):
  if any(c not in r or not math.isfinite(float(r[c])) for r in tau):raise ValueError('wall column '+c)
 xmid=275;yvals=[r for r in tau if int(r['x'])==xmid and 2<=int(r['y'])<=97]
 if not yvals:raise ValueError('no fetch midpoint rows')
 ustar=float(statistics.mean(float(r['ustar_mps']) for r in yvals))
 nonzero=sum(abs(float(r['tau_abs_over_rho_lattice']))>0 for r in tau)
 tau_mean=float(statistics.mean(float(r['tau_abs_over_rho_lattice']) for r in tau))
 strip=[r for r in tau if int(r['y']) in (0,1,98,99)]
 eligible=[r for r in tau if 2<=int(r['y'])<=97]
 def mean_or_null(rows,key):return float(statistics.mean(float(r[key]) for r in rows)) if rows else None
 def band_speed(yy):
  # Description only; sample exactly the same VTK height and vector norm as G1.
  i=round(xc);zf=wall+2-oz;k=int(math.floor(zf));alpha=zf-k;ik=k-20
  yy=np.asarray(yy,dtype=int)
  if not len(yy):return None
  valid=(f[ik,yy,i]>.5)&(f[ik+1,yy,i]>.5)
  yy=yy[valid]
  if not len(yy):return None
  vec=(1-alpha)*u[ik,yy,i].astype('f8')+alpha*u[ik+1,yy,i].astype('f8')
  return float(np.linalg.norm(vec,axis=1).mean())
 strip_speed=band_speed((0,1,98,99));interior_speed=band_speed(range(2,98))
 # Retain profile in its own hashed compact file.
 prof=O/(label+'_profile.csv')
 with prof.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=('z_agl_m','G_x5_mps','G_xc_mps','relative_deviation'));w.writeheader();w.writerows(rows)
 (O/(prof.name+'.sha256')).write_text(sha(prof)+'\n')
 return {'label':label,'H':g_xc/g_in,'G_x5_2m_mps':g_in,'G_xc_2m_mps':g_xc,'profile_max_deviation':max(r['relative_deviation'] for r in rows),'ustar_fetch_mid_mps':ustar,'ustar_design_inlet_mps':u_design,'ustar_ratio':ustar/u_design,'fetch_mid_x_m':xmid,'fetch_mid_eligible_columns':len(yvals),'wall_tau_columns':len(tau),'wall_tau_nonzero_fraction':nonzero/len(tau),'wall_tau_mean_lattice':tau_mean,'strip_ustar_mps':mean_or_null(strip,'ustar_mps'),'interior_ustar_mps':mean_or_null(eligible,'ustar_mps'),'strip_2m_speed_mps':strip_speed,'interior_2m_speed_mps':interior_speed,'strip_tau_rows':len(strip),'profile_rows':len(rows),'profile_file':str(prof),'input_sha256':{n:sha(D/n) for n in (name,label+'_profile_upper.npz',label+'_wall_tau_actual.csv')},'notes':'nominal inlet z=1.5 m linearly interpolated profile; z0=0.024 m, κ=0.4; fetch midpoint x=275 m; eligible-only ustar; strip tau may be absent from native eligible exporter'}
def main():
 done=json.loads(verified('run.done').read_text());assert done=={'mode':'production','verified_cases':['WM_s107','WM_s108','WM_s109']}
 s={};refs={};t4={}
 for seed in (107,108,109):
  label=f'WM_s{seed}';v=seed_metrics(label);s[str(seed)]=v;save(label+'_metrics.json',v)
  b=json.loads((R.parents[1]/'R21.4a_T4_groundWM/phaseB_v2/B_verdict.json').read_text());refs[str(seed)]=b['seeds'][str(seed)]['H_1m'];t4[str(seed)]=b['seeds'][str(seed)]['H_WM']
  v['H_bounce_1m']=refs[str(seed)];v['H_T4_first_layer']=t4[str(seed)];v['delta_H_vs_bounce']=v['H']-refs[str(seed)]
 g1=all(v['H']>=.80 and v['delta_H_vs_bounce']>=.10 for v in s.values())
 g2=all(v['profile_max_deviation']<=.05 for v in s.values())
 g3=all(.9<=v['ustar_ratio']<=1.1 for v in s.values())
 if g1 and g2 and g3:verdict='通过（仅空场）'
 elif g1:verdict='中间'
 elif all(v['delta_H_vs_bounce']<=.03 for v in s.values()):verdict='无改善'
 else:verdict='中间'
 report={'status':'E1_E2_E3prime_E4_see_verified_prior_evidence','G1':{'pass':g1,'threshold':'each H>=0.80 and delta_H>=0.10'},'G2':{'pass':g2,'threshold':'each max deviation <=0.05 at x_c, 5-30 m'},'G3':{'pass':g3,'threshold':'each eligible-only ustar ratio in [0.9,1.1]','inlet_design_method':'U_inlet(1.5 m) linearly interpolated from frozen profile.dat; κ=0.4,z0=.024 m'},'seeds':s,'k3_s107_report_only':None,'verdict':verdict,'scope':'empty ground only; no Case E precision claim; k3 deferred'}
 save('T15_verdict.json',report);print(json.dumps({'verdict':verdict,'gates':{'G1':g1,'G2':g2,'G3':g3},'metrics':{k:{a:v[a] for a in ('H','delta_H_vs_bounce','profile_max_deviation','ustar_ratio')} for k,v in s.items()}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
