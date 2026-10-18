#!/usr/bin/env python3
"""Resume-safe <=3GB PDF batches; existing shared SSH only, two-end SHA256."""
import argparse, hashlib, json, os, sqlite3, subprocess
from pathlib import Path
HOST='[邮箱]'
SSH=['ssh','-o','ControlPath=./.ssh/sockets/[邮箱]','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
ROOT=Path('./22_Lab/06_Logs/figure_kb')
STAGE=Path('./ftkb_figures/stage')
INDEX='./services/ftkb/data/index.sqlite'
def call(args):
    subprocess.run(args,stdin=subprocess.DEVNULL,check=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--max-batches',type=int,default=0);a=p.parse_args()
    call(SSH+['-O','check',HOST]);STAGE.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect('file:'+INDEX+'?mode=ro',uri=True)
    rows=sorted(c.execute("SELECT attachment,library,pdf,work FROM attachments WHERE library IN ('Zotero','EndNote') AND pdf IS NOT NULL"),key=lambda x:(x[1],x[0]));c.close()
    batches=[];batch=[];size=0
    for attachment,library,path,work in rows:
        n=os.path.getsize(path)
        if n>3_000_000_000:raise RuntimeError('single PDF exceeds 3GB: '+path)
        if batch and size+n>2_800_000_000:batches.append(batch);batch=[];size=0
        batch.append((attachment,library,path,n,work));size+=n
    if batch:batches.append(batch)
    print('batches',len(batches),'PDFs',len(rows),flush=True)
    manifest=ROOT/'p14_pdfs_manifest.jsonl'
    done={}
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            x=json.loads(line);done[(x['library'],x['attachment'])]=x
    for i,b in enumerate(batches):
        if a.max_batches and i>=a.max_batches:break
        remaining=[x for x in b if (x[1],x[0]) not in done]
        if not remaining:continue
        tag=f'batch_{i:04d}_resume_20261016'  # fresh staging root; preserve interrupted batch_0004 unchanged
        print(tag,len(remaining),'bytes',sum(x[3] for x in remaining),flush=True)
        entries=[]
        for attachment,library,path,n,work in remaining:
            h=hashlib.sha256()
            with open(path,'rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
            entries.append(dict(attachment=attachment,library=library,work=work,original_path=path,staged_path=f'./ftkb_figures/p14_pdfs/{library}/{attachment}/{Path(path).name}',bytes=n,sha256=h.hexdigest()))
        (STAGE/(tag+'.jsonl')).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in entries))
        (STAGE/(tag+'.files')).write_text(''.join(x[2].lstrip('/')+'\n' for x in remaining))
        call(SSH+['-n',HOST,f'mkdir -p ~/ftkb_figures/p14_pdfs/staging/{tag} ~/ftkb_figures/p14_pdfs/manifests'])
        call(['rsync','-a','--relative','--ignore-existing','--files-from='+str(STAGE/(tag+'.files')),'-e',' '.join(SSH),'/',HOST+f':ftkb_figures/p14_pdfs/staging/{tag}/'])
        call(['scp']+SSH[1:]+[str(STAGE/(tag+'.jsonl')),HOST+':ftkb_figures/p14_pdfs/manifests/'+tag+'.jsonl'])
        call(SSH+['-n',HOST,f'python3 ~/ftkb_figures/scripts/verify_p14_pdfs.py {tag}'])
        with open(manifest,'a') as f:
            for x in entries:f.write(json.dumps(x,ensure_ascii=False)+'\n');done[(x['library'],x['attachment'])]=x
        print(tag,'verified',len(entries),flush=True)
    print('manifest entries',len(done),flush=True)
if __name__=='__main__':main()
