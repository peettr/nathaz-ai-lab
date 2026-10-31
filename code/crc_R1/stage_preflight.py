#!/usr/bin/env python3
"""Stage and preflight R1, without any scheduler submission."""
import json, subprocess, hashlib, shlex
from pathlib import Path
D=Path(__file__).parent
M=json.loads((D/'manifest.json').read_text())
HOST='[邮箱]'
OPT=['-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
def call(args):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
 if p.returncode:raise RuntimeError(f'{args[0]} failed {p.returncode}: {p.stdout[:2000]}')
 return p.stdout
print(call(['ssh','-O','check','-o','ControlPath=./.ssh/sockets/[邮箱]',HOST]).strip(),flush=True)
# Confirm frozen CRC grader and baselines prior to touching any new root.
remote='sha256sum /groups/kareem/[用户]/L22_6/L22_6_T01_grade_v2_code/score_T01.py /groups/kareem/[用户]/L22_6/L22_6_T03_grade_v2_code/grade_T03.py /groups/kareem/[用户]/L22_6/L22_6_T03_v12_analysis_20261021_02/metrics_v12.json /groups/kareem/[用户]/L22_6/L22_6_T01_grade_v2_code/truth_C2.json'
print(call(['ssh','-n',*OPT,HOST,remote]),flush=True)
for r in M:
 root=r['root']; name=f"{r['model']}_{r['id']}"
 # Never stage over a prior root.
 call(['ssh','-n',*OPT,HOST,f'test ! -e {shlex.quote(root)} && mkdir -m 700 {shlex.quote(root)}'])
 for path in (r['archive'],r['run_script']):
  call(['scp',*OPT,path,f'{HOST}:{root}/'])
 arch=Path(r['archive']).name; script=Path(r['run_script']).name
 cmd=(f'cd {shlex.quote(root)} && sha256sum {shlex.quote(arch)} {shlex.quote(script)} && '
      f'tar -xzf {shlex.quote(arch)} && bash -n {shlex.quote(script)} && '
      f'qsub -w v {shlex.quote(script)} 2>&1 && '
      f'for f in candidate/* candidate/Make/*; do [ ! -f "$f" ] || sha256sum "$f"; done')
 report=call(['ssh','-n',*OPT,HOST,cmd])
 assert r['tar_sha256'] in report and r['script_sha256'] in report, name
 for rel,expected in r['input_sha256'].items():
  assert expected in report, (name,rel)
 (D/(name+'.preflight.txt')).write_text(report)
 print('PREFLIGHT',name,'OK',flush=True)
print('ALL_PREFLIGHT_OK',len(M),flush=True)
