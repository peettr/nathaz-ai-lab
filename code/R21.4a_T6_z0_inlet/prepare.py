#!/usr/bin/env python3.10
"""Prestage T6 from immutable T5 archive; no solver execution."""
import pathlib,tarfile,tempfile,hashlib,json,math,shutil,csv,io
import numpy as np
R=pathlib.Path(__file__).resolve().parent; P=R.parent/'R21.4a_T5_caseE_WM_retry2'; src=P/'stage_t5.tar.gz'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src)=='20b4762b59f243f6003fccd55398e7527acc738b377f8f0993df05101a078e97'
with tarfile.open(src) as t:
 m=t.extractfile('stage/case/wind_bc/profile.dat').read().decode().splitlines(); pts=[dict(zip(('z','U'),line.split('\t'))) for line in m[1:]]; selected=[r for r in pts if float(r['z']) in (1.25,2.5,5.)]
 assert [float(r['z']) for r in selected]==[1.25,2.5,5.]
 z=np.array([float(r['z']) for r in selected]); u=np.array([float(r['U']) for r in selected]); x=np.log(z); a,b=np.linalg.lstsq(np.column_stack((x,np.ones(3))),u,rcond=None)[0]; z0=math.exp(-b/a)
 z0_literal=f'{z0:.12g}f'; assert 0<z0<.001
 for seed in (101,102):assert t.extractfile(f'stage/cases/E_s{seed}_on/wind_bc/profile.dat').read()==t.extractfile('stage/case/wind_bc/profile.dat').read()
 with tempfile.TemporaryDirectory(dir=R) as td:
  root=pathlib.Path(td);t.extractall(root,filter='data'); stage=root/'stage'
  setup=stage/'FluidX3D_on/src/setup.cpp'; old=setup.read_text(); needle='experimental_ground_z0_lattice = units.x(0.024f);';assert old.count(needle)==1
  replacement=f'experimental_ground_z0_lattice = units.x({z0_literal}); // T6 inlet z0, fitted 1.25/2.5/5 m'
  setup.write_text(old.replace(needle,replacement))
  manifest=stage/'manifest.json'; man=json.loads(manifest.read_text());assert man['source']['on']['setup.cpp']==hashlib.sha256(old.encode()).hexdigest(); man['source']['on']['setup.cpp']=sha(setup);manifest.write_text(json.dumps(man,indent=2)+'\n')
  manifest_hash=sha(manifest)
  out=R/'stage_t6.tar.gz';assert not out.exists()
  with tarfile.open(out,'w:gz') as o:o.add(stage,arcname='stage')
 (R/'fit.json').write_text(json.dumps({'z_m':z.tolist(),'U_m_s':u.tolist(),'kappa':.4,'model':'U=a ln(z)+b, a=u_star/kappa, b=-a ln(z0)','a':a,'b':b,'u_star':.4*a,'z0_in_m':z0,'literal':z0_literal,'profile_sha256':man['profile_sha256'],'t5_archive_sha256':sha(src),'t6_archive_sha256':sha(out),'t6_setup_sha256':man['source']['on']['setup.cpp'],'t5_setup_sha256':hashlib.sha256(old.encode()).hexdigest(),'source_manifest_sha256':manifest_hash,'t5_config_sha256':{str(seed):man['cases'][f'E_s{seed}_on']['config_sha256'] for seed in (101,102)},'actual_source_line':replacement},indent=2)+'\n')
 (R/'archive.json').write_text(json.dumps({'sha256':sha(out),'bytes':out.stat().st_size})+'\n')
 shutil.copyfile(P/'B2u_reference_points.json',R/'B2u_reference_points.json');shutil.copyfile(P/'widths.csv',R/'widths.csv')
print((R/'fit.json').read_text())
