#!/usr/bin/env python3
"""Stage only the six immutable, hashed CRC GraphCast inputs for Colab."""
import hashlib
import json
import subprocess
from pathlib import Path

SRC = 'gdfull:GC37_R1R2_2024_inputs_20261117_v1/'
DST = 'gdrive:colab_cache/r234c_r1r2_inputs_20261117_v1/'
OUT = Path('./23_AI_Weather/06_Logs/k_gc37_prereg')

def cmd(*args):
    return subprocess.check_output(args, text=True).strip()

def remote_json(name):
    return json.loads(cmd('rclone', 'cat', SRC + name))

def copy(name):
    subprocess.run(['rclone', 'copyto', SRC + name, DST + name, '--immutable',
                    '--transfers', '2', '--checkers', '2', '--tpslimit', '5',
                    '--retries', '3'], check=True)
    a = cmd('rclone', 'md5sum', SRC + name).split()[0]
    b = cmd('rclone', 'md5sum', DST + name).split()[0]
    assert a == b and a != 'ERROR', (name, a, b)
    print('MD5_OK', name, a, flush=True)
    return {'file': name, 'md5': a}

trial = remote_json('INPUT_R1R2_trial_v2_SUMMARY.json')
rest = remote_json('INPUT_R1R2_rest_v3_SUMMARY.json')
assert trial['all_pass'] and rest['all_pass']
a = remote_json('INPUT_NETCDF_MANIFEST_trial_v2.json')
b = remote_json('INPUT_NETCDF_MANIFEST_rest_v3.json')
manifest = a + b
assert len(manifest) == 6 and len({x['cycle'] for x in manifest}) == 6
print('INPUT_MANIFEST', [(x['cycle'],x['bytes']) for x in manifest], flush=True)
names = [x['netcdf'] for x in manifest] + ['event_times_gc37.json','domain_bbox_gc37.json']
checks = [copy(n) for n in names]
summary = {'all_pass': True, 'trial_all_pass': trial['all_pass'], 'rest_all_pass': rest['all_pass'],
           'expected_cycles': 6, 'manifest': manifest,
           'source': SRC, 'destination': DST, 'transfer_md5': checks}
local = OUT / 'DRIVE_CACHE_R1R2_INPUTS_20261117.json'
with local.open('x') as f:
    json.dump(summary,f,indent=2)
subprocess.run(['rclone','copyto',str(local),DST + local.name,'--immutable'],check=True)
assert cmd('rclone','md5sum',str(local)).split()[0] == cmd('rclone','md5sum', DST + local.name).split()[0]
print('STAGE_DONE',local,flush=True)
