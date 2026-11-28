"""UF synthetic stateful reduced-order object; Lead v5--v8 equations, no UF private data."""
from dataclasses import dataclass,replace
import numpy as np

Z=np.array([.05,.10,.15,.198,.25,.30,.525,.725,.95,1.15,1.375,1.575])
ROW_Z=(np.arange(8)+.5)*3/13
DISTANCE=26.3
@dataclass(frozen=True)
class Params:
    fs:float=20.; b:float=.35; tau_ref:float=.5; h650:float=.92
    h50_ratio:float=.625; kappa:float=.8; width:float=.18; c:float=.5
    ffm_rate:float=75.; main_tau:float=4.; drift:float=.01
    s_q:float=.25; tau_q:float=8.; s_p:float=.45; tau_p:float=8.
    z_i:float=.5; gamma:float=.2

def equilibrium(n,f,p):
    return np.sqrt(np.maximum(0.,(1-p.b)*np.asarray(n)**2+p.b*np.asarray(f)*np.abs(f)))

def roughness(terrain,z,p):
    terrain=np.asarray(terrain,float)
    if terrain.shape!=(2,): raise ValueError('Terraformer shape must be (upstream,downstream)')
    return np.exp(-np.asarray(z)/p.z_i)*terrain[1]+(1-np.exp(-np.asarray(z)/p.z_i))*terrain[0]

def profile(p,terrain,z=Z):
    z=np.asarray(z,float)
    h=np.interp(z,[.05,.65,1.575],[p.h650*p.h50_ratio,p.h650,p.h650*1.05])
    # Retain the v7 4% falloff: no source for the claimed 29.5% at matching height/configuration.
    return h*(1-.04*roughness(terrain,z,p)/.16)

def background(p,terrain,z=Z):
    z=np.asarray(z,float);r=roughness(terrain,z,p)/.16
    iu=(.115+.21*r)*(z/.198)**(-p.gamma)
    lux=1.16-.8*r
    return iu,lux

