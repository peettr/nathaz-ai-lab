#!/usr/bin/env python3
"""Explicit Lead-go full-run launcher; all extraction & embedding on desktop."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
BASE=Path('./22_Lab/06_Logs/figure_kb')
LOCAL=Path('./ftkb_figures');HOST='[邮箱]'
REMOTE='./ftkb_figures'
SSH=['ssh','-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
def run(cmd):return subprocess.run(cmd,stdin=subprocess.DEVNULL,check=True)
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def remote(cmd):return subprocess.check_output(SSH+['-n',HOST,cmd],stdin=subprocess.DEVNULL,text=True).strip()
def main():
    p=argparse.ArgumentParser();p.add_argument('--lead-go',action='store_true');p.add_argument('--workers',type=int);p.add_argument('--pair-seed',type=int);a=p.parse_args()
    if not a.lead_go:raise SystemExit('STOP: 0069 completion and explicit Lead go required')
    if not a.workers or not a.pair_seed:raise SystemExit('Lead must supply --workers (8 OCR / 12 post-OCR) and --pair-seed')
    run(SSH+['-O','check',HOST])
    combined=BASE/'p14_pdfs_manifest_all.jsonl'
    entries=[json.loads(x) for x in (BASE/'p14_pdfs_manifest.jsonl').read_text().splitlines()]
    if len(entries)!=4676 or len({(x['library'],x['attachment']) for x in entries})!=4676:raise SystemExit('STOP: staged PDF manifest incomplete')
    if not combined.exists():combined.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in entries))
    elif list(map(json.loads,combined.read_text().splitlines()))!=entries:raise RuntimeError('manifest changed; refusing overwrite')
    if LOCAL.joinpath('figures_full.sqlite').exists():raise FileExistsError('refusing overwrite existing 工作站 result')
    for name in ('p14_pdfs_manifest_all.jsonl','p14_pdfs_work_map.jsonl'):
        run(['scp']+SSH[1:]+[str(BASE/name),HOST+':'+REMOTE+'/'+name])
        a_hash=digest(BASE/name);r_hash=remote('sha256sum '+REMOTE+'/'+name).split()[0]
        if a_hash!=r_hash:raise RuntimeError('manifest checksum mismatch '+name)
    cmd='export TMPDIR='+REMOTE+'/tmp PYTHONDONTWRITEBYTECODE=1; nice -n 10 ~/ftkb_text/venv/bin/python '+REMOTE+'/scripts_restart_20261016/full_desktop_v2.py --lead-go --workers '+str(a.workers)+' --pair-seed '+str(a.pair_seed)+' --manifest '+REMOTE+'/p14_pdfs_manifest_all.jsonl --work-map '+REMOTE+'/p14_pdfs_work_map.jsonl'
    run(SSH+['-n',HOST,cmd])
    compact_size=int(remote('stat -c %s '+REMOTE+'/full_v2/figures_compact.sqlite'))
    vector_size=int(remote('stat -c %s '+REMOTE+'/full_v2/vectors_full_v2.npy'))+int(remote('stat -c %s '+REMOTE+'/full_v2/vectors_full_v2.json'))
    if compact_size>=200_000_000 or vector_size>300_000_000:raise RuntimeError('size cap: DB/vector stay desktop; notify Lead')
    LOCAL.mkdir(parents=True,exist_ok=True)
    for source,target in [('figures_compact.sqlite','figures_full.sqlite'),('vectors_full_v2.npy','vectors_full_v2.npy'),('vectors_full_v2.json','vectors_full_v2.json')]:
        dest=LOCAL/target
        if dest.exists():raise FileExistsError(dest)
        run(['scp']+SSH[1:]+[HOST+':'+REMOTE+'/full_v2/'+source,str(dest)])
        if digest(dest)!=remote('sha256sum '+REMOTE+'/full_v2/'+source).split()[0]:raise RuntimeError('checksum mismatch '+target)
    report=BASE/'full'/'FULL_REPORT.md'
    report.parent.mkdir(parents=True,exist_ok=True)
    if report.exists():raise FileExistsError(report)
    run(['scp']+SSH[1:]+[HOST+':'+REMOTE+'/full_v2/FULL_REPORT.md',str(report)])
    print('full artifacts verified:',LOCAL/'figures_full.sqlite',LOCAL/'vectors_full_v2.npy',report)
if __name__=='__main__':main()
