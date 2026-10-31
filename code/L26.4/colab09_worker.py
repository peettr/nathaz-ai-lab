"""Disposable Colab run: stage, equivalence gate, budget gate, n=17."""
import json, os, pathlib, re, subprocess, sys, time, traceback
P=pathlib.Path('/content/l264surface09'); R=P/'AERO_ODE'; P.mkdir(exist_ok=True)
def run(label, args, env=None):
    start=time.monotonic()
    with (P/f'{label}.log').open('x') as log:
        result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env)
    dt=time.monotonic()-start
    print('STEP',label,'return',result.returncode,'seconds',round(dt,2),flush=True)
    if result.returncode: raise RuntimeError(f'{label} failed ({result.returncode}): '+(P/f'{label}.log').read_text()[-1800:])
    return dt
try:
    stage=run('stage',[sys.executable,'/content/l264stage09.py'])
    install=run('install',[sys.executable,'/content/l264install09.py'])
    py=str(P/'venv/bin/python'); script=R/'AERO_Surface_WD/test_film_00z_RMSE.py'
    env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='0',XLA_FLAGS='--xla_gpu_autotune_level=0',QUICK_MAX_BATCHES='1',QUICK_RESULT_DIR=str(P/'pilot_result'),MPLBACKEND='Agg',PYTHONUNBUFFERED='1')
    pilot=run('pilot',[py,str(script)],env)
    text=(P/'pilot.log').read_text()
    hit=re.search(r'Batch\s+0/\d+\s*\|\s*Init:\s*2024/04/01/00\s*\|\s*Loss:\s*([\d.]+)',text)
    if not hit or 'Evaluation Complete' not in text:raise RuntimeError('pilot incomplete or wrong date')
    loss=float(hit.group(1)); ref=.33871; diff=abs(loss-ref)/ref
    eq={'ours':loss,'colab02':ref,'official':.33861,'relative_difference':diff,'threshold':.001,'stage_seconds':stage,'install_seconds':install,'pilot_seconds':pilot}
    (P/'equivalence.json').write_text(json.dumps(eq,indent=2)+'\n')
    print('EQUIVALENCE',json.dumps(eq),flush=True)
    if diff>.001:raise RuntimeError('EQUIVALENCE_GATE_FAILED')
    (P/'equivalence.done').write_text('passed\n')
    print('WAITING_BUDGET_GATE',flush=True)
    while not (P/'budget_go').exists():
        if (P/'budget_stop').exists():raise RuntimeError('budget stop')
        time.sleep(10)
    # Full-window paths contain symlinks only to days 11..30; original inputs stay intact.
    F=P/'fullroot'; F.mkdir(exist_ok=False)
    for x in R.iterdir():
        if x.name!='data':(F/x.name).symlink_to(x,target_is_directory=x.is_dir())
    for branch in ['era5_test/2024/04','hrrr_test/04']:(F/'data'/branch).mkdir(parents=True)
    (F/'data/hrrr_stat').symlink_to(R/'data/hrrr_stat',target_is_directory=True)
    for day in range(11,31):
        for branch in ['era5_test/2024/04','hrrr_test/04']:
            source=R/'data'/branch/(f'{day:02d}.h5' if branch.startswith('hrrr_') else f'{day:02d}')
            target=F/'data'/branch/source.name
            if not source.exists():raise RuntimeError('missing day '+str(source))
            target.symlink_to(source,target_is_directory=source.is_dir())
    env['QUICK_MAX_BATCHES']='17';env['QUICK_RESULT_DIR']=str(P/'surface_result')
    wrapper="import sys,runpy;sys.path.insert(0,%r);import common.paths;from pathlib import Path;common.paths.ROOT=Path(%r);runpy.run_path(%r,run_name='__main__')"%(str(R),str(F),str(script))
    full=run('surface',[py,'-c',wrapper],env)
    text=(P/'surface.log').read_text()
    if 'Evaluation Complete [00Z Only, Surface Variables] (17 batches' not in text or 'Init: 2024/04/11/00' not in text:raise RuntimeError('not exactly 17 correct starts')
    (P/'surface_meta.json').write_text(json.dumps({'full_seconds':full,'sample_count':17,'equivalence':eq})+'\n')
    (P/'run.done').write_text('ok\n')
except BaseException:
    (P/'run.failed').write_text(traceback.format_exc());traceback.print_exc();raise