def metrics(series,dt):
    series=np.asarray(series,float); n=series.shape[-1]
    means=series.mean(axis=-1); fl=series-means[...,None]
    acf=np.fft.irfft(abs(np.fft.rfft(fl,n=2*n,axis=-1))**2,n=2*n,axis=-1)[...,:n]/np.arange(n,0,-1)
    acf/=np.maximum(acf[...,0,None],1e-12)
    integrate=getattr(np,'trapezoid',None)
    if integrate is None:integrate=np.trapz
    lux=[]
    for row,u in zip(acf.reshape(-1,n),means.reshape(-1)):
        hit=np.flatnonzero(row[1:]<=0)
        stop=min(int(hit[0]+1) if len(hit) else n//4,n//4)
        lux.append(max(0.,float(u*integrate(row[:stop+1],dx=dt))))
    return {'u':means,'Iu':fl.std(axis=-1)/np.maximum(means,1e-6),'Lux':np.array(lux).reshape(means.shape)}

class Plant:
    def __init__(self,p=Params(),heights=Z):
        self.p=p; self.heights=np.asarray(heights,float).copy()
        if self.heights.ndim!=1 or np.any(self.heights<=0):raise ValueError('heights must be positive 1D')
        self.weights=np.exp(-.5*((self.heights[:,None]-ROW_Z[None,:])/p.width)**2)
        self.weights/=self.weights.sum(axis=1,keepdims=True)
        self.reset()
    def reset(self):
        self.k=0; self.N=None;self.F=None;self.Qslow=None;self.Pslow=None;self.q=None
        self.x=0.;self.xhistory=[];self.chistory=[];self.source_index=0;self.noise_state=None;self.rng=None
        self.valid=True;self.min_ratio=float('inf')
    def run(self,main,rows,terrain,duration,seed=None,sample=True):
        p=self.p;dt=1/p.fs;n=int(round(duration*p.fs))
        if n<=0 or abs(n*dt-duration)>1e-8:raise ValueError('duration not aligned to sample clock')
        main=np.asarray(main,float);rows=np.asarray(rows,float);terrain=np.asarray(terrain,float)
        if main.shape==():main=np.full(n,float(main))
        if main.shape!=(n,) or rows.shape!=(8,n) or terrain.shape!=(2,):
            raise ValueError('expected one main N (scalar or n samples), eight row time series (8,n), two Terraformer groups')
        if np.any((main<0)|(main>17)) or np.any((rows< -17)|(rows>20)) or np.any((terrain<0)|(terrain>.16)):
            raise ValueError('command outside envelope')
        if seed is not None and self.rng is None:self.rng=np.random.default_rng(seed)
        rng=self.rng if seed is not None else None
        if rng is not None:
            if self.noise_state is None:self.noise_state=np.zeros(len(self.heights))
            # One independent loading drift per sampled call, not per object lifetime.
            repeat=1+rng.normal(0,p.drift)
        h=profile(p,terrain,self.heights);iu,lux=background(p,terrain,self.heights)
        speed=np.empty((len(self.heights),n));qhist=np.empty(n);dly=np.empty(n)
        al_n=np.exp(-dt/p.main_tau);al_q=np.exp(-dt/p.tau_q);al_p=np.exp(-dt/p.tau_p)
        L=1/(18*p.tau_ref)
        for k in range(n):
            cmd=rows[:,k];nc=main[k]
            if self.k==0:
                self.N=nc;self.F=cmd.copy();self.Qslow=float(cmd.mean());self.Pslow=cmd-cmd.mean()
                fq=self.Qslow;self.q=float(equilibrium(self.N,fq,p))
                self.xhistory=[0.];self.chistory=[self.Pslow.copy()]
            # State refers to end of previous interval; current command can affect current output but not past output.
            self.N=al_n*self.N+(1-al_n)*nc
            self.F+=np.clip(cmd-self.F,-p.ffm_rate*dt,p.ffm_rate*dt)
            avg=float(self.F.mean());contrast=self.F-avg
            self.Qslow=al_q*self.Qslow+(1-al_q)*avg
            self.Pslow=al_p*self.Pslow+(1-al_p)*contrast
            fq=(1-p.s_q)*avg+p.s_q*self.Qslow
            cp=(1-p.s_p)*contrast+p.s_p*self.Pslow
            e=(1-p.b)*self.N**2+p.b*fq*abs(fq)
            for _ in range(2):self.q=max(0.,self.q+.5*dt*L*(e-self.q*self.q))
            self.x+=p.kappa*self.q*dt
            self.xhistory.append(self.x);self.chistory.append(cp.copy())
            source_x=max(0.,self.x-DISTANCE)
            # Strictly causal interpolation in travelled distance; initial history is the initial steady contrast.
            while self.source_index+1<len(self.xhistory) and self.xhistory[self.source_index+1]<=source_x:
                self.source_index+=1
            j=self.source_index
            if j+1<len(self.xhistory) and self.xhistory[j+1]>self.xhistory[j]:
                frac=(source_x-self.xhistory[j])/(self.xhistory[j+1]-self.xhistory[j])
                source=self.chistory[j]*(1-frac)+self.chistory[j+1]*frac
            else:source=self.chistory[j]
            vel=h*self.q+p.c*(self.weights@source)
            ratio=float(np.min(vel/np.maximum(h*self.q,1e-12)))
            self.min_ratio=min(self.min_ratio,ratio)
            if ratio<.5:self.valid=False
            if rng is not None:
                # AR(1) background with local integral-time proxy; noise state persists across calls via seeded RNG only
                if self.noise_state is None:self.noise_state=np.zeros(len(self.heights))
                alpha=np.exp(-dt*np.maximum(vel,.1)/np.maximum(lux,.05))
                self.noise_state=alpha*self.noise_state+np.sqrt(1-alpha**2)*rng.normal(size=len(vel))
                vel=repeat*(vel+self.noise_state*iu*np.maximum(vel,0))
            speed[:,k]=vel;qhist[k]=self.q;dly[k]=self.x
            self.k+=1
        if not sample:return {'duration_s':duration,'time_end_s':self.k*dt,'valid':self.valid,'min_ratio':self.min_ratio}
        return {'t':(np.arange(n)+self.k-n)*dt,'series':speed,'q':qhist,'travelled_m':dly,
                'valid':self.valid,'min_ratio':self.min_ratio}

def commands(p, main, mean_rows, amplitude, wavelength, terrain, duration, command_seed):
    """Generate the 27-input command; a shared phase spectrum makes rows coherent."""
    mean_rows=np.asarray(mean_rows,float);amplitude=np.asarray(amplitude,float)
    wavelength=np.asarray(wavelength,float);terrain=np.asarray(terrain,float)
    if any(x.shape!=(8,) for x in (mean_rows,amplitude,wavelength)) or terrain.shape!=(2,):
        raise ValueError('expected N, eight means, eight amplitudes, eight wavelengths, two Terraformer groups')
    if not(0<=main<=17) or np.any(amplitude<0) or np.any(wavelength<=0):
        raise ValueError('invalid 27-parameter command')
    n=int(round(duration*p.fs))
    if n<2 or abs(n/p.fs-duration)>1e-8:raise ValueError('duration not aligned with sample clock')
    rng=np.random.default_rng(command_seed)
    phase=rng.uniform(0,2*np.pi,n//2+1);phase[0]=0
    if n%2==0:phase[-1]=0
    freq=np.fft.rfftfreq(n,1/p.fs)
    rows=[]
    for mean,amp,lam in zip(mean_rows,amplitude,wavelength):
        # von Karman-like one-dimensional spectral shape, time scale lambda/6 s.
        spectral=(1+(freq*lam/6)**2)**(-5/12)
        spectral[0]=0
        signal=np.fft.irfft(spectral*np.exp(1j*phase),n=n)
        sd=signal.std()
        if sd<1e-12:raise ValueError('degenerate spectrum')
        rows.append(mean+amp*signal/sd)
    raw=np.asarray(rows);clipped=np.clip(raw,-17,20)
    return {'main':float(main),'rows':clipped,'terrain':terrain,
            'clip_fraction':float(np.mean(raw!=clipped))}

def periodic_rows(rows,n):
    rows=np.asarray(rows,float)
    if rows.ndim!=2 or rows.shape[0]!=8 or rows.shape[1]<2:
        raise ValueError('periodic rows must have shape (8,period_samples>=2)')
    if np.any((rows< -17)|(rows>20)):raise ValueError('periodic rows outside envelope')
    return rows[:,np.arange(n)%rows.shape[1]]

def score(p,main,rows,terrain,seeds=(1001,1002,1003),duration=1800.,
          amplitude=None,wavelength=None,command_seeds=(2001,2002,2003)):
    """Three fixed measurement and command seeds; drift disabled only in scoring."""
    values=[];valid=[];minimum=[];clips=[]
    p=replace(p,drift=0.)
    n=int(round(duration*p.fs));settle=int(round(120*p.fs))
    if len(command_seeds)!=len(seeds):raise ValueError('one command seed per measurement seed')
    for seed,cseed in zip(seeds,command_seeds):
        if amplitude is not None or wavelength is not None:
            if amplitude is None or wavelength is None:raise ValueError('amplitude and wavelength required together')
            cmd=commands(p,main,rows,amplitude,wavelength,terrain,duration+120.,cseed)
            series=cmd['rows'];clips.append(cmd['clip_fraction'])
        else:
            base=np.asarray(rows,float)
            if base.shape==(8,):base=base[:,None].repeat(2,axis=1)
            series=periodic_rows(base,n+settle);clips.append(0.)
        obj=Plant(p)
        # Continuous command phase across settling and sampling.
        obj.run(main,series[:,:settle],terrain,120.,sample=False)
        output=obj.run(main,series[:,settle:settle+n],terrain,duration,seed=seed)
        m=metrics(output['series'],1/p.fs)
        values.append(np.stack((m['u'],m['Iu'],m['Lux']),axis=0))
        valid.append(output['valid']);minimum.append(output['min_ratio'])
    a=np.stack(values)
    return {'u':a[:,0].mean(axis=0),'Iu':a[:,1].mean(axis=0),'Lux':a[:,2].mean(axis=0),
            'seed_sd':a.std(axis=0,ddof=1 if len(seeds)>1 else 0),'all_seeds':a,'valid':bool(all(valid)),
            'min_ratio':float(min(minimum)),'clip_fraction':clips}
