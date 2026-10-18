from pathlib import Path
import numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import xlrd,csv,json
base=Path('./22_Lab/06_Logs/luw')
z=np.load(base/'caseE_N_avg_z2_slice.npz'); u=z['u']; origin=z['origin']; dx=float(z['spacing']); nz,ny,nx=map(int,z['dimensions'][::-1]); speed=np.linalg.norm(u,axis=2)
book=xlrd.open_workbook('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM/CaseE(Niigata).xls')
geo=book.sheet_by_name('Geometry&Points'); obs={s:book.sheet_by_name(s) for s in ['Results (Before Construction)','Results (After Construction)']}
# 0 degrees implies velocity toward -y; N measurement column index 2.
# Geometry origin is reported as centre of the reproducing area; domain midpoint alignment is an unverified hypothesis.
profile=[(1.25,2.847),(2.5,3.042),(5,3.2604),(7.5,3.4086),(12.5,3.7674),(25,4.3602)]
uref=float(np.interp(15.9,*zip(*profile)))
ids=[]; xy=[]; sim=[]; refs={key:[] for key in obs}
for row in range(2,82):
 ident=int(geo.cell_value(row,1)); x=float(geo.cell_value(row,2)); y=float(geo.cell_value(row,3)); ids.append(ident); xy.append((x,y))
 # linear horizontal interpolation of model velocity components; only valid for assumed placement
 xi=(x+2022.500153/2-origin[0])/dx; yi=(y+1996.500092/2-origin[1])/dx
 i=int(np.floor(xi)); j=int(np.floor(yi)); a=xi-i; b=yi-j
 if 0<=i<nx-1 and 0<=j<ny-1:
  vec=(1-a)*(1-b)*u[j,i]+a*(1-b)*u[j,i+1]+(1-a)*b*u[j+1,i]+a*b*u[j+1,i+1]; sim.append(float(np.linalg.norm(vec)/uref))
 else:sim.append(float('nan'))
 for key,sh in obs.items(): refs[key].append(float(sh.cell_value(row+1,2)))
ids=np.array(ids); xy=np.array(xy); sim=np.array(sim); before=np.array(refs['Results (Before Construction)']); after=np.array(refs['Results (After Construction)'])
valid=np.isfinite(sim); metrics={}
for title,arr in [('before',before),('after',after)]:
 mask=valid&np.isfinite(arr); metrics[title]={'n':int(mask.sum()),'mae':float(np.mean(np.abs(sim[mask]-arr[mask]))),'corr':float(np.corrcoef(sim[mask],arr[mask])[0,1]) if mask.sum()>2 else None,'mean_obs':float(arr[mask].mean()),'mean_sim':float(sim[mask].mean())}
with (base/'CaseE_N_exploratory_metrics_v2.json').open('w') as f: json.dump({'assumption':'unverified midpoint registration of xls local XY; N=angle0; z=2m; Uref=profile interpolation at 15.9m; time mean last 2000 steps/stride10','uref_mps':uref,'metrics':metrics,'grid':{'origin':origin.tolist(),'spacing':dx,'shape':list(u.shape)}},f,indent=2)
with (base/'CaseE_N_points_exploratory_v2.csv').open('w',newline='') as f:
 w=csv.writer(f); w.writerow(['point','x_local_m','y_local_m','sim_speed_over_U15p9','tunnel_before_N','tunnel_after_N'])
 for t in zip(ids,xy[:,0],xy[:,1],sim,before,after):w.writerow(t)
fig,axes=plt.subplots(1,2,figsize=(12,5),constrained_layout=True)
ax=axes[0]; x0=2022.500153/2;y0=1996.500092/2
X=(origin[0]+np.arange(nx)*dx-x0); Y=(origin[1]+np.arange(ny)*dx-y0)
ix=(X>=-300)&(X<=300); iy=(Y>=-300)&(Y<=300)
im=ax.imshow(speed[np.ix_(iy,ix)]/uref,origin='lower',extent=[X[ix][0],X[ix][-1],Y[iy][0],Y[iy][-1]],cmap='viridis',vmin=0,vmax=1.3)
ax.scatter(xy[:,0],xy[:,1],facecolors='none',edgecolors='white',s=12,lw=.7);ax.set(xlabel='x relative to assumed domain centre (m)',ylabel='y relative to assumed domain centre (m)',title='LUW |mean U|/U15.9, z=2 m; N (0°)');fig.colorbar(im,ax=ax,label='dimensionless speed')
ax=axes[1];ax.scatter(before,sim,s=20,alpha=.75,label=f'Before: MAE {metrics["before"]["mae"]:.2f}, r {metrics["before"]["corr"]:.2f}')
ax.scatter(after,sim,s=20,alpha=.75,label=f'After: MAE {metrics["after"]["mae"]:.2f}, r {metrics["after"]["corr"]:.2f}')
ax.plot([0,1.7],[0,1.7],color='grey',lw=1);ax.set(xlabel='Wind tunnel U(2 m)/U_inflow(15.9 m)',ylabel='LUW |mean U|(2 m)/U_inflow(15.9 m)',xlim=(0,1.7),ylim=(0,1.7),title='Exploratory ONLY: xls registration/build state unverified');ax.legend(fontsize=9)
fig.savefig(base/'CaseE_N_wind_tunnel_exploratory_v2.png',dpi=160);plt.close(fig)
print('uref',uref,'metrics',metrics,'speedrange',np.nanmin(speed),np.nanmax(speed),'files:',base/'CaseE_N_wind_tunnel_exploratory_v2.png')
