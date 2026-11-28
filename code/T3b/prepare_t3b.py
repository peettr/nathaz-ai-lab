#!/usr/bin/env python3
"""One-time immutable T3b staging; no GPU compute on 工作站."""
from pathlib import Path
import shutil,hashlib,json,tarfile,re,math
R=Path(__file__).resolve().parent; P=R.parent; OLD=P/'run3'; S=P/'run2/stage_fixed'
assert not (R/'stage_fixed').exists(), 'stage already exists; refuse overwrite'
assert not (R/'EXPERIMENT_CARD.md').exists()
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
orig=json.loads((S/'stage_manifest.json').read_text())
assert H(S/'FluidX3D/src/setup.cpp')==orig['setup_sha256']=='81c1b21c97882fb51c6c01c0cbec9facbe15660e4d21872d11a009fe33d57eb5'
shutil.copytree(S,R/'stage_fixed')
T=R/'stage_fixed';man=json.loads((T/'stage_manifest.json').read_text());man['domain_m']=[550,100,270];man['entry_x_m']=5.;man['y_archive_m']=[0,100];man['center_band_y_m']=[40,60]
new={}; records=[]
for name,old in orig['cases'].items():
 seed=103 if name.endswith('101') else 104
 stem=name.replace('s101','s103').replace('s102','s104')
 src=T/name; dest=T/stem; src.rename(dest)
 p=dest/'conf.luwpf';text=p.read_text()
 assert text.count('350.000000')==1 and text.count(f'vk_inlet_seed = {old["seed"]}')==1
 text=text.replace('350.000000','550.000000').replace(f'vk_inlet_seed = {old["seed"]}',f'vk_inlet_seed = {seed}')
 p.write_text(text)
 dx=old['dx']; nx=round(550/dx);ny=round(100/dx);nz=round(270/dx)+old['cells_total']//(round(350/dx)*ny)-round(270/dx)
 cells=old['cells_total']*550//350
 assert cells==nx*ny*(old['cells_total']//(round(350/dx)*ny))
 new[stem]={**old,'seed':seed,'cells_total':cells,'core_cells':old['core_cells']*550//350,'conf_sha256':H(p)}
 records.append((stem,dx,cells,H(p)))
man['cases']=new;man['conservative_total_CU']=orig['conservative_total_CU']*550/350
(T/'stage_manifest.json').write_text(json.dumps(man,indent=2)+'\n')
for old,newname in [('controller_run3.py','controller_t3b.py'),('remote_worker_run3.py','remote_worker_t3b.py'),('launch_run3.py','launch_t3b.py'),('check_run3.py','check_t3b.py'),('ack_run3.py','ack_t3b.py')]:
 text=(OLD/old).read_text()
 text=text.replace('run3','t3b').replace('RUN3','T3B').replace('t3_run3','t3b')
 for a,b in [('s101','s103'),('s102','s104')]: text=text.replace(a,b)
 if old=='remote_worker_run3.py':
  text=text.replace('nx==round(350/dx)','nx==round(550/dx)')
  text=text.replace('ys=np.array([j for j in range(ny) if 40-1e-6<=oy+j*dx<=60+1e-6],dtype=int)','ys=np.arange(ny,dtype=int) # full native y extent, report physical labels')
  assert 'ys=np.arange(ny,dtype=int)' in text
 if old=='controller_run3.py':
  text=text.replace("NAME='luw-r214a-t3r3-prod-1115'","NAME='luw-r214a-t3b-prod-1115'")
  text=text.replace("deadline=start+(55/rate)*3600","deadline=start+(45/rate)*3600")
  text=text.replace("'T3 run3 #current '","'T3b #new '")
  text=text.replace("bundle=R.parent/'run2/stage_fixed_bundle.tar.gz'","bundle=R/'stage_t3b_bundle.tar.gz'")
  text=text.replace("man=json.loads((R.parent/'run2/stage_fixed/stage_manifest.json').read_text())","man=json.loads((R/'stage_fixed/stage_manifest.json').read_text())")
  text=text.replace("R.parent/'run2/stage_fixed'/c/'conf.luwpf'","R/'stage_fixed'/c/'conf.luwpf'")
  text=text.replace("R.parent/'run2/gpu_probe.py'","R.parent/'run2/gpu_probe.py'")
  # Original parser provides vtk_map, unchanged.
  text=text.replace("parser=R.parent/'run2/remote_worker_run2.py'","parser=R.parent/'run2/remote_worker_run2.py'")
  text=text.replace("'/content/t3_run2_parser.py'","'/content/t3_run2_parser.py'")
  # Controller's old two-case conservative guard uses two ref runtimes; keep same safety gate.
  assert "deadline=start+(45/rate)*3600" in text
 if old=='launch_run3.py':
  text=text.replace("remote_worker_run2.py').write_bytes(pathlib.Path('/content/t3_run2_parser.py')", "remote_worker_run2.py').write_bytes(pathlib.Path('/content/t3_run2_parser.py')")
 (R/newname).write_text(text)
# Fix public script references and hard-coded names after exact substitution.
controller=R/'controller_t3b.py';s=controller.read_text();s=s.replace("NAME='luw-r214a-t3r3-prod-1115'","NAME='luw-r214a-t3b-prod-1115'");controller.write_text(s)
ana=(OLD/'analyze_wall_corrected.py').read_text().replace('run3','t3b').replace('RUN3','T3B').replace('s101','s103').replace('s102','s104')
ana=ana.replace("xs=[None,2.,5.,10.,25.,50.,75.,100.,125.,150.,175.,200.,225.,252.1485175,275.,300.,325.,340.]","xs=[1.,2.,5.,10.,25.,50.,75.,100.,125.,150.,175.,200.,225.,252.1485175,275.,300.,325.,340.,400.,450.,500.,540.]")
ana=ana.replace("man=json.loads((R.parent/'run2/stage_fixed/stage_manifest.json').read_text())","man=json.loads((R/'stage_fixed/stage_manifest.json').read_text())")
ana=ana.replace("ys=m['y_indices'];nx=m['dims'][0]","ys=m['y_indices'];nx=m['dims'][0]")
ana=ana.replace("ff0=fluid[ka,:,i];ff1=fluid[ka+1,:,i]","ff0=fluid[ka,:,i];ff1=fluid[ka+1,:,i]\n  selected=np.flatnonzero((oy+np.asarray(ys)*dx>=40-1e-6)&(oy+np.asarray(ys)*dx<=60+1e-6)) if not hasattr(sample,'selected') else sample.selected")
# Replace all-center sampling with y-selection argument, preserving full masks for side probes.
ana=ana.replace("def sample(x,h):","def sample(x,h,band='center'):")
ana=ana.replace("selected=np.flatnonzero((oy+np.asarray(ys)*dx>=40-1e-6)&(oy+np.asarray(ys)*dx<=60+1e-6)) if not hasattr(sample,'selected') else sample.selected","selected=np.flatnonzero((oy+np.asarray(ys)*dx>=40-1e-6)&(oy+np.asarray(ys)*dx<=60+1e-6)) if band=='center' else np.array([int(np.argmin(abs(oy+np.asarray(ys)*dx-float(band))))])")
ana=ana.replace("zip(ys,ff0,ff1)","zip(np.asarray(ys)[selected],ff0[selected],ff1[selected])")
ana=ana.replace("u[ka,:,i,:].astype('f8')+a*u[ka+1,:,i,:].astype('f8')","u[ka,selected,i,:].astype('f8')+a*u[ka+1,selected,i,:].astype('f8')")
ana=ana.replace("'inlet_x_m':inlet['actual_x_m'] if inlet else None","'inlet_x_m':5.,'inlet_G2_at_x5_mps':sample(5.,2.)['G_mps'],'first_full_fluid_x_m':inlet['actual_x_m'] if inlet else None")
ana=ana.replace("result['first_fluid_k_at_xc']=first_fluid_k","result['first_fluid_k_at_xc']=first_fluid_k\n for y in (5.,95.):\n  result[f'side_y{int(y)}_at_xc']=sample(252.1485175,2.,y)\n  result[f'side_y{int(y)}_G_over_center']=result[f'side_y{int(y)}_at_xc']['G_mps']/result['xc_G2_mps'] if result[f'side_y{int(y)}_at_xc']['G_mps'] is not None and result['xc_G2_mps'] else None")
ana=ana.replace("['inlet_G2_mps']","['inlet_G2_at_x5_mps']")
ana=ana.replace("'inlet_x_m':{k:v['inlet_x_m'] for k,v in cases.items()}","'inlet_x_m':5.,'side_G_over_center_at_xc':{k:{'y5':v['side_y5_G_over_center'],'y95':v['side_y95_G_over_center']} for k,v in cases.items()}")
ana=ana.replace("按冻结判据加种子 103","本轮不判，交 Lead 决策")
(R/'analyze_t3b.py').write_text(ana)
# Tar only stage, never cached results.
with tarfile.open(R/'stage_t3b_bundle.tar.gz','w:gz') as tf:
 for p in sorted(T.rglob('*')):
  if p.is_file():tf.add(p,p.relative_to(T))
print('setup_sha256',man['setup_sha256']);print('config',records);print('cells',sum(v['cells_total'] for v in new.values()));print('conservative_run2_scaled_CU',man['conservative_total_CU']);print('bundle',H(R/'stage_t3b_bundle.tar.gz'))
