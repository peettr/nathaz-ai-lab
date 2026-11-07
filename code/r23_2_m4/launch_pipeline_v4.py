#!/usr/bin/env python3
"""Restore saved M4 training snapshot; launch one detached continuation."""
import os, subprocess
from pathlib import Path
root=Path('/content/m4')
assert (root/'train_pairs.parquet').is_file()
assert len(list((root/'gfs_train').glob('*.csv')))>1400
assert (root/'coefficients.json').is_file()
assert (root/'OKC/gfs_train').is_symlink() and (root/'OKC/obs_train').is_symlink()
(root/'pipeline_v4.launch').open('x').write('restored snapshot; holdout unread at launch\n')
script=r'''#!/bin/bash
set -Eeuo pipefail
cd /content
finish() { rc=$?; printf '%s\n' "$rc" > /content/m4/pipeline_v4.exit; touch /content/m4/pipeline_v4.done; exit "$rc"; }
trap finish EXIT
checkpoint() {
 local label="$1"; shift
 tar -czf "/content/m4/checkpoint_${label}.tgz.partial" -C /content/m4 "$@"
 mv "/content/m4/checkpoint_${label}.tgz.partial" "/content/m4/checkpoint_${label}.tgz"
 echo CHECKPOINT "$label" "$(stat -c %s "/content/m4/checkpoint_${label}.tgz")"
}
python3 m4_collect.py okc_obs OKC test
checkpoint okc_obs_test OKC/obs_test
python3 m4_collect.py gfs OKC test
checkpoint okc_gfs_test OKC/gfs_test
python3 m4_collect.py gfs Swiss train
checkpoint swiss_gfs_train Swiss/gfs_train
python3 m4_collect.py gfs Swiss test
checkpoint swiss_gfs_test Swiss/gfs_test
python3 m4_weather.py
checkpoint weather OKC/weather_test.csv OKC/weather_positive_reports.csv
for net in OKC Swiss; do
 for delay in 4 3 6; do
  python3 m4_score.py --network "$net" --mode train --delay "$delay"
  python3 m4_score.py --network "$net" --mode test --delay "$delay"
 done
done
checkpoint gfs_pairs pairs output OKC/model_gfs_delay4.json OKC/model_gfs_delay3.json OKC/model_gfs_delay6.json Swiss/model_gfs_delay4.json Swiss/model_gfs_delay3.json Swiss/model_gfs_delay6.json
python3 - <<'CHECK'
from pathlib import Path
import pandas as pd
root=Path('/content/m4/output');loss=True
for net in ('OKC','Swiss'):
 d=pd.read_csv(root/f'{net}_GFS_delay4_mae.csv');b=d[d.method=='B']
 assert len(b)==9 and set(b.lead_min)=={10,20,30,60,120,180,240,300,360}
 print('GATE',net,[(int(x.lead_min),round(x.D,4),round(x.D_hi,4)) for x in b.itertuples()],flush=True)
 loss &= bool((b.D_hi>=0).all())
(root/'stop_loss.txt').write_text(str(loss)+'\n')
print('STOP_LOSS',loss,flush=True)
CHECK
if [ "$(cat /content/m4/output/stop_loss.txt)" = True ]; then echo STOP_AT_PREREGISTERED_GATE; exit 0; fi
for net in OKC Swiss; do
 for split in train test; do
  python3 m4_aiwp.py "$net" "$split"
  checkpoint "$(echo "$net" | tr '[:upper:]' '[:lower:]')_aiwp_${split}" "$net/aiwp_${split}"
 done
done
for net in OKC Swiss; do
 python3 m4_score.py --network "$net" --mode train --delay 6 --source AIWP
 python3 m4_score.py --network "$net" --mode test --delay 6 --source AIWP
done
checkpoint final pairs output
echo ALL_STAGES_DONE
'''
p=root/'run_all_v4.sh';p.write_text(script);p.chmod(0o755)
log=(root/'pipeline_v4.log').open('x')
pid=subprocess.Popen(['/bin/bash',str(p)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True).pid
print('PIPELINE_PID',pid,'LOG',log.name,'MARKER',root/'pipeline_v4.done')
