#!/usr/bin/env python3.10
"""Read archived wall-column stress and thin mean fields; no solver run."""
import csv, json, math, hashlib, statistics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parent
L=O.parents[1]
T15=L/'R21.4a_T15_second_layer_WM/emptyfield_v2b_20261119_0211'
E=T15/'session_luw-t15-a100-34f6b9f9/evidence'
T4=L/'R21.4a_T4_groundWM/phaseB_v2'
PROFILE=T4/'stage/dx1p0_s107/wind_bc/profile.dat'
inputs={}
def record(p):
    assert p.is_file(),p
    h=hashlib.sha256(p.read_bytes()).hexdigest();inputs[str(p)]=h
    side=Path(str(p)+'.sha256')
    if side.exists(): assert side.read_text().split()[0]==h,p
    return p
pts=[tuple(map(float,line.split())) for line in record(PROFILE).read_text().splitlines()[1:]]
z=np.array([a for a,b in pts]);u=np.array([b for a,b in pts]);kap=.4;rough=.024
# Two-point log-profile estimate, then least-squares across the first four levels.
def logfit(zv,uv):
    slope, intercept=np.polyfit(np.log(zv),uv,1)
    z0=math.exp(-intercept/slope)
    return {'u_star_mps':float(kap*slope),'z0_m':float(z0),'log_slope_mps':float(slope),'intercept_mps':float(intercept),'fit_height_m':list(map(float,zv)),'rmse_mps':float(np.sqrt(np.mean((uv-(slope*np.log(zv)+intercept))**2)))}
fits={'first_2':logfit(z[:2],u[:2]),'first_3':logfit(z[:3],u[:3]),'first_4':logfit(z[:4],u[:4]),'first_5':logfit(z[:5],u[:5])}
u15=float(np.interp(1.5,z,u));design=kap*u15/math.log((1.5+rough)/rough)
# Full log-law with first two positive heights is an approximation (z0 << z).
# Wood (1982) wall-region dimensional scaling uses larger z0, not an equilibrium length.
def ibl_wood(x):return .28*rough*(x/rough)**.8
results={}; rows=[]; input_speed=[]
for typ in ('T15_second','T4_first'):
  for seed in (107,108,109):
    pre=f'WM_s{seed}' if typ=='T15_second' else f'B_dx1p0_s{seed}'
    base=E if typ=='T15_second' else T4/'evidence'
    tau_path=record(base/(pre+'_wall_tau_actual.csv'))
    grouped={}
    with tau_path.open(newline='') as f:
      for r in csv.DictReader(f):
        x=int(r['x']);y=int(r['y'])
        assert 2<=x<=547 and 2<=y<=97 and int(r['count'])>0
        grouped.setdefault(x,[]).append(float(r['ustar_mps']))
    assert set(grouped)==set(range(2,548))
    for x,v in grouped.items():assert len(v)>=90 and all(math.isfinite(a) for a in v)
    thin_path=record(base/(pre+'_thin.npz'))
    with np.load(thin_path,allow_pickle=False) as d:
      v=d['u_avg'];fluid=d['fluid'];meta=json.loads(str(d['metadata']))
      assert meta['k_start']==20 and v.shape[:3]==(28,100,550)
      # T15/T4 common height: z=2.5 VTK label -> 2 m AGL, k_start=20.
      jj=2; yy=np.arange(40,61)
      assert (fluid[jj,yy,5:548]>.5).all(),thin_path
      # Maintain G convention: magnitude of time-mean velocity, then y mean.
      speed=np.linalg.norm(v[jj,yy,5:548].astype('f8'),axis=-1).mean(axis=0)
    for x in range(5,548):
      uv=statistics.mean(grouped[x]); rows.append({'configuration':typ,'seed':seed,'x_m':x,'eligible_columns':len(grouped[x]),'ustar_mps':uv,'ustar_over_design':uv/design,'speed2m_y40_60_mps':float(speed[x-5])})
    sub=[r for r in rows if r['seed']==seed and r['configuration']==typ]
    def at(x):return next(r for r in sub if r['x_m']==x)
    us=[r['ustar_mps'] for r in sub]
    results[f'{typ}_s{seed}']={'x5':at(5),'x275':at(275),'x500':at(500),'x547':at(547),'ustar_min_mps':min(us),'ustar_max_mps':max(us),'min_x_m':sub[us.index(min(us))]['x_m'],'max_x_m':sub[us.index(max(us))]['x_m'],'exit_minus_mid_mps':at(547)['ustar_mps']-at(275)['ustar_mps'],'entry_to_mid_change_fraction':at(275)['ustar_mps']/at(5)['ustar_mps']-1,'mid_to_exit_change_fraction':at(547)['ustar_mps']/at(275)['ustar_mps']-1,'fit_normalized_x275':{name:at(275)['ustar_mps']/fit['u_star_mps'] for name,fit in fits.items()}}
    input_speed.append((typ,seed,at(5)['speed2m_y40_60_mps'],at(275)['speed2m_y40_60_mps']))
