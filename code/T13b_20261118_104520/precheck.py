#!/usr/bin/env python3.10
import pathlib,tarfile,hashlib,subprocess,shutil,difflib,re,json
R=pathlib.Path(__file__).resolve().parent
T5=R.parents[1]/'R21.4a_T5_caseE_WM_retry1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=R/'stage_t5.tar.gz';assert sha(a)==json.loads((R/'archive.json').read_text())['sha256']
with tarfile.open(a) as t:t.extractall(R/'precheck_source_t13b_final',filter='data')
s=R/'precheck_source_t13b_final/stage/FluidX3D_off'; src=s/'src';k=src/'kernel.cpp';assert sha(k)==json.loads((R/'kernel_manifest.json').read_text())['base_sha256']
shutil.copyfile(R/'kernel_t13b.cpp',k)
flag=['g++','-std=c++17','-pthread','-Isrc/OpenCL/include','-Wno-comment']
ref=(T5/'evidence/E_s101_off_actual_opencl.cl').read_bytes();marker=b'\n\nconst\nfloat\ndef_domain_offset_x';assert ref.count(marker)==1;offset=ref.index(marker)
emit=R/'emit_t13b_t13.cpp';emit.write_text('#include "kernel.cpp"\nint main(){std::cout << get_opencl_c_code();}\n')
def check(mode):
 d=src/'defines.hpp';b=d.read_bytes();
 if mode=='on':assert b.find(b'SMAG_CS_013')<0;d.write_bytes(b+b'\n#define SMAG_CS_013\n')
 subprocess.run(flag+['-fsyntax-only','src/kernel.cpp','src/setup.cpp','src/lbm.cpp'],cwd=s,check=True)
 exe=R/('emit_t13b_'+mode);subprocess.run(flag+['-Isrc',str(emit),'-o',str(exe)],cwd=s,check=True)
 body=subprocess.check_output([exe]);assert body.startswith(marker)
 print('SYNTAX_OK',mode,flush=True)
 return body
body_off=check('off');assert ref[:offset]+body_off==ref
print('OFF_EXACT_T5',sha(T5/'evidence/E_s101_off_actual_opencl.cl'),len(ref),flush=True)
body_on=check('on')
A=body_off.decode().splitlines(keepends=True);B=body_on.decode().splitlines(keepends=True)
diff=list(difflib.unified_diff(A,B));(R/'opencl_on_vs_off.diff').write_text(''.join(diff))
changes=[(tag,i,j,k,l) for tag,i,j,k,l in difflib.SequenceMatcher(None,A,B,autojunk=False).get_opcodes() if tag!='equal']
assert len(changes)==1 and changes[0][0]=='replace' and A[changes[0][1]].count('0.76421222f')==1 and B[changes[0][3]].count('0.4315f')==1
print('ON_ONE_LINE_DIFFERENCE',changes,flush=True)
# Source unaffected apart from kernel; C++ host signature is unchanged.
old=(T5/'stage/FluidX3D_off/src/kernel.cpp').read_text();new=k.read_text()
assert old.count('kernel void stream_collide')==new.count('kernel void stream_collide')==1
for token in ('stream_collide','add_parameters'):
 print('SIGNATURE_TOKEN',token,'baseline',old.count(token),'variant',new.count(token),flush=True)
print('KERNEL_SHA',sha(k),'SOURCE_SHA',sha(T5/'stage/FluidX3D_off/src/kernel.cpp'),flush=True)
