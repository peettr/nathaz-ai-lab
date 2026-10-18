"""One-time 64 MiB Colab upload with explicit receipt and no retry."""
from pathlib import Path
import hashlib, subprocess, sys, time
ROOT=Path('./22_Lab/06_Logs/cfd_scaling')
SOURCE=ROOT/'v6s2_stage_1015/all_data.pt'
SESSION='wx-urbantales-v6s2-1015'
EXPECTED='494c85166bfc958449dcf753467675cf8d6da429c7edad4a74ec740210c6a5b9'
CLI=['colab','--auth','oauth2']

def call(*args):
    p=subprocess.run(CLI+list(args),stdin=subprocess.DEVNULL,text=True,capture_output=True,timeout=360)
    print(args,p.returncode,p.stdout[-1000:],p.stderr[-1000:],flush=True)
    if p.returncode: raise RuntimeError(str(args))

assert SOURCE.stat().st_size==4321275076
h=hashlib.sha256()
with SOURCE.open('rb') as f:
    for chunk in iter(lambda:f.read(2**20),b''): h.update(chunk)
assert h.hexdigest()==EXPECTED
print('SOURCE_OK',SOURCE.stat().st_size,h.hexdigest(),flush=True)
part=ROOT/'v6s2_stage_1015/upload_part.tmp'
assert not part.exists()
with SOURCE.open('rb') as f:
    i=0
    while chunk:=f.read(64*1024*1024):
        i+=1
        with part.open('xb') as o:o.write(chunk)
        try:call('upload','-s',SESSION,str(part),f'/content/v6part{i:03d}')
        finally:part.unlink()
        if i%4==0:
            ping=subprocess.run(CLI+['exec','-s',SESSION,'--timeout','120'], input="print('UPLOADING')\n", text=True,capture_output=True,timeout=150)
            print('PING',ping.returncode,ping.stdout[-300:],ping.stderr[-300:],flush=True)
            if ping.returncode: raise RuntimeError('keepalive probe failed')
        print('PART_DONE',i,flush=True)
assert i==65
print('ALL_PARTS_UPLOADED',i,flush=True)
