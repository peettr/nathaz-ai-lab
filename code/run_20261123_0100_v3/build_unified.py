#!/usr/bin/env python3
"""Build T18 unified source in a fresh run root; no solver execution."""
from pathlib import Path
import shutil, difflib, hashlib, json, subprocess, re
R=Path(__file__).resolve().parent
P=R.parents[1]/'prep_20261123_0025'
BASE=R.parents[2]/'R21.4a_T17_periodic_ABL/big6v3_periodic_t15_k2_20261121_103455/dry_content_t15_v3/t17b/pack_stage/periodic_t15_k2'
assert BASE.is_dir(), BASE
SRC=R/'unified'
if SRC.exists(): raise FileExistsError(SRC)
shutil.copytree(BASE,SRC)
K=P/'candidates/K3a'
for name in ('kernel.cpp','lbm.cpp','lbm.hpp'):
 shutil.copyfile(K/name,SRC/'src'/name)
# K3a has a fixed Cw=0.20, selected by a compile-time macro outside R(...).
p=SRC/'src/kernel.cpp';s=p.read_text()
old=' const float nut=0.200f*0.200f*numerator/denominator;'
if old not in s:
 for line in s.splitlines():
  if '0.200f' in line: print('CW_LINE',line)
 raise ValueError('Cw anchor changed')
s=s.replace(old,')+"#ifdef T18_CW325"+R(\n const float nut=0.325f*0.325f*numerator/denominator;\n)+"#else"+R(\n'+old+'\n)+"#endif"+R(',1)
# Only active T18_CS macros change the source text. The disabled branch emits the exact old literal.
needle='0.76421222f*sgs_length_factor*sqrt(Q)/rhon'
assert s.count(needle)==1
s=s.replace('w = 2.0f/(tau0+sqrt(sq(tau0)+'+needle+'));',
''')+"#if defined(T18_CS013)"+R(
		w = 2.0f/(tau0+sqrt(sq(tau0)+0.430203766f*sgs_length_factor*sqrt(Q)/rhon));
)+"#elif defined(T18_CS010)"+R(
		w = 2.0f/(tau0+sqrt(sq(tau0)+0.254558f*sgs_length_factor*sqrt(Q)/rhon));
)+"#else"+R(
		w = 2.0f/(tau0+sqrt(sq(tau0)+0.76421222f*sgs_length_factor*sqrt(Q)/rhon));
)+"#endif"+R(''',1)
p.write_text(s)
# WALE infrastructure is guarded by WALE_SGS in K3a; map T18 variants to that existing macro.
p=SRC/'src/defines.hpp';s=p.read_text()
s=s.replace('#define SRT // choose single-relaxation-time LBM collision operator; (default)', '''#if defined(T18_TRT_WALE)
#define TRT // T18 combination candidate
#define WALE_SGS // frozen old-step gradient
#else
#define SRT // choose single-relaxation-time LBM collision operator; (default)
#endif''',1)
assert '#define WALE_SGS // frozen' in s
s += '''
// T18 switches are introduced by candidate-specific compiler flags before this header.
#if defined(T18_CS013) && defined(T18_CS010)
#error Conflicting T18 Cs candidates
#endif
'''
p.write_text(s)
# Config variants are separate copies of the same unified source with defines-only macro switches.
variants={'B0':'','K1a':'#define T18_CS013\n','K1b':'#define T18_CS010\n','K2':'#define GROUND_WALL_SGS_DAMP\n','K3a':'#define T18_TRT_WALE\n','K3b':'#define T18_TRT_WALE\n#define T18_CW325\n'}
for name,extra in variants.items():
 d=R/'variants'/name
 shutil.copytree(SRC,d)
 if extra:
  p=d/'src/defines.hpp';q=p.read_text();p.write_text(q.replace('#pragma once\n','#pragma once\n'+extra,1))
for name in ('kernel.cpp','lbm.cpp','lbm.hpp','defines.hpp'):
 a=(BASE/'src'/name).read_text().splitlines(True);b=(SRC/'src'/name).read_text().splitlines(True)
 (R/(name+'.diff')).write_text(''.join(difflib.unified_diff(a,b,fromfile='baseline/'+name,tofile='unified/'+name)))
manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(R.glob('variants/*/src/*')) if p.is_file()}
(R/'SOURCE_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('variants',list(variants),'source files',len(manifest))
