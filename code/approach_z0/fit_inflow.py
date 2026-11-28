import xlrd,numpy as np
from scipy.optimize import least_squares
p='./22_Lab/06_Logs/argon_blind_luw/repo/examples/example_ProfileResearch_noDEM/CaseE(Niigata).xls'
s=xlrd.open_workbook(p).sheet_by_name('Inflow')
z=np.array([s.cell_value(r,1)*250 for r in range(2,6)]);u=np.array([s.cell_value(r,2)*7.8 for r in range(2,6)])
for wall in (0.,.5):
 h=z-wall
 def model(p,disp=False):
  a,lnz=p[:2]; d=p[2] if disp else 0.
  return a*np.log((h-d+np.exp(lnz))/np.exp(lnz))
 for disp in (False,True):
  sol=least_squares(lambda p:model(p,disp)-u,[.32,np.log(.00014)]+([0.] if disp else []),bounds=([.00001,np.log(1e-9)]+([-10.] if disp else []),[10.,np.log(10.)]+([min(h)-.001] if disp else [])),xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=20000)
  print('wall',wall,'disp',disp,'z,u',list(zip(z,u)),'z0',np.exp(sol.x[1]),'ustar',sol.x[0]*.4,'d_relative',sol.x[2] if disp else 0,'pred',model(sol.x,disp),'residual',model(sol.x,disp)-u,'rmse',np.sqrt(np.mean(sol.fun**2)))
