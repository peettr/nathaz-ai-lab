"""01p pilot: frozen random commands, original mean-SE denominator, one-point FD cost."""
import json, time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64', True)
import jax.numpy as jnp
from pilot_01m import initial, device_peak
from checkpoint_pilot_01i import correlated_noise
from steady_windows_01f import windows
from stage2_01p import WIDTHS

ROOT=Path('/groups/kareem/[用户]/L26_22_DIFFLBM_20261114/armA')
OUT=ROOT/'run_01p/pilot/pilot.jsonl'
NOMINAL=np.r_[np.full(8,.05),np.full(8,.005),[.025,.04]]
COMMANDS=np.random.default_rng(26220).uniform(.8*NOMINAL,1.2*NOMINAL,size=(5,18))
assert COMMANDS.shape==(5,18) and np.all((COMMANDS[:,:8]>=.003)&(COMMANDS[:,:8]<=.09))
def emit(**row):
    with OUT.open('a',buffering=1) as f:f.write(json.dumps(row,allow_nan=False,sort_keys=True)+'\n')
def main():
    if OUT.exists():raise FileExistsError(OUT)
    assert len(jax.devices())==1 and jax.devices()[0].platform=='gpu'
    emit(stage='commands',seed=26220,noise_seed=26031,values=COMMANDS.tolist(),nominal=NOMINAL.tolist())
    root=ROOT/'run_01l/bgk_stage1/qualified'
    st,chunk,cmd=initial(root,'float32')
    noise=correlated_noise(262144,26025,cmd.dtype)
    observations=[]
    for i in range(0,262144,512):
        st,y=chunk(st,noise[i:i+512],cmd)
        observations.append(np.asarray(y.block_until_ready()))
    data=np.concatenate(observations)
    for denominator in (.023,.05):
        for key,T,rows in windows(data,batch=2560,denominator=denominator):
            emit(stage='windows',denominator=denominator,metric=key,T=T,last=rows[-1],n=262144)
    st64,chunk64,cmd64=initial(root,'float64')
    base=np.asarray(COMMANDS[0],dtype=np.float64)
    step=.01
    offsets=step*WIDTHS*np.eye(18)
    inp=jnp.asarray(np.r_[base+offsets,base-offsets],dtype=cmd64.dtype)
    noise=correlated_noise(74240,26031,cmd64.dtype)
    # The pilot uses 840 steps; the full job re-compiles for the actual T.
    from stage2_01p import fd_prefixes_at
    task=jax.jit(jax.vmap(lambda x:fd_prefixes_at(st64,chunk64,noise[:840],x,(840,))))
    start=time.perf_counter(); a=task(inp).block_until_ready(); cold=time.perf_counter()-start
    start=time.perf_counter(); b=task(inp).block_until_ready(); hot=time.perf_counter()-start
    emit(stage='fd_sample',T=840,batch=36,point=0,cold_s=cold,hot_s=hot,
         finite=bool(np.isfinite(np.asarray(b)).all()),peak=device_peak(jax.devices()[0]))
    emit(stage='complete')
if __name__=='__main__':main()
