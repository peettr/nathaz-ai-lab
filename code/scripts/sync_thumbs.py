#!/usr/bin/env python3
"""Stage at most 500 completed 工作站 thumbnails at a time to Desktop; verify SHA256 before local removal."""
import argparse,hashlib,os,sqlite3,subprocess,tempfile,time
from pathlib import Path
SOCK='~/.ssh/sockets/[邮箱]'
HOST='[邮箱]'
SSH=['ssh','-o',f'ControlPath={SOCK}','-o','ControlMaster=no','-o','BatchMode=yes','-o','ProxyCommand=false']
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def sync(db,root,batch):
    c=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
    rel=[r[0] for r in c.execute('SELECT f.thumb_path FROM figures f JOIN documents d ON f.source_library=d.source_library AND f.doc_id=d.doc_id WHERE f.thumb_path IS NOT NULL ORDER BY f.fig_id') if (Path(root)/'thumbs'/r[0]).is_file()]
    c.close()
    run(SSH+['-O','check',HOST],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
    for i in range(0,len(rel),batch):
        names=rel[i:i+batch]
        with tempfile.TemporaryDirectory(dir=str(Path(root)/'pilot')) as t:
            lst=Path(t)/'names';lst.write_text(''.join(x+'\n' for x in names))
            hashes=Path(t)/'hashes';hashes.write_text(''.join(hashlib.sha256((Path(root)/'thumbs'/x).read_bytes()).hexdigest()+'  '+x+'\n' for x in names))
            # rsync files-from reads a regular file; remote SSH stdin is /dev/null.
            run(['rsync','-a','--files-from='+str(lst),'-e',' '.join(SSH),str(Path(root)/'thumbs')+'/',HOST+':ftkb_figures/thumbs/'],stdin=subprocess.DEVNULL)
            run(['scp']+SSH[1:]+[str(hashes),HOST+':ftkb_figures/pilot/checksums.txt'],stdin=subprocess.DEVNULL)
            result=run(SSH+['-n',HOST,'cd ~/ftkb_figures/thumbs && sha256sum -c ~/ftkb_figures/pilot/checksums.txt --quiet'],stdin=subprocess.DEVNULL,capture_output=True,text=True)
            for x in names:(Path(root)/'thumbs'/x).unlink()
        print(f'verified and removed {len(names)} temporary local thumbs',flush=True)
    print('total',len(rel),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--root',required=True);p.add_argument('--batch',type=int,default=500);a=p.parse_args();sync(a.db,a.root,a.batch)
