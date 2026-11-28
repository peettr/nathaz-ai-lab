"""01g: fixed 01f physics, statistical spin-up gate on 8 post-discard blocks.
GPU-only payload. All gate observations and checks are JSON lines on stdout.
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from flow_stage1_01f import build, spectrum_fraction

def gate(samples):
    # Eight adjacent, equal-length blocks. The regression checks the segment
    # means, not each raw sample (which would be pseudoreplication).
    assert samples.shape[0] % 8 == 0
    parts = samples.reshape(8, -1, 12)
    means = parts.mean(axis=1)
    x = np.arange(8, dtype=float); xc = x - x.mean()
    slope = (xc[:,None] * (means-means.mean(axis=0))).sum(axis=0) / (xc*xc).sum()
    residual = means - (means.mean(axis=0) + xc[:,None]*slope)
    slope_se = np.sqrt((residual**2).sum(axis=0)/6/(xc*xc).sum())
    # two-sided 95% t critical for 6 df, frozen before results
    tcrit = 2.446912
    sig = np.abs(slope) > tcrit*slope_se
    seg_se = means.std(axis=0,ddof=1)/np.sqrt(8)
    drift = np.abs(slope)*7
    # Primary rule: either all 12 nonsignificant slopes, OR all 12 drift
    # magnitudes strictly less than twice their segment-mean SE.
    slope_pass = bool(np.all(~sig))
    drift_pass = bool(np.all(drift < 2*seg_se))
    avg = samples.mean(axis=0)
    rms = samples.std(axis=0,ddof=1)
    ratios = rms/np.maximum(np.abs(avg),1e-8)
    peaks = [spectrum_fraction(samples[:,i]) for i in range(12)]
    pulse_count = sum(r >= .05 and p is not None and p < .5 for r,p in zip(ratios,peaks))
    return dict(spinup_pass=slope_pass or drift_pass, slope_pass=slope_pass,
                drift_pass=drift_pass, slope=slope.tolist(), slope_se=slope_se.tolist(),
                slope_significant=sig.tolist(), total_drift=drift.tolist(),
                twice_segment_mean_se=(2*seg_se).tolist(),
                pulse_count=pulse_count,pulse_pass=pulse_count>=6,
                fluctuation_ratios=ratios.tolist(),peak_power_fraction=peaks,
                qualified=(slope_pass or drift_pass) and pulse_count>=6)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True);p.add_argument('--scratch',required=True)
    p.add_argument('--dtype',choices=('float32','float64'),required=True)
    p.add_argument('--max-steps',type=int,default=503808)
    args=p.parse_args()
    assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    out=Path(args.out); out.mkdir(parents=True,exist_ok=False)
    scratch=Path(args.scratch);scratch.mkdir(parents=True,exist_ok=False)
    nx,ny,re,seed,tau,step=384,128,3000,26022,256,512
    discard=100352; segment=25600; first=discard+8*segment
    state,run,nu,control=build(nx,ny,re,args.dtype,'KBC')
    rng=np.random.default_rng(seed); alpha=np.exp(-1/tau); previous=np.zeros(8)
    samples=[]; times=[]; start=time.perf_counter()
    print(json.dumps(dict(stage='config',nx=nx,ny=ny,re=re,collision='KBC',
        seed=seed,noise_ar1_alpha=float(alpha),nominal_inlet_rms_fraction=.1,
        discard=discard,segment=segment,first_check=first,max_steps=args.max_steps,
        dtype=args.dtype,device=str(jax.devices()[0]))),flush=True)
    for stop in range(step,args.max_steps+1,step):
        white=rng.standard_normal((step,8));noise=np.empty_like(white)
        for i in range(step):
            previous=alpha*previous+np.sqrt(1-alpha*alpha)*white[i]
            noise[i]=previous
        tick=time.perf_counter()
        state,obs=run(state,jnp.asarray(noise,dtype=control.dtype),control)
        block=np.asarray(obs.block_until_ready());times.append(time.perf_counter()-tick)
        if not np.isfinite(block).all():
            print(json.dumps(dict(stage='unstable',steps=stop)),flush=True)
            raise SystemExit(43)
        if stop>discard: samples.append(block)
        if stop>=first and (stop-first)%(segment*2)==0:
            # Most recent eight equal segments (>=200k post-discard history).
            series=np.concatenate(samples[-(8*segment//step):])
            result=gate(series)
            print(json.dumps(dict(stage='gate',steps=stop,**result)),flush=True)
            # Node-local diagnostic snapshot, never an undocumented shared write.
            np.save(scratch/f'state_{args.dtype}_{stop}.npy',np.asarray(state[0]))
            np.save(scratch/f'lag_{args.dtype}_{stop}.npy',np.asarray(state[1]))
            if result['qualified']:
                np.save(out/f'state_{args.dtype}.npy',np.asarray(state[0]))
                np.save(out/f'lag_{args.dtype}.npy',np.asarray(state[1]))
                print(json.dumps(dict(stage='spinup_saved',steps=stop,
                    hot_forward_s_per_step=float(np.mean(times[-16:])/step))),flush=True)
                break
    else:
        print(json.dumps(dict(stage='final',qualified=False,steps=args.max_steps,
            elapsed_seconds=time.perf_counter()-start)),flush=True)
        raise SystemExit(42)
    # Post-spinup probe series remains in node-local scratch; retain only the
    # compact batch statistics in the persistent run directory.
    post=[]
    for _ in range(256): # 131072 steps after the qualified state
        white=rng.standard_normal((step,8));noise=np.empty_like(white)
        for i in range(step):
            previous=alpha*previous+np.sqrt(1-alpha*alpha)*white[i]
            noise[i]=previous
        state,obs=run(state,jnp.asarray(noise,dtype=control.dtype),control)
        post.append(np.asarray(obs.block_until_ready()))
    np.save(scratch/f'post_probe_{args.dtype}.npy',np.concatenate(post))
    print(json.dumps(dict(stage='postspinup',steps=131072,
        elapsed_seconds=time.perf_counter()-start)),flush=True)
if __name__=='__main__':main()
