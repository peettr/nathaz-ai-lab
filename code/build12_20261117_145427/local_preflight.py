#!/usr/bin/env python3
"""Fail closed: compiler, generated OpenCL and host-kernel ABI, transport."""
from pathlib import Path
import subprocess,hashlib,json,re,tarfile,tempfile,ast,sys
R=Path(__file__).resolve().parent;S=R/'FluidX3D_facade_v11/src';V6=R.parent/'build6_20261117_123412/FluidX3D_facade_v6/src';B=R.parent/'build10_20261117_1356'
def sh(*args):return subprocess.run(args,cwd=R,capture_output=True,text=True,check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
syntax=sh('g++','-std=c++17','-fsyntax-only',str(S/'kernel.cpp'))
assert syntax.stdout==syntax.stderr==''
for f in ('worker_gate.py','controller_gate.py','probe_gate.py','launch_gate.py'):
 ast.parse((R/f).read_text());sh(sys.executable,'-m','py_compile',str(R/f))
manifest=json.loads((R/'t9b12_manifest.json').read_text());arc=R/'t9b12_source.tar.gz'
assert sha(arc)==manifest['archive_sha256']
with tarfile.open(arc) as t:
 with tempfile.TemporaryDirectory(dir=R) as d:
  t.extractall(d,filter='data')
  for n,h in manifest['members'].items():assert sha(Path(d)/'FluidX3D_facade_v11'/n)==h,n
src=(S/'kernel.cpp').read_text();v6=(V6/'kernel.cpp').read_text()
start='bool facade_eligible(';end=')+"#endif"+R('
assert src[src.index(start):src.index(end,src.index(start))]==v6[v6.index(start):v6.index(end,v6.index(start))]
# All sixteen changed read assignments are identical, not inferred from source hashes.
pattern=r'fhn\[\d+\]\s*=\s*load\(fi,index_f\([^;]+;'
a=re.findall(pattern,src[src.index(')+"#ifdef FACADE_FREE_SLIP"+R(',src.index(start)):src.index(')+"#endif"+R(',src.index('if(facade_eligible('))]);b=re.findall(pattern,v6[v6.index(')+"#ifdef FACADE_FREE_SLIP"+R(',v6.index(start)):v6.index(')+"#endif"+R(',v6.index('if(facade_eligible('))]);assert len(a)==len(b)==16 and a==b,(len(a),len(b))
# Compare real generated OpenCL with identical preprocessor defines.
for raw,processed,extra in [('generated_off.cl','generated_off_preprocessed.cl',[]),('generated_t5.cl','generated_t5_preprocessed.cl',[]),('generated_v6.cl','generated_v6_on.cl',['-DFACADE_FREE_SLIP']),('generated_off.cl','generated_v10_on.cl',['-DFACADE_FREE_SLIP'])]:
 (R/processed).write_text(sh('cpp','-P','-undef','-nostdinc',*extra,str(R/raw)).stdout)
assert (R/'generated_off_preprocessed.cl').read_bytes()==(R/'generated_t5_preprocessed.cl').read_bytes()
assert sha(R/'generated_off_preprocessed.cl')=='cc3f04ad07b371f827ddfb02c393d362c305bca4d310b353c9c0fcbb2a50ba2d'
# Compare generated ON text after removing only v6's no-op counter braces.
v10=(R/'generated_v10_on.cl').read_text();v6on=(R/'generated_v6_on.cl').read_text()
assert 'atomic_inc' not in v10
for stmt in a:
 compact=lambda s:re.sub(r'\s+','',s)
 assert compact(stmt) in compact(v10) and compact(stmt) in compact(v6on)
# Exact ABI comparison for city macro combination, not merely a list of names.
cl=sh('cpp','-P','-undef','-nostdinc','-DFORCE_FIELD',str(R/'generated_off.cl')).stdout
m=re.search(r'kernel\s+void\s+stream_collide\s*\((.*?)\)\s*\{',cl,re.S);assert m
args=[x.strip() for x in m.group(1).split(',')]
actual=[re.search(r'(\w+)\s*$',x).group(1) for x in args]
expected=['fi','rho','u','flags','t','fx','fy','fz','omega_x','omega_y','omega_z','F']
assert actual==expected,(actual,expected)
host=(S/'lbm.cpp').read_text();pos=host.index('kernel_stream_collide = Kernel(');assert 'fi, rho, u, flags, t, fx, fy, fz, omega_x, omega_y, omega_z' in host[pos:pos+200]
assert re.search(r'#ifdef FORCE_FIELD.*?kernel_stream_collide\.add_parameters\(F\);',host,re.S)
for name,macro in [('ground_tau_sum, ground_tau_count','GROUND_WALL_MODEL'),('ground_q_next','GROUND_WALL_FILTER'),('ground_force','WALL_GATE0')]:
 assert re.search(r'#ifdef '+macro+r'.*?kernel_stream_collide\.add_parameters\('+re.escape(name)+r'\);',host,re.S)
assert 'FACADE_COUNT' not in host and 'FACADE_COUNT' not in src
worker=(R/'worker_gate.py').read_text();controller=(R/'controller_gate.py').read_text()
assert 'city_2000_difference.json' in worker and 'stage_A_verdict.json' in worker
assert "deadline=created+4.5*3600/6.81" in controller and '--detach' in controller
assert not any('t9b10' in (R/n).read_text() for n in ('worker_gate.py','controller_gate.py','launch_gate.py','probe_gate.py'))
result={'passed':True,'gxx':'g++ -std=c++17 -fsyntax-only src/kernel.cpp: exit 0, empty output','lbm_cpp':'not compiled locally; legacy OpenCL headers','v10_archive_sha256':sha(arc),'member_count':len(manifest['members']),'off_generated_sha256':sha(R/'generated_off_preprocessed.cl'),'T5_off_generated_sha256':sha(R/'generated_t5_preprocessed.cl'),'off_byte_equal':True,'mirror_eligibility_v6_byte_equal':True,'mirror_read_assignments_equal_count':len(a),'stream_collide_args':actual,'host_constructor':expected[:-1],'host_add_parameters':['F'],'city_macro_combination':'FORCE_FIELD=on; GROUND_WALL_MODEL/GROUND_WALL_FILTER/WALL_GATE0=off','scope':'local only, not GPU'}
(R/'LOCAL_PREFLIGHT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
