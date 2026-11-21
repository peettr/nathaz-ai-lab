#!/usr/bin/env python3
"""Complete Zotero fallback re-render and fixed-seed review cards on restored desktop root."""
import hashlib, os, subprocess
from pathlib import Path
BASE=Path('./22_Lab/06_Logs/figure_kb')
LOCAL=Path('./ftkb_figures')
HOST='[邮箱]'; REMOTE='./ftkb_figures'
SSH=['ssh','-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
def call(a): subprocess.run(a,stdin=subprocess.DEVNULL,check=True)
def remote(s): return subprocess.check_output(SSH+['-n',HOST,s],stdin=subprocess.DEVNULL,text=True).strip()
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def push(src,dst):
 if remote('test -e '+dst+' && echo exists || echo missing')=='exists':
  if digest(src)!=remote('sha256sum '+dst).split()[0]:raise FileExistsError(dst)
  return
 call(['scp']+SSH[1:]+[str(src),HOST+':'+dst]);assert digest(src)==remote('sha256sum '+dst).split()[0]
def main():
 call(SSH+['-O','check',HOST]);m=BASE/'p14_pdfs_manifest.jsonl'
 if len(m.read_text().splitlines())!=4676:raise RuntimeError('stage incomplete')
 remote('mkdir -p '+REMOTE+'/tmp '+REMOTE+'/pilot_v3b/thumbs '+REMOTE+'/scripts_restart_20261016')
 for name in ('figure_pipeline_v3.py','rerender_fallback_v3.py','make_pairs_20_v3.py','make_pairs_v2.py','full_desktop_v2.py','build_vectors_full_v2.py','figsearch_full_desktop_v2.py'):
  push(BASE/'scripts'/name,REMOTE+'/scripts_restart_20261016/'+name)
 push(m,REMOTE+'/p14_pdfs_manifest.jsonl')
 push(BASE/'p14_pdfs_work_map.jsonl',REMOTE+'/p14_pdfs_work_map.jsonl')
 source=LOCAL/'pilot_v2/local.sqlite';dest=REMOTE+'/pilot_v3b/source_local_v2.sqlite';push(source,dest)
 output=REMOTE+'/pilot_v3b/zotero.sqlite'
 if remote('test -e '+output+' && echo exists || echo missing')=='exists':raise FileExistsError(output)
 cmd='export TMPDIR='+REMOTE+'/tmp PYTHONDONTWRITEBYTECODE=1; nice -n 10 ~/ftkb_text/venv/bin/python '+REMOTE+'/scripts_restart_20261016/rerender_fallback_v3.py --source-db '+dest+' --out-db '+output+' --root '+REMOTE+'/pilot_v3b --manifest '+REMOTE+'/p14_pdfs_manifest.jsonl --library Zotero'
 print(remote(cmd),flush=True)
 cmd='export TMPDIR='+REMOTE+'/tmp PYTHONDONTWRITEBYTECODE=1; nice -n 10 ~/ftkb_figures/venv/bin/python '+REMOTE+'/scripts_restart_20261016/make_pairs_20_v3.py --台式机 '+REMOTE+'/pilot_v3b/desktop.sqlite --endnote-db '+REMOTE+'/pilot_v3b/endnote.sqlite --zotero-db '+output+' --root '+REMOTE+'/pilot_v3b --seed 20261017'
 print(remote(cmd),flush=True)
 pilot=BASE/'pilot';out=pilot/'pairs_20_v3'
 if out.exists() or (pilot/'pairs_20_v3_cards.csv').exists():raise FileExistsError('local cards exist')
 call(['scp']+SSH[1:]+[HOST+':'+REMOTE+'/pilot_v3b/pairs_20_v3_cards.csv',str(pilot/'pairs_20_v3_cards.csv')])
 call(['rsync','-a','-e',' '.join(SSH),HOST+':'+REMOTE+'/pilot_v3b/pairs_20_v3/',str(out)+'/'])
 for p in [pilot/'pairs_20_v3_cards.csv',*out.glob('*.jpg')]:
  rp=REMOTE+'/pilot_v3b/'+('pairs_20_v3_cards.csv' if p.suffix=='.csv' else 'pairs_20_v3/'+p.name)
  if digest(p)!=remote('sha256sum '+rp).split()[0]:raise RuntimeError('card mismatch '+str(p))
 print('cards_checked',len(list(out.glob('*.jpg'))),flush=True)
if __name__=='__main__':main()
