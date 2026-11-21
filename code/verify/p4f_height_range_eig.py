import numpy as np
def U(z,zm): return 1.22*(np.exp(-0.15*z/zm)-np.exp(-3.2175*z/zm))*60
for zm in [30,60,100]:
  for zmax in [100,150,200]:
    z=np.arange(2,zmax+1,2.0); u=U(z,zm); D=np.abs(z[:,None]-z[None,:]); Ub=(u[:,None]+u[None,:])/2
    m=min((np.linalg.eigvalsh(np.exp(-c*D/Ub)).min(),c) for c in [0.001,0.003,0.01,0.03,0.1,0.3,1])
    print("zm",zm,"z<=",zmax,"n",len(z),"min_eig %.2e at c=%g"%m)
