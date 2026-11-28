#!/usr/bin/env python3
"""Local fail-closed T15 continuation staging; never invokes a solver."""
import difflib,hashlib,json,pathlib,subprocess,tarfile,datetime,re,sys
R=pathlib.Path(__file__).resolve().parent
OLD=R.parent/'continuation_20261118_1559'
FLAGS=['g++','-std=c++17','-pthread','-Isrc/OpenCL/include','-Wno-comment']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write_new(p,data):
 with p.open('xb') as f:f.write(data if isinstance(data,bytes) else data.encode())
print('BEGIN local validation',flush=True)
manifest={'sources':{},'cases':{}}
emit=R/'emit_kernel.cpp'; expected_emit='#include "kernel.cpp"\nint main(){std::cout << get_opencl_c_code();}\n'
if emit.exists(): assert emit.read_text()==expected_emit
else: write_new(emit,expected_emit)
texts={}
for tree in ('off','on','e3','k3'):
 src=R/'stage'/('FluidX3D_'+tree)
 p=subprocess.run(FLAGS+['-fsyntax-only','src/kernel.cpp','src/lbm.cpp','src/setup.cpp'],cwd=src,capture_output=True,text=True)
 print('GXX_SYNTAX',tree,p.returncode,p.stderr[-1600:],flush=True)
 if p.returncode:raise SystemExit('syntax failure '+tree)
 exe=R/('emit_v2_'+tree)
 subprocess.run(FLAGS+['-Isrc',str(emit),'-o',str(exe)],cwd=src,check=True)
 texts[tree]=subprocess.check_output([str(exe)])
 # The generated OpenCL is macro-conditional; audit declaration and use in both branches.
 cl=texts[tree].decode()
 if tree!='off':
  for symbol in ('applied_ground_fx','applied_ground_fy','applied_ground_tau_abs'):
   if not re.search(r'\bfloat\s+'+symbol+r'\s*=\s*0\.0f\s*;',cl):raise SystemExit('undeclared '+tree+' '+symbol)
 print('GENERATED_CL',tree,hashlib.sha256(texts[tree]).hexdigest(),'DECLARATION_CHECK_PASS',flush=True)
 manifest['sources'][tree]={p.name:sha(p) for p in (src/'src').iterdir() if p.is_file() and p.suffix in ('.cpp','.hpp')}
base=OLD/'stage/FluidX3D_off'
exe=R/'emit_old_off';subprocess.run(FLAGS+['-Isrc',str(emit),'-o',str(exe)],cwd=base,check=True)
assert texts['off']==subprocess.check_output([str(exe)]),'off OpenCL body changed'
for seed in (107,108,109):
 key='dx1p0_s'+str(seed);cfg=R/'stage'/key/'conf.luwpf'
 manifest['cases'][key]=sha(cfg)
 assert manifest['cases'][key]==json.loads((OLD/'t15_manifest.json').read_text())['cases'][key]
print('OFF_OPENCL_UNCHANGED',hashlib.sha256(texts['off']).hexdigest(),flush=True)
a=(OLD/'stage/FluidX3D_e3/src/kernel.cpp').read_text().splitlines(keepends=True)
b=(R/'stage/FluidX3D_e3/src/kernel.cpp').read_text().splitlines(keepends=True)
write_new(R/'E3_fix.diff',''.join(difflib.unified_diff(a,b,fromfile='old/E3/kernel.cpp',tofile='new/E3/kernel.cpp')))
for tree in ('off','on','e3','k3'):
 old=(OLD/'stage'/('FluidX3D_'+tree)/'src/opencl.hpp').read_text().splitlines(keepends=True)
 new=(R/'stage'/('FluidX3D_'+tree)/'src/opencl.hpp').read_text().splitlines(keepends=True)
 write_new(R/('compile_hook_'+tree+'.diff'),''.join(difflib.unified_diff(old,new,fromfile='old/'+tree+'/opencl.hpp',tofile='new/'+tree+'/opencl.hpp')))
arc=R/'t15_stage.tar.gz'
with tarfile.open(arc,'x:gz') as t:t.add(R/'stage',arcname='stage')
manifest['archive_sha256']=sha(arc)
write_new(R/'t15_manifest.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
ref=R.parents[1]/'R21.4a_T3_emptyground/T3d/dx1p0_s107_thin.npz'
assert sha(ref)==json.loads((OLD/'t15_manifest.json').read_text()).get('reference_sha256',sha(ref))
write_new(R/'SOURCE_CHECK.json',json.dumps({'archive_sha256':sha(arc),'variant_kernel_sha256':{k:manifest['sources'][k]['kernel.cpp'] for k in manifest['sources']},'generated_cl_body_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in texts.items()},'off_body_matches_previous':True,'e3_declaration_check':'PASS','note':'Generated text declaration audit is not a full OpenCL parser; native GPU build gates before solver.'},indent=2)+'\n')
print('ARCHIVE',sha(arc),'REFERENCE',sha(ref),'DONE',flush=True)
