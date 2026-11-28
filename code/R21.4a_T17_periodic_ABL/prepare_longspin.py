#!/usr/bin/env python3
"""Prepare a fresh immutable T17 longspin diagnostic from the sealed B source."""
import pathlib,tarfile,shutil,hashlib,json,difflib,datetime
BASE=pathlib.Path(__file__).resolve().parent
OLD=BASE/'stageB_run_20261119_2233'
ROOT=BASE/('longspin_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
ROOT.mkdir(mode=0o755)
with tarfile.open(OLD/'t17b_stage.tar.gz') as t:
    members=[m for m in t if m.name.startswith('pack_stage/periodic_t15_k2/') and (m.isfile() or m.isdir()) and '..' not in pathlib.PurePosixPath(m.name).parts]
    t.extractall(ROOT,members=members,filter='data')
SRC=ROOT/'pack_stage/periodic_t15_k2'
inc=SRC/'src/t17_b_native.inc'
before=inc.read_text()
# Longspin diagnostics share the exact B physics; no V0 decision/restart or producer statistics gate.
start=before.index('    const ulong Tsteps=')
end=before.index('    std::ofstream ledger(',start)
text=before[:start]+'''    const ulong Tsteps=(ulong)std::llround(turnover_steps);
    const ulong half=(ulong)std::llround(half_turnover_steps);
    const ulong total=30ul*Tsteps;
    const ulong window=2ul*Tsteps;
    const ulong sample_stride=200ul, ledger_stride=100ul;
'''+before[end:]
text=text.replace('const ulong total_max=initial+3ul*extension+statsteps;','const ulong total_max=total;')
start=text.index('    ulong equilibrium_end=initial;')
end=text.index('    auto advance=',start)
text=text[:start]+'''    std::ofstream timing(bdir/"timing.csv");
    timing<<"step_T,dt_s,velocity_si_per_lattice,area_cells,sample_stride,mode\\n";
    timing<<Tsteps<<','<<dt_s<<','<<units.si_u(1.0f)<<','<<((ulong)lbm.get_Nx()*lbm.get_Ny())<<','<<sample_stride<<",longspin\\n";
    timing.flush();
'''+text[end:]
start=text.index('    for(uint attempt=')
end=text.index('    return;',start)
text=text[:start]+'''    // Keep one cold-start solver state throughout the entire 30T diagnostic.
    for(ulong w=1ul;w<=15ul;++w) {
        const ulong target=(w==15ul)?total:w*window;
        advance(target,true);
        std::ofstream marker(bdir/("window_"+std::to_string(w)+".ready"));
        marker<<target<<'\\n';marker.close();
        println("T17_LONG_WINDOW "+std::to_string(w)+"/15 step "+std::to_string(target));
    }
    std::ofstream done(bdir/"producer.done");done<<step<<'\\n';done.close();
'''+text[end:]
# Profiles written only on plane sample frames; native ledger always includes 0 and 100-step reads.
inc.write_text(text)
(ROOT/'SOURCE_DIAGNOSTIC.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='stageB_run/t17_b_native.inc',tofile='longspin/t17_b_native.inc')))
# Copy analysis and controller base into a fresh root; prior artifacts remain read-only.
for n in ('native_analysis.py','remote_B.py','controller_native.py','machine.py','assert_T17.py'):
    shutil.copy2(OLD/n,ROOT/n)
archive=ROOT/'longspin_stage.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(SRC,arcname='pack_stage/periodic_t15_k2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'archive_sha256':sha(archive),'source_files':{n:sha(SRC/'src'/n) for n in ('setup.cpp','kernel.cpp','lbm.cpp','defines.hpp','t17_b_native.inc')}}
(ROOT/'longspin_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(ROOT/'SOURCE_SHA256.json').write_text(json.dumps({'original_archive':sha(OLD/'t17b_stage.tar.gz'),'diagnostic_archive':sha(archive),'source':manifest['source_files']},indent=2)+'\n')
print(ROOT)
