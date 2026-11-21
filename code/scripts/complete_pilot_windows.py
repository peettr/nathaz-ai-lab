#!/usr/bin/env python3
"""Once all PDFs are verified, do Zotero v3 rerender and produce 20 cards."""
import hashlib,json,os,subprocess
from pathlib import Path
BASE=Path('./22_Lab/06_Logs/figure_kb')
LOCAL=Path('./ftkb_figures')
HOST='[邮箱]';O='./ftkb_figures';C='./ftkb_figures'
SSH=['ssh','-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
def call(a):subprocess.run(a,stdin=subprocess.DEVNULL,check=True)
def remote(s):return subprocess.check_output(SSH+['-n',HOST,s],stdin=subprocess.DEVNULL,text=True).strip()
def hash_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def push(local,remote_path):
 call(['scp']+SSH[1:]+[str(local),HOST+':'+remote_path]);assert hash_file(local)==remote('sha256sum '+remote_path).split()[0]
def main():
 call(SSH+['-O','check',HOST])
 old=list(map(json.loads,(BASE/'p14_pdfs_manifest.jsonl').open()));new=list(map(json.loads,(BASE/'p14_pdfs_manifest_windows.jsonl').open()))
 all_entries=old+new
 if len(all_entries)!=4676 or len(set((x['library'],x['attachment']) for x in all_entries))!=4676:raise RuntimeError('PDF staging incomplete')
 all_file=BASE/'p14_pdfs_manifest_all.jsonl'
 payload=''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in all_entries)
 if all_file.exists():
  if all_file.read_text()!=payload:raise RuntimeError('refuse changed manifest')
 else:all_file.write_text(payload)
 remote(f'mkdir -p {O}/scripts {O}/tmp {C}/pilot_v3b/thumbs; test -w {C}/pilot_v3b')
 scripts=('figure_pipeline_v3.py','rerender_fallback_v3.py','make_pairs_20_v3.py','make_pairs_v2.py','full_desktop_v2.py','build_vectors_full_v2.py','figsearch_full_desktop_v2.py')
 for name in scripts:push(BASE/'scripts'/name,O+'/scripts/'+name)
 push(all_file,O+'/p14_pdfs_manifest_all.jsonl')
 push(BASE/'p14_pdfs_work_map.jsonl',O+'/p14_pdfs_work_map.jsonl')
 source=LOCAL/'pilot_v2/local.sqlite';dest=C+'/pilot_v3b/source_local_v2.sqlite'
 if remote('test -e '+dest+' && echo exists || echo missing')=='missing':push(source,dest)
 elif hash_file(source)!=remote('sha256sum '+dest).split()[0]:raise RuntimeError('source DB hash mismatch')
 # Remote source DB is a read-only input for the independent Zotero copy.
 cmd=f'export TMPDIR={O}/tmp PYTHONDONTWRITEBYTECODE=1; nice -n 10 ~/ftkb_text/venv/bin/python {O}/scripts/rerender_fallback_v3.py --source-db {dest} --out-db {C}/pilot_v3b/zotero.sqlite --root {C}/pilot_v3b --manifest {O}/p14_pdfs_manifest_all.jsonl --library Zotero'
 if remote(f'test -e {C}/pilot_v3b/zotero.sqlite && echo exists || echo missing')=='missing':print(remote(cmd),flush=True)
 else:raise FileExistsError('Zotero output exists: inspect before retry')
 for lib in ('Desktop','EndNote'):
  link=C+'/pilot_v3b/thumbs/'+lib
  remote(f'test -e {link} || ln -s ./ftkb_figures/pilot_v3b/thumbs/{lib} {link}')
 cmd=f'export TMPDIR={O}/tmp PYTHONDONTWRITEBYTECODE=1; nice -n 10 ~/ftkb_figures/venv/bin/python {O}/scripts/make_pairs_20_v3.py --台式机 ~/ftkb_figures/pilot_v3b/desktop.sqlite --endnote-db ~/ftkb_figures/pilot_v3b/endnote.sqlite --zotero-db {C}/pilot_v3b/zotero.sqlite --root {C}/pilot_v3b --seed 20261017'
 print(remote(cmd),flush=True)
 pilot=BASE/'pilot';out=pilot/'pairs_20_v3'
 if out.exists() or (pilot/'pairs_20_v3_cards.csv').exists():raise FileExistsError('local cards exist')
 call(['scp']+SSH[1:]+[HOST+':'+C+'/pilot_v3b/pairs_20_v3_cards.csv',str(pilot/'pairs_20_v3_cards.csv')])
 call(['rsync','-a','-e',' '.join(SSH),HOST+':'+C+'/pilot_v3b/pairs_20_v3/',str(out)+'/'])
 for p in [pilot/'pairs_20_v3_cards.csv',*out.glob('*.jpg')]:
  remote_path=C+'/pilot_v3b/'+('pairs_20_v3_cards.csv' if p.suffix=='.csv' else 'pairs_20_v3/'+p.name)
  if hash_file(p)!=remote('sha256sum '+remote_path).split()[0]:raise RuntimeError('card checksum mismatch '+str(p))
 print('cards checked',len(list(out.glob('*.jpg'))),'csv bytes', (pilot/'pairs_20_v3_cards.csv').stat().st_size)
if __name__=='__main__':main()
