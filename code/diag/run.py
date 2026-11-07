import json,os,subprocess,time,shutil
T0=time.time(); BUDGET=330
W='/content/w'; OUT='/content/out'; os.makedirs(OUT,exist_ok=True); S={}
def st(n,c,cwd,lim):
    left=BUDGET-(time.time()-T0)
    if left<15: S[n]='skipped_budget'; return
    t=time.time()
    with open(f'{OUT}/{n}.log','w') as f:
        p=subprocess.Popen(c,shell=True,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try: rc=p.wait(timeout=min(lim,left))
        except subprocess.TimeoutExpired: os.killpg(p.pid,9); rc='timeout'
    S[n]={'rc':rc,'sec':round(time.time()-t,1)}; json.dump(S,open(f'{OUT}/summary.json','w'),indent=1); print(n,S[n],flush=True)
os.makedirs(W,exist_ok=True); subprocess.run('tar xzf /content/examples.tar.gz -C /content/w',shell=True)
s=f'{W}/examples/cfd/swe_nonlinear_pino'
st('install','pip install -q "nvidia-physicsnemo[sym]==2.2.2" hydra-core omegaconf h5py matplotlib scipy termcolor imageio',s,120)
st('swe_data','python download_data.py',s,60)
st('shape_check','cp /content/shape_check.py . && python shape_check.py',s,40)
o='max_epochs=2 movie.nmovies=0'
st('A_physicsnemo_unmodified',f'python train_swe_nl_pino.py {o} hydra.run.dir=./oA; rm -rf oA/checkpoints',s,60)
st('B_original_unmodified',f'python train_swe_nl_pino.py {o} loss.derivative=original hydra.run.dir=./oB; rm -rf oB/checkpoints',s,60)
p=s+'_patched'; shutil.copytree(s,p)
fn=f'{p}/train_utils/losses.py'; t=open(fn).read(); n=t.count('[1:-1]')
for k in ('Dh','Du','Dv'): t=t.replace(f'{k} = pde_{k}["{k}"][1:-1]',f'{k} = pde_{k}["{k}"]')
open(fn,'w').write(t); S['patch_count_before']=n
subprocess.run(f'diff {s}/train_utils/losses.py {fn} > {OUT}/patch.diff',shell=True)
st('C_physicsnemo_patched',f'python train_swe_nl_pino.py {o} hydra.run.dir=./oC; rm -rf oC/checkpoints',p,60)
S['total_sec']=round(time.time()-T0,1); json.dump(S,open(f'{OUT}/summary.json','w'),indent=1)
open('/content/run.done','w').write('done')
