#!/usr/bin/env python3
"""Snapshot immutable R3 candidates; no scientific computation or submission."""
from pathlib import Path
import hashlib, json, tarfile, csv
S=Path('./22_Lab/06_Logs/l22_6/sessions')
D=S/'crc_R3'; R2=S/'crc_R2'
rows=[]
for condition in ('N','W'):
 for repeat in (1,2,3):
  ident=f'T03_{condition}_r{repeat}'; source=S/'gpt'/ident/'cand_R3'; tag=f'gpt_{ident}'
  assert source.is_dir() and (source/'EXTRACT.json').is_file()
  assert not (S/'gpt'/ident/'grade_R3.json').exists()
  root=f'/groups/kareem/[用户]/L22_6/L22_6_R3_{tag}_20261023'
  archive=D/(tag+'.tar.gz'); entries={}
  assert not archive.exists()
  with tarfile.open(archive,'w:gz') as tf:
   for f in sorted(source.rglob('*')):
    if f.is_file():
     rel=str(f.relative_to(source)); entries[rel]=hashlib.sha256(f.read_bytes()).hexdigest()
     tf.add(f,arcname='candidate/'+rel)
  script=D/(tag+'.sh'); assert not script.exists()
  old=(R2/(tag+'.sh')).read_text()
  assert old.count('R2')==2 and f'R2_{tag}' in old
  new=old.replace('R2','R3')
  assert root in new and '06:00:00' in new
  script.write_text(new)
  rows.append(dict(model='gpt',id=ident,task='T03',root=root,archive=str(archive),run_script=str(script),input_sha256=entries,tar_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
assert len(rows)==6
(D/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
with (D/'jobs.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['model','id','task','root','job','registration','status']);w.writeheader()
 for r in rows:w.writerow({k:r.get(k,'') for k in w.fieldnames})
print('prepared',len(rows),'archive bytes',sum(Path(r['archive']).stat().st_size for r in rows))
