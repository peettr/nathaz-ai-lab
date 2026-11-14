import pathlib,hashlib,csv,collections,json
p=pathlib.Path('/content/diagout_v3')
for f in (p/'diag_inputs.md',p/'diag_results.csv'):
 print(f.name,f.stat().st_size,hashlib.sha256(f.read_bytes()).hexdigest())
r=list(csv.DictReader((p/'diag_results.csv').open()))
print('rows',len(r),'groups',dict(sorted(collections.Counter((x['chain'],x['variant']) for x in r).items())))
print('events',dict(sorted(collections.Counter(x['event'] for x in r if x['chain']=='b' and x['variant']=='V0').items())))
print('script_sha256',hashlib.sha256(pathlib.Path('/content/diag_inputs_v3.py').read_bytes()).hexdigest())
