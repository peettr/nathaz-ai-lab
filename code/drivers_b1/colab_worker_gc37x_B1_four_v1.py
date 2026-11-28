#!/usr/bin/env python3
"""CRC-verified R1/R2 inputs -> six TFIX forecasts and per-cycle Drive archive."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import urllib.parse
import urllib.request

R = Path('/content/r234c_gc37x_B1')
SRC = 'gdrive:colab_cache/r234c_gc37x_B1_four_inputs_20261124_v1/'
DEST = 'gdrive:colab_cache/r234c_gc37x_B1_forecasts_v1/'
LOG = R/'worker_gc37x_B1_four_v1.log'

def emit(*parts):
    R.mkdir(exist_ok=True)
    with LOG.open('a') as f:
        print(dt.datetime.now(dt.timezone.utc).isoformat(), *parts, file=f, flush=True)

def stage(label, argv):
    emit('START',label)
    with (R/(label+'.log')).open('x') as f:
        rc=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT).returncode
    emit('END',label,rc)
    if rc: raise RuntimeError((label,rc))

def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

try:
    assert not (R/'worker_gc37x_B1_four_v1.done').exists()
    assert Path('/root/.config/rclone/rclone.conf').is_file()
    stage('rclone_install',['bash','-lc','cd /content && curl -fsSLO https://downloads.rclone.org/v1.75.2/rclone-v1.75.2-linux-amd64.zip && curl -fsSL https://downloads.rclone.org/v1.75.2/SHA256SUMS | grep "rclone-v1.75.2-linux-amd64.zip" | sha256sum -c - && unzip -oq rclone-v1.75.2-linux-amd64.zip && install -m 755 rclone-v1.75.2-linux-amd64/rclone /usr/local/bin/rclone'])
    stage('deps',[sys.executable,'-m','pip','install','-q','netcdf4','dask','dm-haiku','chex','jraph','rtree','trimesh','dm-tree','dinosaur-dycore','boto3','xarray','xarray-tensorstore'])
    stage('clone',['git','clone','--depth','1','https://github.com/NOAA-EMC/graphcast.git','/content/r234c_graphcast_source'])
    stage('restore',['rclone','copy',SRC,str(R),'--transfers','2','--checkers','2','--tpslimit','5','--retries','3'])
    stage('restore_check',['rclone','check',SRC,str(R),'--checksum','--one-way'])
    manifest=json.loads((R/'INPUTS_B1_FOUR_MANIFEST.json').read_text())
    assert len(manifest)==4
    for x in manifest:
        p=R/x['netcdf']
        assert p.stat().st_size==x['bytes'] and digest(p)==x['sha256'],x
        emit('INPUT_HASH_OK',x['cycle'])
    assert (R/'event_times_bbox_gc37x.json').is_file()
    assert digest(R/'event_times_bbox_gc37x.json')==digest(Path('/content/event_times_bbox_gc37x.json'))
    for x in manifest:
        stage('tensor_gate_'+x['cycle'],[sys.executable,'/content/check_gc37x_inputs.py','graphcast',str(R/x['netcdf']),'--json',str(R/('TENSOR_GATE_'+x['cycle']+'.json'))])
    W=R/'weights'
    for stem in ['params/GraphCast - ERA5 1979-2017 - resolution 0.25 - pressure levels 37 - mesh 2to6 - precipitation input and output.npz','stats/diffs_stddev_by_level.nc','stats/mean_by_level.nc','stats/stddev_by_level.nc']:
        p=W/stem;p.parent.mkdir(parents=True,exist_ok=True)
        assert not p.exists(),p
        url='https://storage.googleapis.com/dm_graphcast/graphcast/'+urllib.parse.quote(stem)
        urllib.request.urlretrieve(url,p)
        emit('WEIGHT',stem,p.stat().st_size,digest(p))
    events=json.loads((R/'event_times_bbox_gc37x.json').read_text())['events']
    for entry in manifest:
            ev=entry['event'];lead=entry['lead']
            t0=dt.datetime.fromisoformat(events[ev]['leads'][lead]['t0'])
            end=dt.datetime.fromisoformat(events[ev]['end'])
            steps=int((end-t0).total_seconds()/21600)
            cycle=t0.strftime('%Y%m%d%H')
            assert cycle==entry['cycle']
            out=R/f'forecast_{cycle}_{steps}step'
            assert not out.exists(),out
            stage('infer_'+cycle,[sys.executable,'/content/run_gc37_raw_b1_v1.py','--cycle',cycle,'--event',ev,'--steps',str(steps),'--root',str(R),'--bbox','/content/event_times_bbox_gc37x.json'])
            files=sorted(out.glob('step_*.npz'))
            assert len(files)==steps,(cycle,len(files),steps)
            entries=[{'file':p.name,'bytes':p.stat().st_size,'sha256':digest(p)} for p in files]
            (out/'RAW_MANIFEST.json').write_text(json.dumps(entries,indent=2))
            emit('RAW_READY',ev,cycle,len(entries))
            stage('archive_'+cycle,['rclone','copy',str(out),DEST+cycle,'--transfers','2','--checkers','2','--tpslimit','5','--retries','3'])
            stage('archive_check_'+cycle,['rclone','check',str(out),DEST+cycle,'--checksum','--one-way'])
            emit('ARCHIVED',ev,cycle)
    (R/'worker_gc37x_B1_four_v1.done').write_text('SUCCESS\n')
    emit('SUCCESS_ALL')
except BaseException:
    (R/'worker_gc37x_B1_four_v1.failed').write_text(traceback.format_exc())
    emit('FAILED',traceback.format_exc()[-3000:])
    raise
