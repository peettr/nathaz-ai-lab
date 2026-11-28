#!/usr/bin/env python3
import csv, subprocess, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parent
cols=('step','mass_fluid_lattice','px_fluid_lattice','ground_drag_snapshot',
      'eligible_native_columns','ground_drag_integral_10','ground_drag_integral_50')
with tempfile.TemporaryDirectory(dir=root) as d:
    d=Path(d);p=d/'ledger.csv';force=1e-7;volume=256*128*64
    rows=[]
    for s in (0,1000,2000):
        rows.append((s,100.0,10.0+force*volume*s-0.1*s,0.1,256*128,0.1*s,0.1*s))
    def write(rows):
        with p.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(cols);w.writerows(rows)
    def check(mode,expect,**kw):
        args=[sys.executable,str(root/'assert_ledger.py'),str(p),'--mode',mode,'--out',str(d/(mode+'.json'))]
        for k,v in kw.items():args.extend(('--'+k.replace('_','-'),str(v)))
        r=subprocess.run(args,capture_output=True,text=True)
        print(mode,'exit',r.returncode,'expected',expect,r.stdout.strip(),r.stderr.strip(),flush=True)
        assert r.returncode==expect
    write(rows)
    check('a1a',0);check('a1b',2);check('a3',0)
    check('a7',0,force=force,half_steps=1000,group='t15')
    bad=list(rows);bad[1]=(*bad[1][:2],bad[1][2]+3.0,*bad[1][3:]);write(bad)
    check('a7',2,force=force,half_steps=1000,group='t15')
    bad=list(rows);bad[0]=(*bad[0][:4],0,*bad[0][5:]);write(bad)
    check('a3',2)
print('FIXTURE_PASS: positive and negative gates only, not device evidence')
