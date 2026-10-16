"""Prepare separate Case A rerun for the official z/b=0.125 and 1.25 planes."""
import json
from pathlib import Path
r=Path(__file__).parent
src=json.loads((r/'caseA_observations.json').read_text())
for key,zratio in [('z8',.125),('z80',1.25)]:
    for p in src['groups'][key]:p['z_b']=zratio;p['z']=zratio*32.
src['high_plane_note']='Official AIJ sheet title and Zenodo AIJ-curator readme specify z/b=1.25 (40m), although worksheet z cells erroneously say 0.125; low plane z/b=.125 (4m). Han Table 2 calls these z/H=.125,1.25, inconsistent with H=64m.'
(r/'caseA_observations_official.json').write_text(json.dumps(src,indent=2))
for name in ('bootstrap','launch','extract'):
    text=(r/f'{name}_caseA.py').read_text().replace('luw-aij-caseA','luw-aij-caseA-official')
    if name=='extract':text=text.replace('/content/caseA_observations.json','/content/caseA_observations_official.json').replace('samples_caseA.json','samples_caseA_official.json')
    (r/f'{name}_caseA_official.py').write_text(text)
print('separate official-plane scripts and observations prepared')
