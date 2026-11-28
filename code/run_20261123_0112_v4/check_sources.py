from pathlib import Path
import subprocess,hashlib,json
R=Path(__file__).resolve().parent
prep=R.parents[1]/'prep_20261123_0025'
base=(R.parent/'run_20261123_0100_v3/BASE.cl').read_bytes()
out=[]
for variant in ('B0','K1a','K1b','K2','K3a','K3b'):
 src=R/'variants'/variant/'src'; bin=R/(variant+'.emit')
 check=subprocess.run(['g++','-std=c++17','-fsyntax-only',str(src/'kernel.cpp')],capture_output=True,text=True)
 (R/(variant+'.gxx.log')).write_text(f'exit={check.returncode}\n'+check.stdout+check.stderr)
 build=subprocess.run(['g++','-std=c++17','-O0',str(src/'kernel.cpp'),str(prep/'dump_opencl.cpp'),'-o',str(bin)],capture_output=True,text=True)
 (R/(variant+'.build.log')).write_text(f'exit={build.returncode}\n'+build.stdout+build.stderr)
 if build.returncode: print(variant,'FAILED',build.stderr[:250]); continue
 p=subprocess.run([str(bin)],capture_output=True)
 if p.returncode: print(variant,'DUMP FAIL',p.stderr[:200]);continue
 (R/(variant+'.cl')).write_bytes(p.stdout)
 out.append([variant,check.returncode,len(p.stdout),hashlib.sha256(p.stdout).hexdigest(),p.stdout==base])
 print(out[-1])
(R/'GENERATED_CHECK.json').write_text(json.dumps({'baseline_sha256':hashlib.sha256(base).hexdigest(),'variants':out},indent=2)+'\n')
