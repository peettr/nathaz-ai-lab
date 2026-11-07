#!/usr/bin/env python3
"""Stage remaining PDFs onto writable desktop O: in <=2.8GB verified batches."""
import argparse,hashlib,json,os,sqlite3,subprocess
from pathlib import Path
HOST='[邮箱]'
SSH=['ssh','-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
BASE=Path('./22_Lab/06_Logs/figure_kb')
STAGE=Path('./ftkb_figures/stage')
INDEX='./services/ftkb/data/index.sqlite'
REMOTE='./ftkb_figures'
def call(args):subprocess.run(args,stdin=subprocess.DEVNULL,check=True)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--max-batches',type=int,default=0);a=p.parse_args()
 call(SSH+['-O','check',HOST]);STAGE.mkdir(parents=True,exist_ok=True)
 old=list(map(json.loads,(BASE/'p14_pdfs_manifest.jsonl').open()))
 audit=list(map(json.loads,(BASE/'pilot/old_stage_audit.jsonl').open()))
 assert len(audit)==len(old) and all((x['library'],x['attachment'])==(y['library'],y['attachment']) and y['status']=='ok' for x,y in zip(old,audit))
 done={(x['library'],x['attachment']):x for x in old}
 c=sqlite3.connect('file:'+INDEX+'?mode=ro',uri=True)
 rows=sorted(c.execute("SELECT attachment,library,pdf,work FROM attachments WHERE library IN ('Zotero','EndNote') AND pdf IS NOT NULL"),key=lambda x:(x[1],x[0]));c.close()
 remaining=[(att,lib,path,os.path.getsize(path),work) for att,lib,path,work in rows if (lib,att) not in done]
 batches=[];batch=[];size=0
 for x in remaining:
  if x[3]>2_800_000_000:raise RuntimeError('PDF larger than batch cap: '+x[2])
  if batch and size+x[3]>2_800_000_000:batches.append(batch);batch=[];size=0
  batch.append(x);size+=x[3]
 if batch:batches.append(batch)
 print('old',len(old),'remaining',len(remaining),'batches',len(batches),flush=True)
 out=BASE/'p14_pdfs_manifest_windows.jsonl'
 if out.exists():
  for x in map(json.loads,out.open()):done[(x['library'],x['attachment'])]=x
 for i,b in enumerate(batches):
  if a.max_batches and i>=a.max_batches:break
  todo=[x for x in b if (x[1],x[0]) not in done]
  if not todo:continue
  tag=f'windows_{i:04d}';bytecount=sum(x[3] for x in todo)
  print(tag,'count',len(todo),'bytes',bytecount,flush=True)
  entries=[dict(attachment=att,library=lib,work=work,original_path=path,staged_path=f'{REMOTE}/p14_pdfs/{lib}/{att}/{Path(path).name}',root=REMOTE,bytes=n,sha256=sha(path)) for att,lib,path,n,work in todo]
  manifest=STAGE/(tag+'.jsonl');manifest.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in entries))
  files=STAGE/(tag+'.files');files.write_text(''.join(x[2].lstrip('/')+'\n' for x in todo))
  call(SSH+['-n',HOST,f'mkdir -p {REMOTE}/p14_pdfs/staging/{tag} {REMOTE}/p14_pdfs/manifests {REMOTE}/tmp'])
  call(['rsync','-a','--relative','--ignore-existing','--files-from='+str(files),'-e',' '.join(SSH),'/',HOST+f':{REMOTE}/p14_pdfs/staging/{tag}/'])
  call(['scp']+SSH[1:]+[str(manifest),HOST+f':{REMOTE}/p14_pdfs/manifests/{tag}.jsonl'])
  if sha(manifest)!=subprocess.check_output(SSH+['-n',HOST,f'sha256sum {REMOTE}/p14_pdfs/manifests/{tag}.jsonl'],stdin=subprocess.DEVNULL,text=True).split()[0]:raise RuntimeError('manifest transfer hash mismatch')
  call(SSH+['-n',HOST,f'TMPDIR={REMOTE}/tmp python3 {REMOTE}/verify_p14_pdfs_windows.py {tag}'])
  with out.open('a') as f:
   for x in entries:f.write(json.dumps(x,ensure_ascii=False)+'\n');done[(x['library'],x['attachment'])]=x
  print(tag,'verified',len(entries),'committed',len(done),flush=True)
 print('total committed',len(done),flush=True)
if __name__=='__main__':main()
