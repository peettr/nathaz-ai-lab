from pathlib import Path
import sys,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
b=Path('./22_Lab/06_Logs/luw');sys.path.insert(0,str(b/'pydeps'));import xlrd
p=Path('./.cache/dwt-luw-eval/examples/example_ProfileResearch_noDEM');pr=np.loadtxt(p/'wind_bc/profile.dat',skiprows=1);s=xlrd.open_workbook(str(p/'CaseE(Niigata).xls')).sheet_by_name('Inflow');z=[];u=[]
for i in range(2,s.nrows):
 try:z.append(float(s.cell_value(i,1)));u.append(float(s.cell_value(i,2)))
 except (TypeError,ValueError):pass
fig,ax=plt.subplots(figsize=(6,5));ax.plot(pr[:,1]/7.8,pr[:,0]/250,'o-',label='repo profile.dat (U/7.8; z/250)');ax.plot(u,z,'x',label='xls Inflow U/UR versus z/ZR');ax.set(xlabel='Inflow normalized U/UR',ylabel='z/ZR',title='Case E prescribed inflow only (NOT a solver result)');ax.legend();ax.grid(alpha=.3);fig.tight_layout();fig.savefig(b/'CaseE_inflow_only_r4.png',dpi=160);print('saved',b/'CaseE_inflow_only_r4.png','n_xls',len(u),'n_profile',len(pr))
