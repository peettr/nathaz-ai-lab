import tarfile,gzip,json
p='/content/sens2/source_stage.tar'
with tarfile.open(p) as t:
 for x in t:
  if not x.name.startswith('isd/'):continue
  data=json.loads(gzip.decompress(t.extractfile(x).read()));
  for y in data:
   if y.get('REM') and 'PK WND' in y['REM']:
    print(x.name,{k:y.get(k) for k in ('DATE','REM','OC1','SOURCE')});raise SystemExit
