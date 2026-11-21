"""P4 试刀：Davenport 相干用两点平均风速 Ubar=(U1+U2)/2 时，相干矩阵是否仍半正定。
gamma_jk = exp(-c f |z_j - z_k| / ((U_j+U_k)/2)),  U(z)=U10 (z/10)^alpha.
扫 alpha, c*f, 高度网格；报最小特征值。秒级。"""
import numpy as np, itertools, json, sys
res=[]
for alpha in [0.0,0.1,0.16,0.3,0.6,1.0,2.0]:
    for cf in [0.01,0.1,1,10,100]:
        for (zmin,zmax,n) in [(1,200,50),(1,300,80),(0.1,500,120)]:
            z=np.linspace(zmin,zmax,n); U=10*(z/10)**alpha
            D=np.abs(z[:,None]-z[None,:]); Ub=(U[:,None]+U[None,:])/2
            G=np.exp(-cf*D/Ub)
            lam=np.linalg.eigvalsh(G).min()
            res.append(dict(alpha=alpha,cf=cf,zmin=zmin,zmax=zmax,n=n,min_eig=float(lam)))
neg=[r for r in res if r['min_eig']<-1e-10]
print("cases",len(res),"negative",len(neg))
for r in sorted(res,key=lambda r:r['min_eig'])[:8]: print(r)
json.dump(res,open(sys.argv[1],'w'),indent=1)