# Provenance and two window-wide compact plots.
for file in (T15/'postprocess_v2b_fix1/T15_verdict.json',T4/'B_verdict.json'):record(file)
out={'definitions':{'ustar':'mean of archived ustar_mps over actual eligible y columns per x; no strip or zero fill','speed2m':'mean_y40..60 norm(u_avg[k22,y,x,:]); VTK label z=2.5 m is 2 m above wall','x':'5..547 m; x=275 m fetch midpoint','profile_fit':'ordinary least squares U=A ln(z)+B, u*=kappa*A, z0=exp(-B/A); low-z approximation ln((z+z0)/z0)≈ln(z/z0); not a turbulence-stress measurement'},'profile':{'path':str(PROFILE),'first_levels':pts[:5],'u_1p5_mps':u15,'design_ustar_mps':design,'kappa':kap,'wall_z0_m':rough,'fits':fits,'ratio_wall_z0_to_first4_fit':rough/fits['first_4']['z0_m']},'IBL_conditional':{'reference':'Wood 1982, Eq.(4) PDF p.2 journal p.242; wall-region limit delta_i/delta<~0.2','formula':'h/z0r=0.28*(x/z0r)^0.8, z0r=max(upstream,downstream)=0.024 m','x_m':[5,275,547],'h_m':[ibl_wood(x) for x in (5,275,547)],'caveat':'conditional ideal-neutral homogeneous step only, not verified IBL height in finite LBM box; no upstream roughness-controlled experiment'},'cases':results,'input_sha256':inputs}
with (O/'USTAR_FETCH_RESULT.json').open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
with (O/'USTAR_FETCH.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,axs=plt.subplots(2,1,figsize=(9,7),sharex=True)
for typ,ls in [('T15_second','-'),('T4_first','--')]:
 for seed in (107,108,109):
  rr=[r for r in rows if r['configuration']==typ and r['seed']==seed]
  axs[0].plot([r['x_m'] for r in rr],[r['ustar_over_design'] for r in rr],ls,label=f'{typ} s{seed}',lw=1.1)
  axs[1].plot([r['x_m'] for r in rr],[r['speed2m_y40_60_mps'] for r in rr],ls,lw=1.1)
axs[0].axhline(1,color='gray',lw=.8);axs[0].set_ylabel('eligible mean u* / design u*');axs[0].legend(ncol=2,fontsize=8)
axs[1].set_ylabel('2 m mean speed (m/s)');axs[1].set_xlabel('fetch x (m)')
for ax in axs:ax.grid(alpha=.25);ax.axvline(275,color='gray',ls=':',lw=.8)
fig.suptitle('T15 second-layer and T4 first-layer: archived empty field')
fig.tight_layout();fig.savefig(O/'USTAR_FETCH.png',dpi=160);plt.close(fig)
print(json.dumps({'design_ustar':design,'fits':fits,'IBL':out['IBL_conditional'],'cases':results,'rows':len(rows),'inputs':len(inputs),'speed':input_speed},ensure_ascii=False,indent=2))
