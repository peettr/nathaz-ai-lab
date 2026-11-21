#!/usr/bin/env python3
"""Freeze build8 source archive and diff after local generator validation."""
import pathlib,hashlib,json,tarfile,difflib
R=pathlib.Path(__file__).resolve().parent;P=R.parent/'build7_20261117_1250'/'FluidX3D_facade_v7';V=R/'FluidX3D_facade_v8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
arc=R/'t9b8_source.tar.gz'
with tarfile.open(arc,'w:gz') as t:t.add(V,arcname=V.name)
members={str(p.relative_to(V)):sha(p) for p in V.rglob('*') if p.is_file()}
(R/'t9b8_manifest.json').write_text(json.dumps({'archive_sha256':sha(arc),'members':members},indent=2)+'\n')
lines=[]
for p in V.rglob('*'):
 if not p.is_file():continue
 prev=P/p.relative_to(V)
 if prev.is_file() and prev.read_bytes()!=p.read_bytes():lines+=list(difflib.unified_diff(prev.read_text().splitlines(keepends=True),p.read_text().splitlines(keepends=True),fromfile='v7/'+str(p.relative_to(V)),tofile='v8/'+str(p.relative_to(V))))
(R/'diff_vs_v7.patch').write_text(''.join(lines))
print(json.dumps({'archive':sha(arc),'members':len(members),'diff_lines':len(lines)}))
