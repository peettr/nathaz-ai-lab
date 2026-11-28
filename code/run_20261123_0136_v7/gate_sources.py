from pathlib import Path
import subprocess,hashlib,shutil,json,re
R=Path(__file__).resolve().parent
P=R.parents[1]/'prep_20261123_0025';V=R/'pack_stage';D=R/'gate';D.mkdir(exist_ok=False)
BASE=R.parent/'run_20261123_0100_v3/BASE.cl';baseline=BASE.read_bytes();h0=hashlib.sha256(baseline).hexdigest()
reports=[]
for name in ('B0','K1a','K1b','K2','K3a','K3b'):
 src=V/name/'src'
 g=subprocess.run(['g++','-std=c++17','-fsyntax-only',str(src/'kernel.cpp')],capture_output=True,text=True)
 (D/(name+'_gxx.log')).write_text('exit='+str(g.returncode)+'\n'+g.stderr)
 # Truly disable *all* candidate macros in a separate, disposable source tree;
 # compile generated OpenCL container and compare its bytes against frozen baseline.
 tmp=D/('off_'+name);shutil.copytree(V/name,tmp)
 d=tmp/'src/defines.hpp';text=d.read_text()
 for macro in ('T18_CS013','T18_CS010','T18_TRT_WALE','T18_CW325','GROUND_WALL_SGS_DAMP'):
  text=re.sub(r'^#define '+macro+r'\s*\n','',text,flags=re.M)
 d.write_text(text)
 binary=D/(name+'_off.emit')
 build=subprocess.run(['g++','-std=c++17',str(tmp/'src/kernel.cpp'),str(P/'dump_opencl.cpp'),'-o',str(binary)],capture_output=True,text=True)
 assert build.returncode==0,(name,build.stderr[:500])
 out=subprocess.run([str(binary)],capture_output=True)
 sha=hashlib.sha256(out.stdout).hexdigest()
 reports.append({'variant':name,'gxx_rc':g.returncode,'off_generator_rc':out.returncode,'off_sha256':sha,'baseline_sha256':h0,'byte_equal':out.stdout==baseline})
 print(reports[-1])
(D/'macro_off.json').write_text(json.dumps(reports,indent=2)+'\n')
assert all(x['gxx_rc']==0 and x['byte_equal'] for x in reports)
