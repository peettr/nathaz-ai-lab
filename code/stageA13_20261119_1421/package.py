from pathlib import Path
import hashlib,json,subprocess,tarfile,difflib
r=Path(__file__).resolve().parent
prev=r.parent/'stageA12_20261119_133203'
ref=r.parent.parent/'R21.4a_T15_second_layer_WM/continuation8b_20261119_0026'
pack=r/'work/pack_stage'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report={}
emit=r.parent/'stageA9_20261119_101411/emit_kernel.cpp'
for v,tag in [('legacy_off','off'),('legacy_on','on'),('legacy_k3','k3')]:
    src=pack/v/'src'
    binary=r/(v+'_emitter')
    subprocess.run(['g++','-std=c++17',str(src/'kernel.cpp'),str(emit),'-o',str(binary)],check=True)
    output=r/(v+'_generated.cl')
    subprocess.run([str(binary),str(output)],check=True)
    reference=ref/(tag+'_new_kernel_container.cl')
    report[v]={'new_sha256':h(output),'reference_sha256':h(reference),'byte_equal':output.read_bytes()==reference.read_bytes()}
assert all(a['byte_equal'] for a in report.values()),report
(r/'LEGACY_BYTE_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
variants={}
for v in ('periodic_bounce','periodic_t4','periodic_t15_k2','periodic_t15_k3'):
    src=pack/v/'src'
    log=r/(v+'_syntax.log')
    cmd=['g++','-std=c++17','-fsyntax-only','-I',str(src/'OpenCL/include'),'-I',str(src),str(src/'kernel.cpp'),str(src/'lbm.cpp'),str(src/'setup.cpp')]
    p=subprocess.run(cmd,capture_output=True,text=True)
    log.write_text(' '.join(cmd)+'\nexit='+str(p.returncode)+'\n'+p.stdout+p.stderr)
    assert p.returncode==0,(v,p.stderr[-1000:])
    variants[v]={f:h(src/f) for f in ('defines.hpp','kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp')}
with tarfile.open(r/'t17_stage.tar.gz','w:gz') as t:t.add(pack,arcname='pack_stage')
manifest={'archive_sha256':h(r/'t17_stage.tar.gz'),'variants':variants}
(r/'t17_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
base=prev/'dry_content/t17/pack_stage'
with (r/'SOURCE_vs_A12.diff').open('w') as f:
    for v in variants:
        for fn in ('kernel.cpp','lbm.cpp','lbm.hpp','setup.cpp'):
            a=(base/v/'src'/fn).read_text().splitlines(True)
            b=(pack/v/'src'/fn).read_text().splitlines(True)
            f.writelines(difflib.unified_diff(a,b,fromfile='A12/'+v+'/'+fn,tofile='A13/'+v+'/'+fn))
print('SEALED',manifest['archive_sha256'],report)
