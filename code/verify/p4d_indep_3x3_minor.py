# P4 独立复核：纯 Python（不用 numpy），在 Vicroy 剖面上找行列式为负的小主子式（2x2 恒正，找 3x3/4x4）。
import math, itertools
def U(z,zm): return 1.22*(math.exp(-0.15*z/zm)-math.exp(-3.2175*z/zm))*60
def det(M):
    n=len(M); A=[r[:] for r in M]; d=1.0
    for i in range(n):
        p=max(range(i,n),key=lambda r:abs(A[r][i]))
        if abs(A[p][i])<1e-300: return 0.0
        if p!=i: A[i],A[p]=A[p],A[i]; d=-d
        d*=A[i][i]
        for r in range(i+1,n):
            f=A[r][i]/A[i][i]
            for c in range(i,n): A[r][c]-=f*A[i][c]
    return d
best=None
for zm in [30,60,100]:
    Umax=max(U(z,zm) for z in range(1,501))
    zs=[z for z in range(2,500,6) if U(z,zm)>=0.2*Umax]
    for c in [0.001,0.01,0.1,1]:
        for tri in itertools.combinations(zs,3):
            G=[[math.exp(-c*abs(a-b)/((U(a,zm)+U(b,zm))/2)) for b in tri] for a in tri]
            d=det(G)
            if best is None or d<best[0]: best=(d,zm,c,tri,[round(U(z,zm),2) for z in tri])
print("min 3x3 det:",best)
