from pathlib import Path
import hashlib,json,shutil,tarfile,difflib,subprocess,re
R=Path(__file__).resolve().parent
S=Path((R/'SOURCE_ROOT.txt').read_text().strip());P=R/'pack_stage'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for variant in ('B0','K1a','K1b','K2','K3a','K3b'):
 p=P/variant/'src/kernel.cpp'; t=p.read_text(); old='wall_xyz.z+def_Oz>=def_wale_ground_first_z && wall_xyz.z+def_Oz<=def_wale_ground_first_z+2u'; new='wall_xyz.z+def_Oz>=def_ground_first_fluid_z && wall_xyz.z+def_Oz<=def_ground_first_fluid_z+2u';assert t.count(old)==1; p.write_text(t.replace(old,new))
 assert subprocess.run(['g++','-std=c++17','-fsyntax-only',str(p)],capture_output=True).returncode==0
 if variant in ('K3a','K3b'):
  q=P/variant/'src/t17_b_native.inc'; text=q.read_text();assert text.count('if(mode!="smoke" && mode!="production")')==1
  text=text.replace('if(mode!="smoke" && mode!="production")','if(mode!="smoke" && mode!="production" && mode!="compilecheck")')
  text=text.replace('const ulong initial=(mode=="smoke")?53851ul:25ul*Tsteps;', 'const ulong initial=(mode=="compilecheck")?10ul:((mode=="smoke")?53851ul:25ul*Tsteps);')
  text=text.replace('const ulong statsteps=(mode=="smoke")?0ul:4ul*half;', 'const ulong statsteps=(mode=="smoke" || mode=="compilecheck")?0ul:4ul*half;')
  text=text.replace('if(mode=="smoke" && (step%1000ul==0ul || step==target))','if((mode=="smoke" || mode=="compilecheck") && (step%1000ul==0ul || step==target))')
  text=text.replace('if(mode=="smoke") {\n        advance(initial,false);','if(mode=="smoke" || mode=="compilecheck") {\n        advance(initial,false);')
  q.write_text(text)
# Check six candidate-off emitted container against archived frozen B0 baseline, with disposable defines.
prep=S.parents[1]/'prep_20261123_0025'; base=S.parent/'run_20261123_0100_v3/BASE.cl'; original=base.read_bytes(); gate=R/'macro_off';gate.mkdir()
reports=[]
for v in ('B0','K1a','K1b','K2','K3a','K3b'):
 d=gate/v;shutil.copytree(P/v,d); h=d/'src/defines.hpp';txt=h.read_text()
 for macro in ('T18_CS013','T18_CS010','T18_TRT_WALE','T18_CW325','GROUND_WALL_SGS_DAMP'):txt=re.sub(r'^#define '+macro+r'\s*\n','',txt,flags=re.M)
 h.write_text(txt)
 exe=gate/(v+'.emit'); c=subprocess.run(['g++','-std=c++17',str(d/'src/kernel.cpp'),str(prep/'dump_opencl.cpp'),'-o',str(exe)],capture_output=True,text=True);assert c.returncode==0,(v,c.stderr[:200])
 out=subprocess.run([str(exe)],capture_output=True);hsh=hashlib.sha256(out.stdout).hexdigest();reports.append({'variant':v,'off_sha':hsh,'baseline_sha':hashlib.sha256(original).hexdigest(),'byte_equal':out.stdout==original,'gxx_rc':0});assert out.returncode==0 and out.stdout==original,(v,hsh)
(R/'MACRO_OFF_CHECK.json').write_text(json.dumps(reports,indent=2)+'\n')
(R/'K3_FIX.diff').write_text(''.join(''.join(difflib.unified_diff((S/'pack_stage'/v/'src'/name).read_text().splitlines(True),(P/v/'src'/name).read_text().splitlines(True),fromfile='old/'+v+'/'+name,tofile='new/'+v+'/'+name)) for v in ('K3a','K3b') for name in ('kernel.cpp','t17_b_native.inc')))
# Frozen archive/manifest, all members held in fresh root.
m=json.loads((S/'t17b_manifest.json').read_text());m['variants']={v:{f.name:sha(f) for f in (P/v/'src').iterdir() if f.is_file()} for v in m['variant_names'].values()}
a=R/'t17b_stage.tar.gz'
with tarfile.open(a,'w:gz') as tf:tf.add(P,arcname='pack_stage')
m['archive_sha256']=sha(a);(R/'t17b_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print('PREP_K3_OK',sha(a),len(reports))
