#!/usr/bin/env python3
"""Stage only: never runs a solver or Colab. Fail closed on source anchor drift."""
from pathlib import Path
import shutil,math,difflib,hashlib,subprocess,json
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parents[1]/'R21.4a_T17_periodic_ABL/big6v3_periodic_t15_k2_20261121_103455/dry_content_t15_v3/t17b/pack_stage/periodic_t15_k2/src'
REF=ROOT.parents[1]/'wp1_nearwall/wale_fix/stage_FG0W/FluidX3D/src'
OUT=ROOT/'candidates';OUT.mkdir(exist_ok=True)
def replace(s,a,b):
    assert s.count(a)==1,(a[:80],s.count(a))
    return s.replace(a,b)

def wrapped(ref,start,end):
    a=ref.index(start);b=ref.index(end,a)+len(end);return ref[a:b]

def create(name):
    target=OUT/name
    if target.exists():raise FileExistsError(target)
    shutil.copytree(BASE,target,ignore=shutil.ignore_patterns('*.o','*.bin'))
    return target

for label,cs in [('K1a',.13),('K1b',.10)]:
    d=create(label);p=d/'kernel.cpp';s=p.read_text();n=18*math.sqrt(2)*cs*cs
    assert s.count('0.76421222f')==3
    s=s.replace('0.76421222f',f'{n:.9f}f');p.write_text(s)
    (d/'CHANGE.md').write_text(f'{label}: Cs={cs}; coefficient=18*sqrt(2)*Cs²={n:.12g}. Three occurrences in kernel.cpp including harmonic dormant branch; no other code edited.\n')
d=create('K2');p=d/'defines.hpp';s=p.read_text();s=replace(s,'//#define GROUND_WALL_SGS_DAMP // optional','#define GROUND_WALL_SGS_DAMP // optional');p.write_text(s)
(d/'CHANGE.md').write_text('K2: enable pre-existing GROUND_WALL_SGS_DAMP; otherwise base source unchanged.\n')
for name,cw in [('K3a',.20),('K3b',.325)]:
 d=create(name)
 p=d/'defines.hpp';s=p.read_text();s=replace(s,'#define SUBGRID // enables','#define WALE_SGS // TRT, frozen old-step velocity gradient\n#define SUBGRID // enables');s=replace(s,'#define SRT //','#define TRT //\n//#define SRT //') if '#define SRT //' in s else s
 # inspect collision definitions rather than guess
 assert '#define TRT' in s and not any(line.startswith('#define SRT ') for line in s.splitlines())
 p.write_text(s)
 p=d/'kernel.cpp';s=p.read_text();r=(REF/'kernel.cpp').read_text()
 block=wrapped(r,')+"#ifdef WALE_SGS"+R(\n// Fixed old-step velocity-gradient pass',')+"#endif"+R( // WALE_SGS')
 block=block.replace('0.325f*0.325f',f'{cw:.3f}f*{cw:.3f}f')
 # integration all outside R(...) except the OpenCL body.
 s=replace(s,')+R(kernel void initialize)+"("+R(',block+'\n\n)+R(kernel void initialize)+"("+R(')
 sig=wrapped(r,')+"#ifdef WALE_SGS"+R(\n\t, const global float* wale_omega',')+"#endif"+R( // WALE_SGS')
 anchor=')+"#ifdef FORCE_FIELD"+R(\n\t, const global float* F'
 s=replace(s,anchor,sig+'\n'+anchor)
 # Smagorinsky block retained byte-identical when WALE_SGS off.
 marker=')+"#ifdef SUBGRID"+R(\n\t{ // Smagorinsky-Lilly'
 assert marker in s
 s=s.replace(marker,')+"#ifdef SUBGRID"+R(\n)+"#ifndef WALE_SGS"+R(\n\t{ // Smagorinsky-Lilly',1)
 marker=')+"#endif"+R( // SUBGRID\n)+"#if defined(SRT)"+R('
 assert marker in s
 s=s.replace(marker,')+"#endif"+R( // !WALE_SGS\n)+"#endif"+R( // SUBGRID\n)+"#ifdef WALE_SGS"+R(\n\tw=wale_omega[n];\n)+"#endif"+R( // WALE_SGS\n)+"#if defined(SRT)"+R(',1)
 p.write_text(s)
 p=d/'lbm.hpp';s=p.read_text();s=replace(s,'\tKernel kernel_stream_collide;','\tKernel kernel_stream_collide;\n#ifdef WALE_SGS\n\tMemory<float> wale_omega;\n\tKernel kernel_wale_omega;\n#endif');s=replace(s,'\tvoid enqueue_stream_collide();','\tvoid enqueue_stream_collide();\n#ifdef WALE_SGS\n\tvoid enqueue_wale_omega();\n#endif');p.write_text(s)
 p=d/'lbm.cpp';s=p.read_text()
 s=replace(s,'\tkernel_update_fields = Kernel(device, N, "update_fields",', '#ifdef WALE_SGS\n\twale_omega=Memory<float>(device,N);\n\tkernel_wale_omega=Kernel(device,N,"wale_prepare",u,flags,wale_omega);\n#endif\n\tkernel_update_fields = Kernel(device, N, "update_fields",')
 # additional parameter must match signature after existing wall model parameters and before FORCE_FIELD
 s=replace(s,'#ifdef FORCE_FIELD\n\tF = Memory<float>(device, N, 3u);','#ifdef WALE_SGS\n\tkernel_stream_collide.add_parameters(wale_omega);\n#endif\n#ifdef FORCE_FIELD\n\tF = Memory<float>(device, N, 3u);')
 s=replace(s,'void LBM_Domain::enqueue_stream_collide() {','#ifdef WALE_SGS\nvoid LBM_Domain::enqueue_wale_omega() { kernel_wale_omega.enqueue_run(); }\n#endif\nvoid LBM_Domain::enqueue_stream_collide() {')
 s=replace(s,'#ifdef SUBGRID\n\t"\\n\t#define SUBGRID"','#ifdef WALE_SGS\n\t"\\n\t#define WALE_SGS"\n#endif\n#ifdef SUBGRID\n\t"\\n\t#define SUBGRID"')
 s=replace(s,'\tfor(uint d=0u; d<get_D(); d++) lbm_domain[d]->enqueue_stream_collide();','#ifdef WALE_SGS\n\tif(get_D()!=1u) print_error("WALE_SGS single-domain only");\n\tfor(uint d=0u; d<get_D(); d++) lbm_domain[d]->enqueue_wale_omega();\n#endif\n\tfor(uint d=0u; d<get_D(); d++) lbm_domain[d]->enqueue_stream_collide();')
 p.write_text(s)
 (d/'CHANGE.md').write_text(f'{name}: TRT + WALE Cw={cw}; reference {REF}; frozen velocity separate wale_prepare, single-domain guard. Check generated OpenCL and native syntax before GPU.\n')
for name in ['K1a','K1b','K2','K3a','K3b']:
 d=OUT/name
 for fn in ('kernel.cpp','defines.hpp','lbm.cpp','lbm.hpp'):
  diff=''.join(difflib.unified_diff((BASE/fn).read_text().splitlines(True),(d/fn).read_text().splitlines(True),fromfile='baseline/'+fn,tofile=name+'/'+fn))
  (d/(fn+'.diff')).write_text(diff)
print('created',','.join(x.name for x in OUT.iterdir() if x.is_dir()))
