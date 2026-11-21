#!/usr/bin/env python3.10
"""Freeze T7 archive and adapt proven T6 transport scripts; no GPU computation."""
import pathlib,tarfile,tempfile,hashlib,json,shutil,re,subprocess,time
R=pathlib.Path(__file__).resolve().parent; L=R.parent; P=L/'R21.4a_T5_caseE_WM_retry2'; Q=L/'R21.4a_T6_z0_inlet'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
src=P/'stage_t5.tar.gz';assert sha(src)=='20b4762b59f243f6003fccd55398e7527acc738b377f8f0993df05101a078e97'
with tempfile.TemporaryDirectory(dir=R) as d:
 with tarfile.open(src) as t:
  for m in t.getmembers(): assert (m.name=='stage' or m.name.startswith('stage/')) and '..' not in pathlib.PurePath(m.name).parts and (m.isfile() or m.isdir())
  t.extractall(d,filter='data')
 stage=pathlib.Path(d)/'stage'; setup=stage/'FluidX3D_off/src/setup.cpp'; old=setup.read_text();needle='buffer_n_cells = nbuf;';assert old.count(needle)==1
 replacement='buffer_n_cells = 40; // T7: def_buffer_N 40u instead of T5 117u, unchanged elsewhere'
 setup.write_text(old.replace(needle,replacement))
 manfile=stage/'manifest.json';man=json.loads(manfile.read_text()); assert man['source']['off']['setup.cpp']==hashlib.sha256(old.encode()).hexdigest();man['source']['off']['setup.cpp']=sha(setup);manfile.write_text(json.dumps(man,indent=2)+'\n')
 for label in ('E_s101_off','E_s102_off'):
  assert man['cases'][label]['variant']=='off'
  assert sha(stage/'cases'/label/'conf.luwpf')==man['cases'][label]['config_sha256']
 out=R/'stage_t7.tar.gz';assert not out.exists()
 with tarfile.open(out,'w:gz') as t:t.add(stage,arcname='stage')
 archive={'t5_sha256':sha(src),'t7_sha256':sha(out),'t7_setup_sha256':sha(setup),'t5_setup_sha256':hashlib.sha256(old.encode()).hexdigest(),'t7_manifest_sha256':sha(manfile),'config_sha256':{label:man['cases'][label]['config_sha256'] for label in ('E_s101_off','E_s102_off')},'source_line':replacement}
(R/'archive.json').write_text(json.dumps({'sha256':sha(out),'bytes':out.stat().st_size,**archive},indent=2)+'\n')
for f in ('B2u_reference_points.json','widths.csv'): shutil.copyfile(P/f,R/f)
# Every derived controller/worker reference is checked after substitutions; no T6 physics remains.
for name in ('controller.py','worker.py','launch.py','probe.py','ack.py','gpu_probe.py','abort_prelaunch.py'):
 text=(Q/name).read_text()
 text=text.replace('T6','T7').replace('t6','t7').replace('z0-inlet','buffer40').replace('z0inlet','buffer40')
 if name=='worker.py':
  text=text.replace("CASES=['E_s101_on','E_s102_on']","CASES=['E_s101_off','E_s102_off']")
  text=text.replace("for mode in ('on',):","for mode in ('off',):")
  text=text.replace("match=re.search(r'^\\s*#define def_ground_z0_lattice\\s+([0-9.eE+-]+)f',cl.read_text(),re.M)\n  assert match and abs(float(match.group(1))-9.043314192325095e-05)<1e-8, 'T7 actual OpenCL z0 mismatch'","match=re.search(r'^\\s*#define def_buffer_N\\s+(\\d+)u',cl.read_text(),re.M)\n  assert match and int(match.group(1))==40, 'T7 actual OpenCL buffer mismatch'")
  text=text.replace('E_s101_on E_s102_on complete','E_s101_off E_s102_off complete')
 if name=='controller.py':
  text=text.replace("LABELS=('E_s101_on','E_s102_on')","LABELS=('E_s101_off','E_s102_off')")
  text=text.replace("match=re.search(r'^\\s*#define def_ground_z0_lattice\\s+([0-9.eE+-]+)f',cl.read_text(),re.M)\n assert match and abs(float(match.group(1))-9.043314192325095e-05)<1e-8,'actual OpenCL z0 mismatch'","match=re.search(r'^\\s*#define def_buffer_N\\s+(\\d+)u',cl.read_text(),re.M)\n assert match and int(match.group(1))==40,'actual OpenCL buffer mismatch'")
  # preserve exact private config contract and avoid confusing T6 after name changes
  text=text.replace("'luw-r214a-t7-buffer40-1117'","'luw-r214a-t7-buffer40-1117'")
  text=text.replace("for name in ('stage_t7.tar.gz'","for name in ('stage_t7.tar.gz'")
  text=text.replace("'--no-remind'","'--no-remind'")
 assert ('9.043314192325095e-05' not in text and 'E_s101_on' not in text and 'E_s102_on' not in text),name
 (R/name).write_text(text)
for name in ('controller.py','worker.py','launch.py','probe.py','ack.py','gpu_probe.py','abort_prelaunch.py'):
 subprocess.run(['python3.10','-m','py_compile',str(R/name)],check=True)
print(json.dumps(archive,indent=2))
