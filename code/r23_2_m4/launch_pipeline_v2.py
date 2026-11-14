#!/usr/bin/env python3
"""Detached one-session M4 sequence after the first training stage.
Stops at preregistered 18-cell loss gate; no rerun or result overwrite.
"""
from pathlib import Path
import subprocess
root=Path('/content/m4');root.mkdir(exist_ok=True)
(root/'pipeline_v2.launch').open('x').write('One M4 continuation, no replay\n')
shell='''#!/bin/bash
set -Eeuo pipefail
cd /content
finish() { rc=$?; printf '%s\\n' "$rc" > /content/m4/pipeline_v2.exit; touch /content/m4/pipeline_v2.done; exit "$rc"; }
trap finish EXIT
while [ ! -f /content/m4/train_v2.exit ]; do sleep 60; done
[ "$(cat /content/m4/train_v2.exit)" = 0 ] || { echo TRAIN_STAGE_FAILED; exit 10; }
ln -s /content/m4/gfs_train /content/m4/OKC/gfs_train
ln -s /content/m4/obs_train /content/m4/OKC/obs_train
python3 m4_collect.py okc_obs OKC test
python3 m4_collect.py gfs OKC test
python3 m4_collect.py gfs Swiss train
python3 m4_collect.py gfs Swiss test
python3 m4_weather.py
for net in OKC Swiss; do
 for delay in 4 3 6; do
  python3 m4_score.py --network "$net" --mode train --delay "$delay"
  python3 m4_score.py --network "$net" --mode test --delay "$delay"
 done
done
python3 - <<'CHECK'
from pathlib import Path
import pandas as pd
root=Path('/content/m4/output')
loss=True
for net in ('OKC','Swiss'):
 f=root/f'{net}_GFS_delay4_mae.csv'
 d=pd.read_csv(f);b=d[d.method=='B']
 assert len(b)==9 and set(b.lead_min)=={10,20,30,60,120,180,240,300,360}
 print('GATE',net,[(int(x.lead_min),round(x.D,4),round(x.D_hi,4)) for x in b.itertuples()],flush=True)
 loss &= bool((b.D_hi>=0).all())
(root/'stop_loss.txt').write_text(str(loss)+'\\n')
print('STOP_LOSS',loss,flush=True)
CHECK
if [ "$(cat /content/m4/output/stop_loss.txt)" = True ]; then echo STOP_AT_PREREGISTERED_GATE; exit 0; fi
python3 m4_aiwp.py OKC train
python3 m4_aiwp.py OKC test
python3 m4_aiwp.py Swiss train
python3 m4_aiwp.py Swiss test
for net in OKC Swiss; do
 python3 m4_score.py --network "$net" --mode train --delay 6 --source AIWP
 python3 m4_score.py --network "$net" --mode test --delay 6 --source AIWP
done
echo ALL_STAGES_DONE
'''
p=root/'run_all_v2.sh';p.write_text(shell);p.chmod(0o755)
log=(root/'pipeline_v2.log').open('x')
pid=subprocess.Popen(['/bin/bash',str(p)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True).pid
print('PIPELINE_PID',pid,'LOG',log.name,'MARKER',root/'pipeline_v2.done')
