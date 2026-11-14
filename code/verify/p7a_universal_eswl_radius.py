# P7' 数值核对：同时复现 M 个响应峰值的单一荷载，其等效「几倍峰值事件」半径 rho 满足 rho^2 = 1' Gamma^{-1} 1（Gamma 为目标响应相关矩阵）
import numpy as np
rng=np.random.default_rng(20261108)
for trial in range(5):
    M,N=int(rng.integers(3,12)),int(rng.integers(15,60))
    B=rng.normal(size=(M,N))            # B = A C^{1/2}，行 i 对应响应 i
    rhat=np.linalg.norm(B,axis=1)        # 各响应脉动峰值 / g
    z=np.linalg.lstsq(B,rhat,rcond=None)[0]   # 最小范数解：B z = rhat
    S=[邮箱]; d=np.sqrt(np.diag(S)); Gam=S/np.outer(d,d)
    rho2=np.ones(M)@np.linalg.solve(Gam,np.ones(M))
    print(M,N,"resid=%.1e"%np.abs(B@z-rhat).max(),"||z||^2=%.6f"%(z@z),"1'G^-1 1=%.6f"%rho2)
# 不相关响应：rho = sqrt(M)
B=np.eye(9,30); z=np.linalg.lstsq(B,np.linalg.norm(B,axis=1),rcond=None)[0]; print("uncorrelated M=9 ||z||=",np.linalg.norm(z))
