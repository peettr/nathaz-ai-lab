import pathlib,subprocess,json
r=pathlib.Path('/content/s2')
for name in ('resume_20_130.log','incremental_20_130.jsonl','s2_20_130.done','resume_20_130.failed'):
 p=r/name
 print(name,'exists',p.exists(),'bytes',p.stat().st_size if p.exists() else None)
 if p.exists() and name.endswith('.log'):
  s=p.read_text(errors='replace').splitlines();print('tail',s[-12:]);print('group_count',sum('GROUP_END' in x for x in s))
print('process',subprocess.run(['pgrep','-af','resume_inner_20_130.py'],capture_output=True,text=True).stdout)
