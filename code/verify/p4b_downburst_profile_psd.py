import numpy as np
# 下击暴流 Vicroy 型剖面：U(z)=1.22[exp(-0.15 z/zm)-exp(-3.2175 z/zm)]Umax, zm 取 30/60/100 m
for zm in [30,60,100]:
  for cf in [0.01,0.1,1,10]:
    for c0 in [8,10]:
      z=np.linspace(1,500,150); U=1.22*(np.exp(-0.15*z/zm)-np.exp(-3.2175*z/zm))*60
      D=np.abs(z[:,None]-z[None,:]); Ub=(U[:,None]+U[None,:])/2
      G=np.exp(-cf*c0/10*D/Ub)
      print(zm,cf,c0,round(float(np.linalg.eigvalsh(G).min()),6))
