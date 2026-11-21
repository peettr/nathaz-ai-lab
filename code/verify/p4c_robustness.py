import numpy as np
# 稳健性：只保留 U>=0.2*Umax 的高度；同时对比 Ubar 的三种取法
def prof(z,zm): return 1.22*(np.exp(-0.15*z/zm)-np.exp(-3.2175*z/zm))*60
for zm in [30,60,100]:
  z=np.linspace(1,500,400); U=prof(z,zm); keep=U>=0.2*U.max(); z=z[keep][::3]; U=U[keep][::3]
  D=np.abs(z[:,None]-z[None,:])
  for name,Ub in [("arith",(U[:,None]+U[None,:])/2),("geom",np.sqrt(U[:,None]*U[None,:])),("const_Umax",np.full_like(D,U.max()))]:
    m=min(np.linalg.eigvalsh(np.exp(-c*D/Ub)).min() for c in [0.001,0.01,0.1,1,10])
    print(zm,len(z),round(z.min(),1),round(z.max(),1),name,round(float(m),6))
