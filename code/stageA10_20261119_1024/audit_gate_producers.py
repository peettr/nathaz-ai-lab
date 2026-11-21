#!/usr/bin/env python3
"""Fail-closed audit of stage-A native producers and fixture semantics."""
from pathlib import Path
import hashlib,json,re,sys
R=Path(__file__).resolve().parent
A9=R.parent/'stageA9_20261119_101411'
T15=R.parents[1]/'R21.4a_T15_second_layer_WM/continuation8b_20261119_0026'
src=R/'stage/FluidX3D_on/src'
read=lambda p:p.read_text()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
setup=read(src/'setup.cpp');kernel=read(src/'kernel.cpp')
old=read(T15/'stage/FluidX3D_e3/src/setup.cpp')
checks={
 'a9_source_copy_sha_equal':all(sha(src/n)==sha(A9/'stage/FluidX3D_on/src'/n) for n in ('setup.cpp','kernel.cpp','defines.hpp','lbm.cpp')),
 'production_periodic_ledger_present':'T17_LEDGER_CSV' in setup and 'T17_DIAGNOSTIC_STEPS' in setup,
 'native_a4_trace_producer_present':all(s in setup for s in ('t15_e3_force_tau.csv','t15_e3_evolution.csv','t15_e3_top_shear.csv')),
 'native_a4_fixture_macro_present':bool(re.search(r'\b(T17_E3_FIXTURE|E3_PERIODIC_GROUND)\b',setup)),
 'old_fixture_trace_producer_present':all(s in old for s in ('t15_e3_force_tau.csv','t15_e3_evolution.csv','t15_e3_top_shear.csv')),
 'old_fixture_has_periodic_abl_macro': 'PERIODIC_ABL_GROUND' in old,
 'periodic_setup_wins_before_wall_gate0':setup.index('#ifdef PERIODIC_ABL_GROUND')<setup.index('#ifdef WALL_GATE0'),
 'periodic_source_uses_256_domain':'LBM lbm(256u,128u,66u' in setup,
 'a6_phaseB_sampling_output_present':bool(re.search(r'T17_(?:TKE|PROFILE|STAT|SAMPLE)',setup)),
}
report={'checks':checks,'source_sha256':{n:sha(src/n) for n in ('setup.cpp','kernel.cpp','defines.hpp','lbm.cpp')},'a9_preflight_sha256':sha(A9/'PREFLIGHT_RESULT_A9.json'),'old_e3_fixture_source':str(T15/'stage/FluidX3D_e3/src/setup.cpp'),'findings':['A9 periodic setup emits only T17_LEDGER_CSV and has no E3-prime native per-step trace/evolution/top producer.','T15 E3-prime producer exists in a different WALL_GATE0 fixture source, with TYPE_E top and different macro path; it cannot be silently substituted for E3-prime on PERIODIC_ABL_GROUND.','A9 periodic setup hardcodes 256x128x66 and has no small-case switch, so A4 cannot be exercised by worker orchestration alone.','A6 full phase-B sampling path is not wired into the periodic setup.']}
(R/'GATE_PRODUCER_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
if not (checks['native_a4_trace_producer_present'] and checks['native_a4_fixture_macro_present']):sys.exit(2)
