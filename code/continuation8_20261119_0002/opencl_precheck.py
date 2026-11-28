#!/usr/bin/env python3
"""Recheck frozen four OpenCL variants; compatibility format from prior fixture."""
import hashlib,os,pathlib,subprocess
R=pathlib.Path(__file__).resolve().parent
P=R.parent/'continuation7_20261118_231514'
O=R/'opencl_checks';O.mkdir(exist_ok=True)
clang=R/'local_clang/usr/bin/clang-14'
assert clang.is_file()
env={**os.environ,'LD_LIBRARY_PATH':str(R/'local_clang/usr/lib/llvm-14/lib')+':'+str(R/'local_clang/usr/lib/x86_64-linux-gnu')}
old='if((int)xyz.z+def_Oz!=def_ground_first_fluid_z\n||\nxyz.x<=1u\n||\nxyz.x+2u>=def_Nx\n||\nxyz.y<=1u\n||\nxyz.y+2u>=def_Ny\n||\n(flags[n]&TYPE_BO)!=0u)'
new='if((int)xyz.z+def_Oz!=def_ground_first_fluid_z\n||\n(flags[n]&TYPE_BO)!=0u)'
for v in ('off','on','e3','k3'):
 ref=P/'opencl_checks'/f'{v}_clang_compat.cl'
 text=ref.read_text()
 # For e3 only, remove the edge checks from the compatibility copy; the original generated
 # source was separately compared bytewise and the new generated function inspected.
 if v=='e3':
  assert text.count(old)==1
  text=text.replace(old,new)
 if v!='e3':
  assert (R/f'{v}_new_kernel_container.cl').read_bytes()==(R/f'{v}_old_kernel_container.cl').read_bytes()
 else:
  generated=(R/'e3_new_kernel_container.cl').read_text()
  assert 'if((int)xyz.z+def_Oz!=def_ground_first_fluid_z || (flags[n]&TYPE_BO)!=0u) return false;' in generated
  assert 'xyz.x<=1u' not in generated[generated.find('flat_ground_eligible'):generated.find('flat_ground_eligible')+450]
  assert ') +R(' not in generated
 out=O/f'{v}_clang_compat.cl';out.write_text(text)
 cp=subprocess.run([str(clang),'-x','cl','-cl-std=CL1.2','-fsyntax-only','-Wno-macro-redefined',str(out)],env=env,capture_output=True,text=True)
 log=O/f'{v}.log';log.write_text(f'command: clang-14 -x cl -cl-std=CL1.2 -fsyntax-only {out}\nexit_code: {cp.returncode}\n'+cp.stdout+cp.stderr)
 print(v,'exit',cp.returncode,'errors',cp.stderr.count(' error:'),'compat_sha',hashlib.sha256(text.encode()).hexdigest(),flush=True)
 if cp.returncode:raise SystemExit(1)
