#!/usr/bin/env python3
"""Static staging only: no solver, no previous run modifications."""
import pathlib,shutil,json,hashlib,tarfile
R=pathlib.Path(__file__).resolve().parent
BASE=R.parent.parent/'R21.4a_T3_emptyground/T3d/stage_fixed'
T4=R.parent/'try13/main_smoke_fix1/stage_t4/FluidX3D_on'
DEST=R/'stage'
assert not DEST.exists()
assert (BASE/'stage_manifest.json').is_file() and (T4/'src/defines.hpp').is_file()
shutil.copytree(BASE,DEST,symlinks=True)
shutil.rmtree(DEST/'FluidX3D')
shutil.copytree(T4,DEST/'FluidX3D_on',symlinks=True)
# Source copy for A differs only by the wall switch; no second-layer switch.
shutil.copytree(T4,DEST/'FluidX3D_off',symlinks=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
expected=json.loads((T4.parent/'try13_source_manifest.json').read_text())
for name,digest in expected.items():assert sha(DEST/'FluidX3D_on/src'/name)==digest,name
p=DEST/'FluidX3D_off/src/defines.hpp'
s=p.read_text();old='#define GROUND_WALL_MODEL // T4 linked flat-ground specular reflection + log-stress; default OFF in source'
assert s.count(old)==1
p.write_text(s.replace(old,'//#define GROUND_WALL_MODEL // phase A: disabled'))
assert 'GROUND_WALL_SECOND_LAYER // ' not in s or '//#define GROUND_WALL_SECOND_LAYER' in s
# Audit eligible columns before time stepping, after the native post-BC mask exists.
p=DEST/'FluidX3D_on/src/setup.cpp';s=p.read_text();needle='if(ok && (lbm.flags[below+1]&TYPE_S)!=0u && (lbm.flags[below-1]&TYPE_S)!=0u &&\n                       (lbm.flags[below+nx]&TYPE_S)!=0u && (lbm.flags[below-nx]&TYPE_S)!=0u) eligible++;'
assert s.count(needle)==1
# Add an independent exhaustive CSV, with reason codes matching the device predicate.
start='const long long plane=nx*ny;\n                ulong eligible=0ul;'
assert s.count(start)==1
s=s.replace(start,start+'\n                std::filesystem::create_directories(parent+"/RESULTS");\n                std::ofstream excluded(parent+"/RESULTS/ground_excluded.csv");\n                excluded<<"x_index,y_index,x_m,y_m,reason\\n";')
s=s.replace('x*cell_size','x*cell_m').replace('y*cell_size','y*cell_m')
# existing short-circuit exits need their own recorded labels
s=s.replace('if((lbm.flags[n]&(TYPE_S|TYPE_E))!=0u || (lbm.flags[below]&TYPE_S)==0u) continue;', 'if((lbm.flags[n]&(TYPE_S|TYPE_E))!=0u) { excluded<<x<<","<<y<<","<<x*cell_size<<","<<y*cell_size<<",first_layer_not_fluid\\n"; continue; }\n                    if((lbm.flags[below]&TYPE_S)==0u) { excluded<<x<<","<<y<<","<<x*cell_size<<","<<y*cell_size<<",ground_below_not_solid\\n"; continue; }')
s=s.replace('if(ok && (lbm.flags[below+1]&TYPE_S)!=0u && (lbm.flags[below-1]&TYPE_S)!=0u &&\n                       (lbm.flags[below+nx]&TYPE_S)!=0u && (lbm.flags[below-nx]&TYPE_S)!=0u) eligible++;', 'if(!ok) { excluded<<x<<","<<y<<","<<x*cell_size<<","<<y*cell_size<<",neighbor_not_fluid\\n"; continue; }\n                    if((lbm.flags[below+1]&TYPE_S)==0u || (lbm.flags[below-1]&TYPE_S)==0u || (lbm.flags[below+nx]&TYPE_S)==0u || (lbm.flags[below-nx]&TYPE_S)==0u) { excluded<<x<<","<<y<<","<<x*cell_size<<","<<y*cell_size<<",neighbor_below_not_solid\\n"; continue; }\n                    eligible++;')
s=s.replace('ef.flush(); if(!ef) print_error("ground eligibility diagnostic write failed");','ef.flush(); excluded.flush(); if(!ef || !excluded) print_error("ground eligibility diagnostic write failed");')
# Early creation of RESULTS already occurs before this section in main code; confirm when auditing.
# x/y physical coordinates use the executed cell_m; all other source is unchanged.
s=s.replace('x*cell_size','x*cell_m').replace('y*cell_size','y*cell_m')
p.write_text(s)
manifest={'source_on':{n:sha(DEST/'FluidX3D_on/src'/n) for n in expected},'source_off':{n:sha(DEST/'FluidX3D_off/src'/n) for n in expected},'cases':json.loads((DEST/'stage_manifest.json').read_text())['cases'],'baseline_thin_sha256':sha(R.parent.parent/'R21.4a_T3_emptyground/T3d/dx1p0_s107_thin.npz')}
(DEST/'phase_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=R/'stage_phase.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(DEST,arcname='stage')
(R/'archive.json').write_text(json.dumps({'sha256':sha(archive),'size':archive.stat().st_size})+'\n')
print(json.dumps({'archive':sha(archive),'source_on':manifest['source_on'],'baseline':manifest['baseline_thin_sha256']},indent=2))
