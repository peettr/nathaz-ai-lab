#!/usr/bin/env python3.10
"""Freeze T15 source and 1-m decks; only small local inputs."""
import hashlib,json,pathlib,shutil,tarfile
R=pathlib.Path(__file__).resolve().parent
BASE=R.parents[1]/'R21.4a_T4_groundWM/phaseB_v2/stage'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
S=R/'stage';S.mkdir(exist_ok=False)
m={'sources':{},'cases':{}}
for variant in ('off','e3','on','k3'):
 src=R/('FluidX3D_'+variant);dest=S/src.name
 shutil.copytree(src,dest,ignore=shutil.ignore_patterns('bin','obj','__pycache__'))
 m['sources'][variant]={p.name:sha(p) for p in (dest/'src').iterdir() if p.is_file() and p.suffix in ('.cpp','.hpp')}
for seed in (107,108,109):
 key=f'dx1p0_s{seed}';shutil.copytree(BASE/key,S/key)
 m['cases'][key]=sha(S/key/'conf.luwpf')
 assert m['cases'][key]==json.loads((BASE/'phase_manifest.json').read_text())['cases'][key]['conf_sha256']
archive=R/'t15_stage.tar.gz'
with tarfile.open(archive,'x:gz') as tf:tf.add(S,arcname='stage')
m['archive_sha256']=sha(archive)
(R/'t15_manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n')
print('STAGE_SHA',m['archive_sha256'],'SOURCE_FILES',sum(map(len,m['sources'].values())),'CASES',m['cases'])
