import subprocess, pathlib
for p in ['/content/Strata/engine','/content/Strata-data/packs','/content/Strata-data/models','/content/Strata-data']:
 r=subprocess.run(['du','-sh',p],capture_output=True,text=True);print(r.stdout.strip() or r.stderr.strip())
p=pathlib.Path('/content/Strata/engine/strata')
print('engine',p.stat().st_size,'bytes')
print(subprocess.run(['ldd',str(p)],capture_output=True,text=True).stdout)
print('pack inventory')
p=pathlib.Path('/content/Strata-data/packs/unsloth-ud-iq4_xs')
for x in sorted(p.iterdir()):
 if x.is_file():print(x.name,x.stat().st_size)
