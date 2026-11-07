import json, os, subprocess, time, sys, shutil
T0=time.time(); BUDGET=1680  # 28 min 总墙钟，约 2.5 CU
W='/content/w'; OUT='/content/out'; os.makedirs(OUT,exist_ok=True)
S={'stages':{}}
def save(): json.dump(S,open(f'{OUT}/summary.json','w'),ensure_ascii=False,indent=1)
def st(name,cmd,cwd,limit):
    left=BUDGET-(time.time()-T0)
    if left<30:
        S['stages'][name]={'rc':'skipped_budget'}; save(); print('SKIP',name,flush=True); return False
    t=time.time(); print(f'=== {name} start {t-T0:.0f}s',flush=True)
    with open(f'{OUT}/{name}.log','w') as f:
        p=subprocess.Popen(cmd,shell=True,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try: rc=p.wait(timeout=min(limit,left))
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,9); rc='timeout'
    S['stages'][name]={'rc':rc,'sec':round(time.time()-t,1)}; save()
    print(f'=== {name} rc={rc} {time.time()-t:.0f}s',flush=True)
    return rc==0
os.makedirs(W,exist_ok=True)
subprocess.run('tar xzf /content/examples.tar.gz -C /content/w; nvidia-smi > /content/out/nvidia_smi.txt',shell=True)
ok=st('install','pip install -q "nvidia-physicsnemo[sym]==2.2.2" hydra-core omegaconf h5py "gdown>=5.2.2" matplotlib scipy termcolor imageio && pip freeze > /content/out/pip_freeze.txt && python -c "import physicsnemo,physicsnemo.sym,torch;from physicsnemo.sym.eq.phy_informer import PhysicsInformer;print(physicsnemo.__version__,torch.__version__,torch.cuda.get_device_name(0))"','/content',420)
d=f'{W}/examples/cfd/darcy_physics_informed'; s=f'{W}/examples/cfd/swe_nonlinear_pino'
if ok:
    if st('darcy_data','python download_data.py',d,300):
        st('darcy_train','python darcy_physics_informed_fno.py max_epochs=5',d,420)
    if st('swe_data','python download_data.py',s,300):
        st('swe_train','python train_swe_nl_pino.py max_epochs=3',s,480)
for root,dest in ((d,'darcy'),(s,'swe')):
    os.makedirs(f'{OUT}/{dest}',exist_ok=True)
    o=f'{root}/outputs_pino'
    if os.path.isdir(o):
        fs=[]
        for r,_,n in os.walk(o):
            for x in n:
                p=os.path.join(r,x); fs.append((p,os.path.getsize(p)))
                if x.endswith(('.png','.yaml','.log')) and os.path.getsize(p)<3e6: shutil.copy(p,f'{OUT}/{dest}/')
        S[dest+'_files']=[(p.replace(o,''),z) for p,z in fs][:200]
S['total_sec']=round(time.time()-T0,1); save()
open('/content/run.done','w').write('done')
