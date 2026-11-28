#!/usr/bin/env python3
"""Snapshot nine immutable R2 inputs; no computation or submission."""
from pathlib import Path
import hashlib, json, tarfile, csv
S=Path('./22_Lab/06_Logs/l22_6/sessions')
D=S/'crc_R2'; R1=S/'crc_R1'
rows=[]
for model,conditions in (('gpt',('N','W')),('gemini',('N',))):
 for condition in conditions:
  for repeat in (1,2,3):
   ident=f'T03_{condition}_r{repeat}'; source=S/model/ident/'cand_R2'; tag=f'{model}_{ident}'
   assert source.is_dir() and not (S/model/ident/'grade_R2.json').exists()
   root=f'/groups/kareem/[用户]/L22_6/L22_6_R2_{tag}_20261023'
   archive=D/(tag+'.tar.gz'); entries={}
   assert not archive.exists()
   with tarfile.open(archive,'w:gz') as tf:
    for f in sorted(source.rglob('*')):
     if f.is_file():
      rel=str(f.relative_to(source)); entries[rel]=hashlib.sha256(f.read_bytes()).hexdigest()
      tf.add(f,arcname='candidate/'+rel)
   assert entries
   script=D/(tag+'.sh'); assert not script.exists()
   old=(R1/(tag+'.sh')).read_text()
   assert f'R1_{tag}' in old and old.count('R1')==2
   new=old.replace('R1','R2').replace('_20261023','_20261023')
   assert root in new and '06:00:00' in new
   script.write_text(new)
   rows.append(dict(model=model,id=ident,task='T03',root=root,archive=str(archive),run_script=str(script),input_sha256=entries,tar_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
assert len(rows)==9
(D/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
with (D/'jobs.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['model','id','task','root','job','registration','status']);w.writeheader()
 for r in rows:w.writerow({k:r.get(k,'') for k in w.fieldnames})
print('prepared',len(rows),'archive bytes',sum(Path(r['archive']).stat().st_size for r in rows))
