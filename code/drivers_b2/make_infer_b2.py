#!/usr/bin/env python3
"""Stage isolated B2 Blackwell inference without touching B1 outputs."""
from pathlib import Path
import hashlib, json
here=Path(__file__).resolve().parent
b1=here.parent/'drivers_b1'
out=here/'infer_package_v1';out.mkdir(exist_ok=True)
base='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x'
src=(b1/'infer_b1_blackwell_8_v2.py').read_text()
src=src.replace('inputs_N1N3N4_v1','inputs_N8N9N10_v1')
src=src.replace('for event in (\'N1\',\'N3\',\'N4\'):',"for event in ('N8','N9','N10'):")
src=src.replace("if event == 'N4' and lead == '72h':\n                continue", "if False:\n                continue")
src=src.replace('assert len(planned)==8','assert len(planned)==9')
assert "inputs_N8N9N10_v1" in src and "('N8','N9','N10')" in src
p=out/'infer_b2_science_v1.py'
if p.exists(): assert p.read_text()==src
else:p.write_text(src)
wrap='''#!/usr/bin/env python3
import argparse, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--event',required=True,choices=('N8','N9','N10'));p.add_argument('--lead',required=True,choices=('24h','48h','72h'));a=p.parse_args()
spec=importlib.util.spec_from_file_location('science',ROOT/'infer_b2_science_v1.py');science=importlib.util.module_from_spec(spec);spec.loader.exec_module(science)
science.ROOT=ROOT
assert science.sha(science.PARAM)==science.EXPECTED
assert any(d.platform=='gpu' for d in science.jax.devices())
config=json.loads((ROOT/'event_times_bbox_gc37x.json').read_text())['events'];v=config[a.event]['leads'][a.lead];cycle=v['t0'].replace('-','').replace(':','').replace('T','')[:10]
science.run_one(a.event,a.lead,cycle,int(v['length_h']//6),config[a.event]['domain'])
'''
p=out/'run_single_b2_v1.py'
if p.exists():assert p.read_text()==wrap
else:p.write_text(wrap)
for event in ('N8','N9','N10'):
 for lead in ('24h','48h','72h'):
  root=f'{base}/infer_b2_{event}_{lead}_v1'
  sh=f'''#!/usr/bin/env bash
set -uo pipefail
ROOT={root}
cd "$ROOT" || exit 100
mkdir "$ROOT/attempt.claim" || exit 106
trap 'printf "%s\\n" "$?" > "$ROOT/infer.exitcode"' EXIT
export PYTHONUNBUFFERED=1 JAX_PLATFORMS=cuda XLA_PYTHON_CLIENT_PREALLOCATE=false
export LD_LIBRARY_PATH=/software/p/python/3.12.15/gcc/11.5.0/lib
PY="$ROOT/venv/bin/python"
test -f "$ROOT/run_single_b2_v1.py" || exit 101
test -x "$PY" || exit 102
"$PY" -m pip check || exit 103
nvidia-smi > "$ROOT/nvidia_smi.txt" || exit 104
"$PY" -c 'import jax,jaxlib,xarray,numpy,pandas; print(jax.__version__,jaxlib.__version__,xarray.__version__,numpy.__version__,pandas.__version__,jax.devices())' > "$ROOT/jax_devices.txt" || exit 105
"$PY" "$ROOT/run_single_b2_v1.py" --event {event} --lead {lead} || exit 107
'''
  sub=f'''universe = vanilla
executable = /bin/bash
arguments = {root}/run_b2.sh
initialdir = {root}
output = {root}/condor.out
error = {root}/condor.err
log = {root}/condor.log
request_cpus = 4
request_memory = 131072 MB
request_disk = 65536 MB
request_gpus = 1
requirements = (Machine == "qa-rtx6kbw-001.超算")
+JobBatchName = "R234c_GC37x_B2_{event}_{lead}"
+MaxRuntime = 7200
should_transfer_files = NO
queue 1
'''
  for filename,text in ((f'{event}_{lead}_run.sh',sh),(f'{event}_{lead}.sub',sub)):
   p=out/filename
   if p.exists():assert p.read_text()==text
   else:p.write_text(text)
for p in out.glob('*.py'): compile(p.read_text(),str(p),'exec')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256.json'}
p=out/'SHA256.json';text=json.dumps(manifest,indent=2)+'\n'
if p.exists():assert p.read_text()==text
else:p.write_text(text)
print(len(manifest),out)
