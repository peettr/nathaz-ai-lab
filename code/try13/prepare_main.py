#!/usr/bin/env python3
"""Stage isolated production source from prior T4 deck; no solver runs here."""
from pathlib import Path
import shutil, hashlib, json, difflib
R=Path(__file__).resolve().parent
OLD=R.parent/'try7/stage_t4'
DST=R/'main_stage'
FIX=R/'shear_stage/FluidX3D_gate0/src'
assert OLD.is_dir() and FIX.is_dir() and not DST.exists()
shutil.copytree(OLD,DST)
S=DST/'FluidX3D_on/src'
# The approved 4 ground-link loads must exactly match the tested fixture, even
# though the prior production snapshot already contains the corrected values.
a=(S/'kernel.cpp').read_text(); f=(FIX/'kernel.cpp').read_text()
links=('fhn[9]  = load(fi, index_f(j[6], t%2ul ? 15u : 16u));',
       'fhn[16] = load(fi, index_f(j[1], t%2ul ? 10u : 9u));',
       'fhn[11] = load(fi, index_f(j[6], t%2ul ? 17u : 18u));',
       'fhn[18] = load(fi, index_f(j[3], t%2ul ? 12u : 11u));')
for line in links:
 assert a.count(line)==1 and f.count(line)==1, line
# Preserve production predicate (no WALL_GATE0_ALL), append only the gated
# initializer that the fixture actually compiled and executed.
start=f.index(' )+"#ifdef GROUND_WALL_MODEL"+R(\n// Post-initialize repair')
end=f.index(')+"#ifdef GROUND_WALL_MODEL"+R(\n// A specular link is activated',start)
init=f[start:end]
assert 'WALL_GATE0' in init
# Production must not get fixture-only top repair; it has no top mirror.
sub=init.index(')+"#ifdef WALL_GATE0"+R(')
init=init[:sub]+'}\n)+"#endif"+R(\n\n'
marker=')+"#ifdef GROUND_WALL_MODEL"+R(\n// A specular link is activated'
assert a.count(marker)==1
old={n:(S/n).read_text() for n in ('kernel.cpp','lbm.cpp','lbm.hpp')}
(S/'kernel.cpp').write_text(a.replace(marker,init+marker))
for n in ('lbm.cpp','lbm.hpp'):
 p=S/n; t=p.read_text(); fixture=(FIX/n).read_text()
 if n=='lbm.cpp':
  clauses=(('kernel_initialize = Kernel(device, N, "initialize", fi, rho, u, flags);',
            '\n#ifdef GROUND_WALL_MODEL\n\tkernel_ground_initialize_incoming = Kernel(device, N, "ground_initialize_incoming", fi, rho, u, flags);\n#endif'),
           ('void LBM_Domain::enqueue_initialize() { // call kernel_initialize\n\tkernel_initialize.enqueue_run();\n}',
            '\n#ifdef GROUND_WALL_MODEL\nvoid LBM_Domain::enqueue_ground_initialize_incoming() { kernel_ground_initialize_incoming.enqueue_run(); }\n#endif'),
           ('\tcommunicate_fi(); // time step must be odd here',
            '\n#ifdef GROUND_WALL_MODEL\n\tfor(uint d=0u; d<get_D(); d++) lbm_domain[d]->enqueue_ground_initialize_incoming();\n#endif'))
 else:
  clauses=(('Kernel kernel_initialize;', 'Kernel kernel_ground_initialize_incoming;\n\t'),
           ('void enqueue_initialize();', '\n#ifdef GROUND_WALL_MODEL\n\tvoid enqueue_ground_initialize_incoming();\n#endif'))
 for needle,addition in clauses:
  assert t.count(needle)==1 and fixture.count(addition.strip())==1,(n,needle)
  t=t.replace(needle,needle+addition,1) if n=='lbm.cpp' else t.replace(needle,addition+needle,1)
 p.write_text(t)
# Gate must be absent from OFF; source identity retained.
assert '#define GROUND_WALL_MODEL' in (S/'defines.hpp').read_text()
assert '#define WALL_GATE0' not in '\n'.join(x for x in (S/'defines.hpp').read_text().splitlines() if not x.strip().startswith('//'))
assert 'GROUND_WALL_MODEL' not in '\n'.join(x for x in (DST/'FluidX3D_off/src/defines.hpp').read_text().splitlines() if not x.strip().startswith('//'))
for n in old:
 new=(S/n).read_text()
 (R/f'main_{n}.patch').write_text(''.join(difflib.unified_diff(old[n].splitlines(True),new.splitlines(True),fromfile='try7/'+n,tofile='try13_main/'+n)))
hashes={n:hashlib.sha256((S/n).read_bytes()).hexdigest() for n in ('kernel.cpp','lbm.cpp','lbm.hpp','defines.hpp','setup.cpp')}
(DST/'try13_source_manifest.json').write_text(json.dumps(hashes,indent=2)+'\n')
print(json.dumps({'stage':str(DST),'sources':hashes,'fixture_links_verified':len(links),'off_untouched':True},indent=2))
