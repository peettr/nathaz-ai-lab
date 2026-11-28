import json, os, sys, subprocess, time
from pathlib import Path
import numpy as np
P=Path('/content/a3_b_1014');sys.path.insert(0,str(P/'code'))
import segment_b_run as b,segment_a_run as a
from wind_field_probe import CASES
b.BASE=P/'base';b.ROOT=P/'runs';b.SRC=P/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'base/rosco210_ff_build_guo_v2/libdiscon.so';a.CURVE=P/'base/segment_a_v4_curve.txt'
b.ROOT.mkdir(exist_ok=True)
seed_dir=b.ROOT/'I_near_s112';seed_dir.mkdir(exist_ok=False)
p=b.make_seed(CASES[0],112,seed_dir)
# Same padding correction as v4, retain raw separately.
b.phase_correct_bts(seed_dir/'wind.bts',seed_dir/'wind_corrected.bts');(seed_dir/'wind.bts').rename(seed_dir/'wind_unshifted.bts');(seed_dir/'wind_corrected.bts').rename(seed_dir/'wind.bts')
row=dict(case='I_near',seed=112,group='G1_instant',trigger_abs_s=p['trigger_abs_s']['G1_instant'],actual_lead_s=0,start_abs_s=p['start_abs_s'],end_abs_s=p['end_abs_s'],source=str(seed_dir))
print('provenance',p,flush=True)
dest=b.stage(row);env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='0')
t0=time.monotonic()
with (dest/'openfast.log').open('w') as f: r=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600)
print('pilot returncode',r.returncode,'wall',time.monotonic()-t0,'logtail',(dest/'openfast.log').read_text()[-1200:],flush=True)
assert r.returncode==0
from analyze_segment_b import read_out,measures
d=read_out(dest/'NREL-5MW.out');m=measures(d,p,p['start_abs_s'])
result={'provenance':p,'metric':m,'wall_s':time.monotonic()-t0,'wind_file_size':(seed_dir/'wind.bts').stat().st_size}
(P/'pilot.json').write_text(json.dumps(result,indent=2))
print('PILOT_METRICS',m,flush=True)
