import csv,json,pathlib,subprocess,os
p=pathlib.Path('/content/l264a100/texas');p.mkdir(exist_ok=True)
with (p/'Table4_IGBP_z0.csv').open() as f: rows=list(csv.DictReader((s for s in f if not s.startswith('#'))))
lookup={r['igbp_class']:float(r['z0_m']) for r in rows}
assert set(map(int,lookup))==set(range(18)) and all(z>0 for z in lookup.values())
(p/'table4_z0.json').write_text(json.dumps(lookup,indent=2))
fd=os.open(p/'build_static_retry.started',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
with (p/'build_static_retry.log').open('x') as log:
 proc=subprocess.Popen(['/content/l264a100/venv/bin/python','/content/l264_build_static.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('STATIC_PID',proc.pid,'TABLE4_CLASSES',len(lookup),flush=True)
