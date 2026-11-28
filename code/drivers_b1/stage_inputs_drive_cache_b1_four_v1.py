#!/usr/bin/env python3
"""Copy four immutable CRC-verified NetCDF inputs into Colab-visible Drive cache."""
import hashlib, json, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
SRC='gdfull:GC37x_B1_four_inputs_20261124_v1/'
DST='gdrive:colab_cache/r234c_gc37x_B1_four_inputs_20261124_v1/'
manifest=json.loads((HERE/'INPUTS_B1_FOUR_MANIFEST.json').read_text())
assert len(manifest)==4 and len({x['cycle'] for x in manifest})==4

def md5(remote):
    return subprocess.check_output(['rclone','md5sum',remote],text=True).split()[0]
for name in [x['netcdf'] for x in manifest]+['event_times_bbox_gc37x.json']:
    subprocess.run(['rclone','copyto',SRC+name,DST+name,'--immutable','--transfers','2','--checkers','2','--tpslimit','5','--retries','3'],check=True)
    source,dest=md5(SRC+name),md5(DST+name)
    assert source==dest and source!='ERROR',(name,source,dest)
    print('MD5_OK',name,source,flush=True)
name='INPUTS_B1_FOUR_MANIFEST.json'
subprocess.run(['rclone','copyto',str(HERE/name),DST+name,'--immutable'],check=True)
assert md5(str(HERE/name))==md5(DST+name)
print('STAGE_DONE',DST,flush=True)
