#!/usr/bin/env python3.10
"""Stage the single-factor facade candidate; never run the solver locally."""
import hashlib, pathlib, shutil, json
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT.parent/'R21.4a_T5_caseE_WM_retry1/stage'
DEST=ROOT/'stage_v3'
V=[(0,0,0),(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,0),(-1,-1,0),(1,0,1),(-1,0,-1),(0,1,1),(0,-1,-1),(1,-1,0),(-1,1,0),(1,0,-1),(-1,0,1),(0,1,-1),(0,-1,1)]
assert len(V)==19 and all(tuple(-a for a in V[i])==V[i+1] for i in range(1,19,2))

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(p,old,new):
 s=p.read_text();assert s.count(old)==1,(p,s.count(old));p.write_text(s.replace(old,new))

def generate():
 # The outgoing partner has the incoming tangential direction but points into the same wall.
 # Esoteric pull: odd outgoing is in solid's slot; even outgoing in source fluid's slot.
 lines=['\t// T9b: flat horizontal facade only. Ground, roofs, corners remain native bounce.',
        '\t// Mirror reads an already-stored outgoing population; never writes fi here.',
        '\tconst uint3 fs_xyz=coordinates(n);',
        '\tif(fs_xyz.x>1u && fs_xyz.x+2u<def_Nx && fs_xyz.y>1u && fs_xyz.y+2u<def_Ny && fs_xyz.z>1u && fs_xyz.z+2u<def_Nz) {',
        '\t const bool fs_xp=(flags[j[1]]&TYPE_BO)==TYPE_S, fs_xm=(flags[j[2]]&TYPE_BO)==TYPE_S;',
        '\t const bool fs_yp=(flags[j[3]]&TYPE_BO)==TYPE_S, fs_ym=(flags[j[4]]&TYPE_BO)==TYPE_S;',
        '\t const bool fs_one=(uint)fs_xp+(uint)fs_xm+(uint)fs_yp+(uint)fs_ym==1u;',
        '\t if(fs_one) {']
 for i,v in enumerate(V):
  if i<7:continue
  for axis in (0,1):
   if not v[axis]:continue
   norm=tuple((-v[axis] if k==axis else 0) for k in range(3))
   tang=tuple(v[k] if k!=axis else 0 for k in range(3))
   reflect=tuple(norm[k]+tang[k] for k in range(3))
   try: m=V.index(reflect)
   except ValueError:continue
   assert m!=i and m>0
   wallidx=V.index(norm); opp_t=V.index(tuple(-x for x in tang))
   # incoming q has upstream solid along -q; normal towards wall is -q_normal.
   # Source cell is n-tangent. For odd outgoing the previous store reached solid n+normal;
   # for even outgoing it remains at source n-tangent.
   source=f'j[{wallidx}]' if m%2 else f'j[{opp_t}]'
   slot_even=m+1 if m%2 else m-1
   slot_odd=m
   # Require source fluid plus its normal-neighbor solid, and a non-corner base.
   off=f'(fs_xyz.x{("+" if -tang[0]>=0 else "-")}{abs(tang[0])}u, fs_xyz.y{("+" if -tang[1]>=0 else "-")}{abs(tang[1])}u, fs_xyz.z{("+" if -tang[2]>=0 else "-")}{abs(tang[2])}u)'
   # Construct source index through D3Q19 neighbor in opposite tangential direction.
   source_fluid=f'j[{opp_t}]'
   xyz=f'coordinates({source_fluid})'
   # For corner exclusion test cardinal normal at source, plus three others.
   c=f'fs_{"xp" if norm[0]==1 else "xm" if norm[0]==-1 else "yp" if norm[1]==1 else "ym"}'
   # Check reciprocal source's cardinal neighborhood with periodic index math, avoiding ambiguous corner ownership.
   # No change on diagonal if source is solid or diagonal upstream isn't solid.
   upstream=V.index(tuple(-x for x in v))
   reciprocal=V.index(tuple(norm[k]-tang[k] for k in range(3)))
   lines.append(f'\t  if({c} && (flags[j[{upstream}]]&TYPE_BO)==TYPE_S && '
                f'(flags[{source_fluid}]&TYPE_BO)==0u && (flags[j[{reciprocal}]]&TYPE_BO)==TYPE_S) '
                f'fhn[{i}]=load(fi,index_f({source}, t%2ul ? {slot_odd}u : {slot_even}u)); '
                f'// normal={norm}, mirror_out={m}')
 lines+=['\t }','\t}']
 return '\n'.join(lines)+'\n'

def main():
 assert BASE.exists() and not DEST.exists()
 shutil.copytree(BASE,DEST,symlinks=False)
 src=DEST/'FluidX3D_off/src';on=DEST/'FluidX3D_on'
 # The stage carries an on-tree that must not be used; remove only this *new* staged duplicate.
 shutil.rmtree(on)
 defines=src/'defines.hpp';replace(defines,'//#define WALL_GATE0', '//#define FACADE_FREE_SLIP // T9b default OFF\n//#define WALL_GATE0')
 lbm=src/'lbm.cpp';replace(lbm,'#ifdef WALL_GATE0\n\t"\\n\t#define WALL_GATE0"', '#ifdef FACADE_FREE_SLIP\n\t"\\n\t#define FACADE_FREE_SLIP"\n#endif\n#ifdef WALL_GATE0\n\t"\\n\t#define WALL_GATE0"')
 kernel=src/'kernel.cpp'
 needle='\tconst uchar flagsn_bo=flagsn&TYPE_BO, flagsn_su=flagsn&TYPE_SU; // extract boundary and surface flags\n\tif(flagsn_bo==TYPE_S||flagsn_su==TYPE_G) return; // if cell is solid boundary or gas, just return\n\n\tuxx j[def_velocity_set]; // neighbor indices\n\tneighbors(n, j); // calculate neighbor indices\n\n\tfloat fhn[def_velocity_set]; // local DDFs\n\tload_f(n, fhn, fi, j, t); // perform streaming (part 2)\n'
 replace(kernel,needle,needle+')+"#ifdef FACADE_FREE_SLIP"+R(\n'+generate()+')+"#endif"+R( // FACADE_FREE_SLIP\n')
 out={'baseline':str(BASE),'files':{x:sha(src/x) for x in ('defines.hpp','lbm.cpp','kernel.cpp')},'mapped_links':generate().count('mirror_out=')}
 (ROOT/'stage_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(out,indent=2))
if __name__=='__main__':main()
