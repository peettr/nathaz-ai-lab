from pathlib import Path
import shutil, datetime, re, hashlib, json, tarfile, subprocess
P=Path(__file__).resolve().parent
old=P/'build11_20261117_141636'
R=P/('build12_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
R.mkdir(exist_ok=False)
shutil.copytree(old/'FluidX3D_facade_v10',R/'FluidX3D_facade_v11')
s=R/'FluidX3D_facade_v11/src/setup.cpp'
t=s.read_text()
a='    const std::string output=std::getenv("T9B_GATE_OUTPUT")'
assert t.count(a)==1
t=t.replace(a,'''    // Test-only initialization: seed solid DDF slots with the same uniform
    // fluid equilibrium already produced by the native initialize kernel.
    // Do not change solid u: no moving-wall ambiguity, and no city-path change.
    gate.run(0u,100u);
    auto& initial_fi=gate.lbm_domain[0]->diagnostic_fi();
    initial_fi.add_host_buffer();
    initial_fi.read_from_device();
    const ulong fluid_reference=gate.index(4u,4u,4u);
    if(gate.flags[fluid_reference]&TYPE_S)print_error("test equilibrium reference is solid");
    ulong initialized_solid=0u;
    for(ulong n=0;n<gate.get_N();n++)if(gate.flags[n]&TYPE_S) {
        for(uint q=0u;q<19u;q++)
            initial_fi[(ulong)q*gate.get_N()+n]=initial_fi[(ulong)q*gate.get_N()+fluid_reference];
        initialized_solid++;
    }
    initial_fi.write_to_device();
    println("FACADE_INITIALIZED_SOLID_DDF "+to_string(initialized_solid));
'''+a)
# reference (4,4,4) fluid for channel x/y and cube; guard above.
# Existing diagnostics share the same already allocated host buffer.
t=t.replace('    auto& fi=gate.lbm_domain[0]->diagnostic_fi();\n','    auto& fi=initial_fi;\n')
t=t.replace('        if(step==0u) fi.add_host_buffer();\n','')
s.write_text(t)
for n in ('worker_gate.py','controller_gate.py','launch_gate.py','probe_gate.py','protocol_dryrun.py','local_preflight.py','emit_opencl.cpp','emit_t5.cpp'):
 x=(old/n).read_text()
 for a,b in [('t9b11','t9b12'),('T9b build11','T9b build12'),('build11','build12'),('facade_v10','facade_v11'),('luw-t9b11-g4-1117-a1','luw-t9b12-g4-1117-a1')]:x=x.replace(a,b)
 if n=='local_preflight.py':
  x=x.replace("V6=R.parent/'build6_20261117_123412/FluidX3D_facade_v6/src'", "V6=R.parent/'build6_20261117_123412/FluidX3D_facade_v6/src'")
  x=x.replace("assert src[src.index(start):src.index(end,src.index(start))]==v6[v6.index(start):v6.index(end,v6.index(start))]", "assert src[src.index(start):src.index(end,src.index(start))]==v6[v6.index(start):v6.index(end,v6.index(start))]")
  x=x.replace("assert not any('t9b10'", "assert not any('t9b10'")
 (R/n).write_text(x)
for n in ('generated_off.cl','generated_t5.cl','generated_v6.cl','generated_v6_on.cl','generated_t5_preprocessed.cl'):
 shutil.copy2(old/n,R/n)
# Generate v11 OpenCL text using emitter pointing to the new kernel.
x=(R/'emit_opencl.cpp').read_text().replace('FluidX3D_facade_v10','FluidX3D_facade_v11')
(R/'emit_opencl.cpp').write_text(x)
for n in ('generated_off.cl',):
 # kernel itself is byte-identical so preserved prior generated text is exact.
 pass
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with tarfile.open(R/'t9b12_source.tar.gz','w:gz') as tf:tf.add(R/'FluidX3D_facade_v11',arcname='FluidX3D_facade_v11')
S=R/'FluidX3D_facade_v11'
(R/'t9b12_manifest.json').write_text(json.dumps({'archive_sha256':sha(R/'t9b12_source.tar.gz'),'members':{p.relative_to(S).as_posix():sha(p) for p in S.rglob('*') if p.is_file()}},indent=2)+'\n')
for n in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp'):
 a=old/'FluidX3D_facade_v10/src'/n;b=S/'src'/n
 d=subprocess.run(['diff','-u','--label','v10/src/'+n,'--label','v11/src/'+n,str(a),str(b)],capture_output=True,text=True)
 assert d.returncode in (0,1)
 with (R/'diff_vs_v10.patch').open('a') as f:f.write(d.stdout)
assert sha(S/'src/kernel.cpp')==sha(old/'FluidX3D_facade_v10/src/kernel.cpp')
assert sha(S/'src/lbm.cpp')==sha(old/'FluidX3D_facade_v10/src/lbm.cpp')
assert sha(S/'src/defines.hpp')==sha(old/'FluidX3D_facade_v10/src/defines.hpp')
print(R)
print('archive_sha256',sha(R/'t9b12_source.tar.gz'),'diff_sha256',sha(R/'diff_vs_v10.patch'))
