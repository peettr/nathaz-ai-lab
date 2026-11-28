#!/usr/bin/env python3.10
"""Prepare one private default-OFF source from frozen T5 OFF; never execute solver."""
import hashlib,json,shutil,difflib
from pathlib import Path
from emu_facade import C
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'R21.4a_T5_caseE_WM_retry1/stage/FluidX3D_off'
DEST=ROOT/'FluidX3D_facade_v2'
def patch(p,old,new):
    s=p.read_text();assert s.count(old)==1,(p,s.count(old));p.write_text(s.replace(old,new))
def body():
    z=['// A single flat horizontal facade normal; edges, corners, roofs and ground retain native bounce.',
       'bool facade_eligible(const uxx n, const global uchar* flags, const int axis, const int sign) {',
       '  if((flags[n]&TYPE_BO)!=0u) return false;',
       '  const uint3 xyz=coordinates(n);',
       '  if(xyz.x<=1u||xyz.x+2u>=def_Nx||xyz.y<=1u||xyz.y+2u>=def_Ny||xyz.z<=1u||xyz.z+2u>=def_Nz) return false;',
       '  uxx j[def_velocity_set]; neighbors(n,j);',
       '  const bool xp=(flags[j[1]]&TYPE_BO)==TYPE_S, xm=(flags[j[2]]&TYPE_BO)==TYPE_S;',
       '  const bool yp=(flags[j[3]]&TYPE_BO)==TYPE_S, ym=(flags[j[4]]&TYPE_BO)==TYPE_S;',
       '  if((uint)xp+(uint)xm+(uint)yp+(uint)ym!=1u) return false;',
       '  if((flags[j[5]]&TYPE_BO)==TYPE_S||(flags[j[6]]&TYPE_BO)==TYPE_S) return false;',
       '  return axis==0 ? (sign>0 ? xp : xm) : (sign>0 ? yp : ym);','}']
    return '\n'.join(z)+'\n'
def branch():
    lines=['  // Every mirror read is paired to the preceding store_f of the tangential source.',
           '  // Both endpoints must be flat-face eligible; ambiguous geometry remains native bounce.']
    count=0
    for axis in (0,1):
      for sign in (-1,1):
       norm=tuple(sign if k==axis else 0 for k in range(3))
       inward=tuple(-v for v in norm)
       for i,v in enumerate(C):
        if i<7 or v[axis]!=-sign:continue
        tangent=tuple(v[k]-inward[k] for k in range(3))
        partner=C.index(tuple(-w for w in tangent));wall=C.index(norm)
        upstream=C.index(tuple(-w for w in v))
        m=C.index(tuple(norm[k]+tangent[k] for k in range(3)))
        source='j[%d]'%wall if m%2 else 'j[%d]'%partner
        slot_odd=m if m%2 else m
        slot_even=m+1 if m%2 else m-1
        lines.extend([f'  if(facade_eligible(n,flags,{axis},{sign}) &&',
                      f'     facade_eligible(j[{partner}],flags,{axis},{sign}) &&',
                      f'     (flags[j[{upstream}]]&TYPE_BO)==TYPE_S) ',
                      f'    fhn[{i}]=load(fi,index_f({source},t%2ul ? {slot_odd}u : {slot_even}u)); // from outgoing {m}'])
        count+=1
    assert count==16,count
    return '\n'.join(lines)+'\n'
def main():
    assert BASE.is_dir() and not DEST.exists()
    shutil.copytree(BASE,DEST)
    src=DEST/'src';defines=src/'defines.hpp';lbm=src/'lbm.cpp';kernel=src/'kernel.cpp'
    patch(defines,'//#define GROUND_WALL_MODEL // T5 OFF','//#define GROUND_WALL_MODEL // T5 OFF\n//#define FACADE_FREE_SLIP // T9b-build default OFF')
    patch(lbm,'#ifdef WALL_GATE0\n\t"\\n\t#define WALL_GATE0"', '#ifdef FACADE_FREE_SLIP\n\t"\\n\t#define FACADE_FREE_SLIP"\n#endif\n#ifdef WALL_GATE0\n\t"\\n\t#define WALL_GATE0"')
    # Macro guard in the concatenated C++ source, outside R() stringification.
    patch(kernel,')+R(kernel void stream_collide) + "("',')+"#ifdef FACADE_FREE_SLIP"+R(\n'+body()+')+"#endif"+R(\n)+R(kernel void stream_collide) + "("')
    marker='\tfloat fhn[def_velocity_set]; // local DDFs\n\tload_f(n, fhn, fi, j, t); // perform streaming (part 2)\n\n)+"#ifdef GROUND_WALL_MODEL"+R('
    patch(kernel,marker,marker.replace(')+"#ifdef GROUND_WALL_MODEL"+R(','')+')+"#ifdef FACADE_FREE_SLIP"+R(\n'+branch()+')+"#endif"+R(\n)+"#ifdef GROUND_WALL_MODEL"+R(')
    changed=('defines.hpp','lbm.cpp','kernel.cpp')
    diff=''.join(''.join(difflib.unified_diff((BASE/'src'/x).read_text().splitlines(True),(src/x).read_text().splitlines(True),fromfile='T5_OFF/src/'+x,tofile='facade/src/'+x)) for x in changed)
    (ROOT/'SOURCE_DIFF_v2.patch').write_text(diff)
    manifest={str(p.relative_to(DEST)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DEST.rglob('*')) if p.is_file()}
    (ROOT/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('files',len(manifest),'diff_lines',len(diff.splitlines()),'changed', {x:manifest['src/'+x] for x in changed})
if __name__=='__main__':main()
