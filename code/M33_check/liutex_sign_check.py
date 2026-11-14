"""M33 核对：照抄 DeltaLiutexTildeDelta.C 第 110–150 行的算法，与 numpy 真值比。只用 numpy。"""
import numpy as np
rng=np.random.default_rng(0); ang=[];lam=[];n=0
while n<2000:
    A=rng.normal(size=(3,3)); A-=np.trace(A)/3*np.eye(3)
    w,V=np.linalg.eig(A)
    if np.sum(abs(w.imag)<1e-12)!=1: continue
    i=np.argmin(abs(w.imag)); lt=w[i].real; vt=V[:,i].real; vt/=np.linalg.norm(vt)
    a=A.ravel(); I1=np.trace(A); I2=(A[0,0]*A[1,1]+A[0,0]*A[2,2]+A[1,1]*A[2,2])-(A[0,1]*A[1,0]+A[0,2]*A[2,0]+A[1,2]*A[2,1]); I3=np.linalg.det(A)
    p=(3*I2-I1**2)/3; q=(2*I1**3-9*I1*I2+27*I3)/27   # 代码原样
    d=(q/2)**2+(p/3)**3
    if d<=0: continue
    s=np.sqrt(d); S1=np.cbrt(-q/2+s); S2=np.cbrt(-q/2-s); lc=S1+S2+I1/3
    B=A-lc*np.eye(3); det=B[0,0]*B[1,1]-B[0,1]*B[1,0]
    v1=(B[0,2]*B[1,1]-B[0,1]*B[1,2])/det; v2=(B[0,0]*B[1,2]-B[0,2]*B[1,0])/det; v=np.array([v1,v2,1.]); v/=np.linalg.norm(v)
    ang.append(np.degrees(np.arccos(min(1,abs(v@vt))))); lam.append(lc/lt); n+=1
ang=np.array(ang);lam=np.array(lam)
print('n',n,'median angle deg',round(np.median(ang),1),'share <1deg',float((ang<1).mean()),'lambda_code/lambda_true median',round(np.median(lam),6),'all -1',bool(np.allclose(lam,-1,atol=1e-6)))
# 修正后对照：q 反号 + 分子反号
