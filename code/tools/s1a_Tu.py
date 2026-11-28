"""T_u：站 z=6 顺风速度 uz 脉动自相关积分到首个零点（50 Hz 原采样，42–642 s），单位 s。用法: python3 -I s1a_Tu.py <npz> [站...]"""
import sys,numpy as np
d=np.load(sys.argv[1]);X=d['x'];ST=list(d['stations']);FS=50
def Tu(g):
    u=X[:,3*ST.index(f'{g}_z6')+2];u=u-u.mean();n=len(u);f=np.fft.rfft(u,2*n);r=np.fft.irfft(f*np.conj(f))[:n];r/=r[0]
    k=np.argmax(r<=0);return float(r[:k].sum()/FS)
for g in sys.argv[2:]:print(g,round(Tu(g),3))
