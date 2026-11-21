"""Read-only summary of paired monitor CSVs; no causality claim."""
import argparse,json
import numpy as np
p=argparse.ArgumentParser();p.add_argument('diagnostic');p.add_argument('corrected');a=p.parse_args()
for label,path in [('zero_gradient',a.diagnostic),('fixed_pressure',a.corrected)]:
    x=np.genfromtxt(path,delimiter=',',names=True)
    assert len(x)>=2 and np.all(np.diff(x['step'])==2048)
    rho=x['rho_mean'];u=x['u_mean'];diff=x['inlet_mass_flux']-x['outlet_mass_flux']
    def corr(a,b):
        return float(np.corrcoef(a,b)[0,1]) if np.std(a)>0 and np.std(b)>0 else None
    print(json.dumps(dict(stage='monitor_summary',outlet=label,n=len(x),first_step=int(x['step'][0]),last_step=int(x['step'][-1]),rho_first=float(rho[0]),rho_last=float(rho[-1]),u_first=float(u[0]),u_last=float(u[-1]),flux_imbalance_mean=float(np.mean(diff)),rho_u_pearson=corr(rho,u),rho_flux_cumulative_pearson=corr(rho,np.cumsum(diff)),rho_step_pearson=corr(rho,x['step']),u_step_pearson=corr(u,x['step']))))
