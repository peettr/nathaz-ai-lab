"""Four full-sized FP32 cases, sequential in one Colab A100 session."""
from pathlib import Path
import tarfile,subprocess,os,time,traceback,json,shutil,math,sys
sys.path.insert(0,'/content')
from extract_precision_full import extract
root=Path('/content/luw_wp1_full');root.mkdir(exist_ok=False)
with tarfile.open('/content/precision_full_inputs.tar.gz') as t:t.extractall(root,filter='data')
summary=[]
for name in ('none','first','second','filtered'):
 try:
  r=root/name;r.mkdir();src=r/'FluidX3D';case=r/'case';shutil.copytree(root/'FluidX3D',src);shutil.copytree(root/'case',case)
  p=src/'src/defines.hpp';s=p.read_text();assert '#define FP16C // optional' in s;s=s.replace('#define FP16C // optional','//#define FP16C // optional');s=s.replace('//#define GROUND_WALL_MODEL // experimental','#define GROUND_WALL_MODEL // experimental' if name!='none' else '//#define GROUND_WALL_MODEL // experimental');
  if name=='second':s=s.replace('//#define GROUND_WALL_SECOND_LAYER','#define GROUND_WALL_SECOND_LAYER')
  if name=='filtered':s=s.replace('//#define GROUND_WALL_FILTER','#define GROUND_WALL_FILTER')
  p.write_text(s)
  env=os.environ.copy()
  if name=='filtered':
   prior=json.loads((root/'second_profile.json').read_text());samples=[x['speed'] for x in prior['rows'] if x['z']==2 and x['x'] in (200,300,400)]
   # Second lattice cell center h_m=1.5 m corresponds to physical z=2 in the existing 0.5-m wall coordinate convention.
   # Capture this explicit mapping for auditing; no extrapolation hidden in the reported alpha.
   ref=sum(samples)/len(samples);alpha=1-math.exp(-ref*.1/3.9286416/10);env['LUW_GROUND_ALPHA']=str(alpha)
   (root/'frozen_alpha.json').write_text(json.dumps(dict(ref_speed_si=ref,alpha=alpha,samples=samples,formula='1-exp(-U_lattice/10)',height_note='physical center z=2m; numerical wall z=0.5m'),indent=2))
  t0=time.monotonic()
  with (r/'build.log').open('w') as f:build=subprocess.run(['make','Linux','-j4'],cwd=src,stdout=f,stderr=subprocess.STDOUT,timeout=360)
  print(name,'BUILD',build.returncode,round(time.monotonic()-t0,2),flush=True);assert build.returncode==0
  t0=time.monotonic()
  with (r/'solver.log').open('w',buffering=1) as f:cp=subprocess.run([str(src/'bin/FluidX3D'),str(case/'conf.luwpf')],cwd=case,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=2400)
  print(name,'SOLVE',cp.returncode,round(time.monotonic()-t0,2),flush=True);assert cp.returncode==0
  extract(case,root/(name+'_profile.json'))
  entry={'name':name,'build_rc':build.returncode,'run_rc':cp.returncode,'seconds':time.monotonic()-t0,'summary':str(root/(name+'_profile.json'))};summary.append(entry)
  (root/'summary.json').write_text(json.dumps(summary,indent=2))
 except Exception:
  print('FAIL',name,traceback.format_exc(),flush=True);(root/'failure.txt').write_text(name+'\n'+traceback.format_exc());break
(root/'done.txt').write_text('COMPLETE' if len(summary)==4 else 'FAIL')
