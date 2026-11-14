import csv, pathlib, subprocess, re
R=pathlib.Path(__file__).parent
rows=list(csv.DictReader((R/'VISUAL_QUEUE.csv').open()))
ctx='[已隐去]'
log=R/'thumb_receipts.tsv'
done={}
if log.exists():
 for line in log.read_text().splitlines():
  fig,code,path=line.split('\t',2);done[fig]=(code,path)
for fig in dict.fromkeys(x['fig_id'] for x in rows):
 if fig in done: continue
 p=subprocess.run(['rc-kb','--ctx',ctx,'figs','--thumb',fig],capture_output=True,text=True,timeout=60)
 m=re.search(r'缩略图已取到：(\S+)',p.stdout)
 path=m.group(1) if m else ('ERROR '+p.stdout.strip()+' '+p.stderr.strip())
 with log.open('a') as f:f.write(f'{fig}\t{p.returncode}\t{path}\n')
 done[fig]=(str(p.returncode),path)
 print(fig,p.returncode,path,flush=True)
 if p.returncode: raise SystemExit('thumb fetch failure, stop without retry')
for r in rows: r['缩略图本机路径']=done[r['fig_id']][1]
with (R/'VISUAL_QUEUE.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print('rows',len(rows),'unique fetched',len(done))
