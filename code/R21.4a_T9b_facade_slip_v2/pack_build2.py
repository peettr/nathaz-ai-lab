#!/usr/bin/env python3
"""Freeze one new stage archive for the GPU validation attempt."""
import pathlib,tarfile,hashlib,json,shutil
R=pathlib.Path(__file__).resolve().parent
T5=R.parent/'R21.4a_T5_caseE_WM_retry1';S=R/'build2_stage'
assert not S.exists()
S.mkdir()
shutil.copytree(R/'FluidX3D_facade_v3',S/'FluidX3D_facade_v3')
shutil.copytree(T5/'stage/cases/E_s101_off',S/'case')
shutil.copyfile(T5/'B2u_reference_points.json',S/'B2u_reference_points.json')
files={str(p.relative_to(S)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(S.rglob('*')) if p.is_file()}
arc=R/'t9b2_stage.tar.gz';assert not arc.exists()
with tarfile.open(arc,'w:gz') as t:t.add(S,arcname='stage')
h=hashlib.sha256(arc.read_bytes()).hexdigest()
(R/'t9b2_archive.json').write_text(json.dumps({'archive_sha256':h,'members':files},indent=2)+'\n')
print('archive',arc,'bytes',arc.stat().st_size,'sha256',h,'members',len(files))
