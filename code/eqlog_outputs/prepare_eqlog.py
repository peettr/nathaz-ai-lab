from pathlib import Path
import subprocess,shutil,tarfile,math,json,struct
R=Path(__file__).resolve().parent
repo=R.parent/'LatticeUrbanWind_repo'
stage=R/'stage'; assert not stage.exists()
stage.mkdir()
# Restore missing tracked build dependencies from the pinned HEAD in a fresh tree.
p=subprocess.run(['git','archive','HEAD','core/cfd_core/FluidX3D'],cwd=repo,stdout=subprocess.PIPE,check=True)
with (R/'source_HEAD.tar').open('wb') as f:f.write(p.stdout)
with tarfile.open(R/'source_HEAD.tar') as t:t.extractall(stage,filter='data')
# Apply archived solver diff, including setup and kernel, to the clean HEAD tree.
with (R.parent/'solver_wallmodel_cont5_final.diff').open('rb') as f:
 subprocess.run(['git','apply','--directory=', '-'],cwd=stage,input=f.read(),check=True)
src=stage/'core/cfd_core/FluidX3D';assert (src/'src/setup.cpp').exists() and (src/'src/kernel.cpp').exists()
base=repo/'examples/example_ProfileResearch_noDEM'
case=stage/'case';(case/'wind_bc').mkdir(parents=True);(case/'proj_temp').mkdir()
shutil.copy2(base/'conf.luwpf',case/'conf.luwpf')
# No building mesh: empty field built from a flat base, same as prior cont5 procedure.
blob=subprocess.run(['git','show','HEAD:examples/example_ProfileResearch_noDEM/proj_temp/CaseE_PF.stl'],cwd=repo,stdout=subprocess.PIPE,check=True).stdout
n=struct.unpack_from('<I',blob,80)[0];assert n==9210
tri=bytearray(blob[84+(n-12)*50:]);assert len(tri)==600
for i in range(12):
 for j in range(3):
  for axis,oldval,newval in ((0,2022.5001,500.),(1,1996.5001,200.)):
   off=i*50+12+j*12+axis*4;v=struct.unpack_from('<f',tri,off)[0]
   assert min(abs(v),abs(v-oldval))<.02,(i,j,axis,v)
   struct.pack_into('<f',tri,off,0. if abs(v)<.02 else newval)
(case/'proj_temp/CaseE_PF.stl').write_bytes(blob[:80]+struct.pack('<I',12)+tri)
conf=case/'conf.luwpf';s=conf.read_text()
for old,new in [('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 500.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 200.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('angle = [0, 90, 180, 270]','angle = [270]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 1.0\n')]:
 assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
s+='\nrun_nstep = 31000\npurge_avg = 20000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\nvk_inlet_ti = 0.1621087892\nvk_inlet_l = 100.0\nvk_inlet_inflow_only = true\nvk_inlet_face_mode = TARGET_INFLOW\n'
conf.write_text(s)
z0=.024;k=.4;uref=3.9286416;ustar=uref*k/math.log((15.9+z0)/z0)
# LUW profile parser linearly interpolates; 0.1m spacing limits interpolation error.
pf=case/'wind_bc/profile.dat';pf.write_text('z,U\n'+''.join(f'{i/10:.1f}\t{ustar/k*math.log((i/10+z0)/z0):.10f}\n' for i in range(0,3001)))
(R/'parameters.json').write_text(json.dumps({'z0_m':z0,'kappa':k,'Uref_mps':uref,'ustar_mps':ustar,'profile_spacing_m':.1,'source_diff':str(R.parent/'solver_wallmodel_cont5_final.diff')},indent=2))
# Stage minimal solver tree + deck only, with reference files untouched.
with tarfile.open(R/'eqlog_inputs.tar.gz','w:gz') as t:
 t.add(src,arcname='FluidX3D');t.add(case,arcname='case')
print('archive', (R/'eqlog_inputs.tar.gz').stat().st_size,'ustar',ustar,'mesh',list((case/'proj_temp').iterdir()))
