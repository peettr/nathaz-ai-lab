#!/usr/bin/env python3.10
import pathlib,subprocess
R=pathlib.Path(__file__).resolve().parent;Q=R.parent/'R21.4a_T6_z0_inlet'
for name in ('controller.py','worker.py','launch.py','probe.py','ack.py','gpu_probe.py','abort_prelaunch.py'):
 text=(Q/name).read_text().replace('T6','T7').replace('t6','t7').replace('z0-inlet','buffer40').replace('z0inlet','buffer40')
 text=text.replace('E_s101_on','E_s101_off').replace('E_s102_on','E_s102_off')
 if name=='worker.py':
  text=text.replace("for mode in ('on',):","for mode in ('off',):")
  text=text.replace("match=re.search(r'^\\s*#define def_ground_z0_lattice\\s+([0-9.eE+-]+)f',cl.read_text(),re.M)\n  assert match and abs(float(match.group(1))-9.043314192325095e-05)<1e-8, 'T7 actual OpenCL z0 mismatch'","match=re.search(r'^\\s*#define def_buffer_N\\s+(\\d+)u',cl.read_text(),re.M)\n  assert match and int(match.group(1))==40, 'T7 actual OpenCL buffer mismatch'")
 if name=='controller.py':
  text=text.replace("match=re.search(r'^\\s*#define def_ground_z0_lattice\\s+([0-9.eE+-]+)f',cl.read_text(),re.M)\n assert match and abs(float(match.group(1))-9.043314192325095e-05)<1e-8,'actual OpenCL z0 mismatch'","match=re.search(r'^\\s*#define def_buffer_N\\s+(\\d+)u',cl.read_text(),re.M)\n assert match and int(match.group(1))==40,'actual OpenCL buffer mismatch'")
 assert '9.043314192325095e-05' not in text and 'E_s101_on' not in text and 'E_s102_on' not in text,name
 p=R/name
 if p.exists():
  assert p.read_text()==text or name in ('controller.py','worker.py'),name
  if p.read_text()!=text: p.write_text(text)
 else:p.write_text(text)
 subprocess.run(['python3.10','-m','py_compile',str(p)],check=True)
 print(name,'PASS')
