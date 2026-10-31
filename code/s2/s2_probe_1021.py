import pathlib, subprocess
r=pathlib.Path('/content/s2')
for n in ['pilot_repaired.log','incremental.jsonl','s2_smoke.done']:
 p=r/n
 print(n, 'exists',p.exists(),'bytes',p.stat().st_size if p.exists() else None)
 if p.exists() and n in ('pilot_repaired.log','s2_smoke.done'):
  print(p.read_text()[-3000:])
print(subprocess.run(['pgrep','-af','s2_install_and_pilot_1021.py'],capture_output=True,text=True).stdout[:1000])
