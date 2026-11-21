from pathlib import Path
import tarfile, hashlib, json, difflib, subprocess, re, shutil, tempfile
R=Path(__file__).resolve().parent
L=R.parents[1]
T5=L/'R21.4a_T5_caseE_WM_retry1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
V11='13bc199a005cfdf99cb7e81de79382676fcc4c2479e6abcc35ff4ef9296be9aa'

def main():
    with tempfile.TemporaryDirectory(prefix='t9b_v12_') as tmp:
        tmp=Path(tmp); a=R/'t9b12_source.tar.gz'; assert sha(a)==V11
        with tarfile.open(a) as t:t.extractall(tmp,filter='data')
        v11=tmp/'FluidX3D_facade_v11'; v12=tmp/'FluidX3D_facade_v12';shutil.copytree(v11,v12)
        s=v12/'src'; p=s/'setup.cpp'; x=p.read_bytes().decode(); nl='\r\n' if '\r\n' in x else '\n'
        anchor='            apply_profile_boundaries(lbm, ground_xy, dir_x, dir_y, case_downstream_bc);'
        assert x.count(anchor)==1
        x=x.replace(anchor,anchor+nl+nl.join(['            check_t9b_outer_flags(Nx, Ny, Nz, lbm.flags);','            println("T9B_MISSING_PATCH path=.luwpf/apply_profile_boundaries patch_sampler=not_used missing_patch_samples=0");','#ifdef FACADE_FREE_SLIP','            report_t9b_facades(Nx, Ny, Nz, lbm.flags);','#endif']))
        x=x.replace('#include "setup.hpp"','#include "setup.hpp"'+nl+'#include "t9b_boundary_audit.hpp"',1)
        p.write_bytes(x.encode());shutil.copyfile(R/'t9b_boundary_audit.hpp',s/'t9b_boundary_audit.hpp')
        p=s/'kernel.cpp'; old=p.read_text(); basic=(T5/'stage/FluidX3D_off/src/kernel.cpp').read_text(); aa=basic.splitlines(keepends=True);bb=old.splitlines(keepends=True)
        edits=[q for q in difflib.SequenceMatcher(None,aa,bb,autojunk=False).get_opcodes() if q[0]!='equal'];assert [q[0] for q in edits]==['insert','insert']
        for _,i,_,j,k in reversed(edits):
            fragment=''.join(bb[j:k]); assert fragment.startswith(')+"#ifdef FACADE_FREE_SLIP"+R(') and fragment.endswith(')+"#endif"+R(\n') and aa[i].startswith(')+')
            aa[i:i+1]=[')\n#ifdef FACADE_FREE_SLIP\n'+fragment[1:-1]+')\n#endif\n'+aa[i][1:]]
        p.write_text('#include "defines.hpp"\n'+''.join(aa));
        files=['src/setup.cpp','src/kernel.cpp','src/t9b_boundary_audit.hpp']; diff=[]
        for f in files:
            q=v11/f; diff.extend(difflib.unified_diff(q.read_text().splitlines(True) if q.exists() else [],(v12/f).read_text().splitlines(True),fromfile='v11/'+f,tofile='v12/'+f))
        (R/'v12_vs_v11.diff').write_text(''.join(diff));
        flags=['g++','-std=c++17','-pthread','-Isrc/OpenCL/include','-Wno-comment']; off=s/'defines.hpp'; offbytes=off.read_bytes(); toggle=b'//#define FACADE_FREE_SLIP // T9b-build default OFF'; assert offbytes.count(toggle)==1
        with (tmp/'emit.cpp').open('w') as f:f.write('#include "kernel.cpp"\nint main(){std::cout << get_opencl_c_code();}\n')
        ref=(T5/'evidence/E_s101_off_actual_opencl.cl').read_bytes();marker=b'\n\nconst\nfloat\ndef_domain_offset_x'; assert ref.count(marker)==1; offset=ref.index(marker)
        for mode in ['off','on']:
            if mode=='on':off.write_bytes(offbytes.replace(toggle,b'#define FACADE_FREE_SLIP // T9b-build ON'))
            subprocess.run(flags+['-fsyntax-only','src/kernel.cpp','src/setup.cpp','src/lbm.cpp'],cwd=v12,check=True);print('SYNTAX_OK',mode,flush=True)
            subprocess.run(flags+['-Isrc',str(tmp/'emit.cpp'),'-o',str(tmp/'emit')],cwd=v12,check=True)
            body=subprocess.check_output([tmp/'emit']); assert body.startswith(marker)
            if mode=='off':
                # Device/domain header is frozen T5 fixed-environment input, not a claim of local GPU creation.
                generated=ref[:offset]+body;(R/'v12_off_t5_environment.cl').write_bytes(generated)
                assert generated==ref, 'OFF generator differs from T5 OFF'
                print('OPENCL_OFF_EXACT_T5_FROZEN_HEADER',sha(R/'v12_off_t5_environment.cl'),len(generated),flush=True)
            else:
                assert body.count(b'#ifdef FACADE_FREE_SLIP')==2 and b'facade_eligible' in body
                # Compare ON to actual builder's v11 ON device-independent kernel body.
                (v11/'src/defines.hpp').write_bytes(offbytes.replace(toggle,b'#define FACADE_FREE_SLIP // T9b-build ON'))
                subprocess.run(flags+['-Isrc',str(tmp/'emit.cpp'),'-o',str(tmp/'emit11')],cwd=v11,check=True)
                assert body==subprocess.check_output([tmp/'emit11']);print('OPENCL_ON_BODY_EXACT_V11',flush=True)
        off.write_bytes(offbytes)
        subprocess.run(flags+['-Isrc',str(R/'test_t9b_boundary.cpp'),'-o',str(tmp/'boundary')],cwd=v12,check=True)
        for mode,code in [('good',0),('bad',1)]:
            out=subprocess.run([tmp/'boundary',mode],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);print(out.stdout,end='',flush=True)
            assert out.returncode==code and ('FIRST_STEP_SENTINEL' in out.stdout)==(code==0)
            if code:assert 'bad=1' in out.stdout and 'outer flags audit failed' in out.stdout
            print('BOUNDARY_TEST',mode,'exit',out.returncode,flush=True)
        manifest={str(f.relative_to(v12)):sha(f) for f in sorted(v12.rglob('*')) if f.is_file()}; prev=json.loads((R/'t9b12_manifest.json').read_text())['members'];assert {k for k in manifest.keys()|prev.keys() if manifest.get(k)!=prev.get(k)}==set(files)
        arc=R/'t9b_v12_source.tar.gz'
        with tarfile.open(arc,'w:gz') as t:t.add(v12,arcname=v12.name)
        (R/'t9b_v12_manifest.json').write_text(json.dumps(dict(archive_sha256=sha(arc),base_sha256=V11,members=manifest),indent=2)+'\n');print('V12_SHA',sha(arc),flush=True)
if __name__=='__main__':main()
