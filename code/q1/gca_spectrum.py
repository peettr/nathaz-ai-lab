"""A2 input-spectrum warping from noisy probe histories only.

Pinyochotiwong 2022 PDF pp.117--122 equations 6-10--6-13; the
nonnegative incremental gain and smoothing are explicitly assumed.
"""
import numpy as np
from scipy.signal import welch
from common import Z,target,vector_command
FREQ=np.geomspace(.02,5.,32)

def target_psd(event,height,freq):
    t=target(event);u=t[0,height];iu=t[1,height];lux=t[2,height]
    # Mokhtar 2024 PDF p.5 equation 8.
    return 4*lux*iu**2*u/(1+70.8*(freq*lux/u)**2)**(5/6)

def update(warp,series,event,gain):
    if warp is None:warp=np.ones((8,len(FREQ)))
    new=warp.copy();fs=20.
    for row in range(8):
        z=(row+.5)*3/13;h=int(np.argmin(abs(Z-z)))
        f,s=welch(series[h],fs=fs,nperseg=min(256,series.shape[-1]))
        measured=np.interp(FREQ,f,s,left=s[0],right=s[-1])
        desired=target_psd(event,h,FREQ)
        ratio=np.clip(desired/np.maximum(measured,1e-7),.05,20.)
        # Incremental additive PSD warp, eq. 6-13; protect nonnegative PSD.
        factor=np.sqrt(np.maximum(.01,1+gain*(ratio-1)))
        new[row]=np.clip(new[row]*factor,.1,5.)
        new[row]=np.convolve(np.pad(new[row],(1,1),mode='edge'),np.ones(3)/3,mode='valid')
    return new

def warped_rows(x,p,total_s,seed,warp):
    cmd=vector_command(x,p,total_s,seed)
    rows=cmd['rows'].copy()
    if warp is None:return rows
    freq=np.fft.rfftfreq(rows.shape[1],1/p.fs)
    # Uniform 5-Hz low-pass on input; assumes a fixed cutoff (thesis pp.121--122).
    lowpass=1/np.sqrt(1+(freq/5.)**8)
    for j in range(8):
        mean=rows[j].mean();signal=np.fft.rfft(rows[j]-mean)
        interp=np.interp(freq,FREQ,warp[j],left=warp[j,0],right=warp[j,-1])
        rows[j]=mean+np.fft.irfft(signal*interp*lowpass,n=rows.shape[1])
    # Common scale over all rows preserves contrasts, ensures actuator limits.
    center=np.mean(x[1:9]);d=rows-center
    pos=d>0;neg=d<0
    scale=min(1.,float(np.min((20-center)/d[pos])) if np.any(pos) else 1.,
              float(np.min((-17-center)/d[neg])) if np.any(neg) else 1.)
    return np.clip(center+scale*d,-17,20)
