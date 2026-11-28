"""Run on disposable Colab VM, logging evidence without replacing prior runs."""
import pathlib, subprocess, time, json, csv, os, traceback
P=pathlib.Path('/content/l264diag04'); T=P/'texas'; T.mkdir(exist_ok=True)
py=P/'venv/bin/python'
start=time.monotonic()
def run(label,args):
    with (P/(label+'.log')).open('x') as log:
        q=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
    if q.returncode: raise RuntimeError(f'{label} rc={q.returncode}; see {P/(label+".log")}')
    print('DONE',label,'elapsed',round(time.monotonic()-start,1),flush=True)
try:
    while not (P/'stage.done').exists():
        if (P/'stage.failed').exists():raise RuntimeError((P/'stage.failed').read_text()[-3000:])
        time.sleep(10)
    lookup={}
    with open('/content/Table4_IGBP_z0.csv') as f:
        for row in csv.DictReader(line for line in f if not line.startswith('#')):lookup[row['igbp_class']]=float(row['z0_m'])
    (T/'table4_z0.json').write_text(json.dumps(lookup))
    run('static_probe',[str(py),'/content/colab04_diag_static_probe.py'])
    run('build_static',[str(py),'/content/colab04_diag_build_static.py'])
    run('interpolation',[str(py),'/content/colab04_diag_interp.py'])
    # Stage script stores f00 reference only for the original west; shift predictions use common-grid comparison.
    for net in ('air','surface'):
        for variant,region in (('original','shift'),('shift','shift')):
            run(f'forecast_{net}_{variant}',[str(py),'/content/colab04_diag_forecast.py','--net',net,'--region',region,'--variant',variant,'--days','1'])
    run('comparison',[str(py),'/content/colab04_diag_compare.py'])
    (P/'diag.done').write_text('ok\n')
except BaseException:
    (P/'diag.failed').write_text(traceback.format_exc());traceback.print_exc();raise
