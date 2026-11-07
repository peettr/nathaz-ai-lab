from pathlib import Path
import shutil, subprocess, hashlib
base=Path(__file__).resolve().parent
src=Path('./24_Urban_Wind_LBM/04_Handoffs/from_22_Lab_20261015/06_Logs_luw')
repo=src/'han2026_supp/LatticeUrbanWind_repo'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()=='dd438c1c68664980a92460e4778f18f36be3f47c'
stage=base/'stage'
assert not stage.exists(), 'Never overwrite a stage'
stage.mkdir()
(stage/'caseA/proj_temp').mkdir(parents=True)
(stage/'caseA/wind_bc').mkdir()
for a,b in [(src/'CaseA_PF_caseA.stl',stage/'caseA/proj_temp/CaseA_PF.stl'),(src/'profile_caseA.dat',stage/'caseA/wind_bc/profile.dat'),(src/'caseA_observations_official.json',stage/'caseA_observations_official.json'),(src/'metrics_caseA_turb.json',stage/'metrics_caseA_turb.json')]:shutil.copy2(a,b)
c=repo/'examples/example_ProfileResearch_noDEM/conf.luwpf';txt=c.read_text()
changes=[('casename = CaseE','casename = CaseA'),('si_x_cfd = [0.000000, 2022.500153]','si_x_cfd = [0.000000, 1088.000000]'),('si_y_cfd = [0.000000, 1996.500092]','si_y_cfd = [0.000000, 704.000000]'),('si_z_cfd = [0.000000, 270.000000]','si_z_cfd = [0.000000, 384.000000]'),('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]'),('mesh_control = "gpu_memory"','mesh_control = "cell_size"'),('cell_size =\n','cell_size = 2.0\n'),('angle = [0, 90, 180, 270]','angle = [270]')]
for old,new in changes:assert txt.count(old)==1,(old,txt.count(old));txt=txt.replace(old,new)
txt+='\nrun_nstep = 32000\npurge_avg = 22000\npurge_avg_stride = 40\noutput_tke_ti_tls = [tke]\n'
txt+='\nvk_inlet_ti = 0.1468030617\nvk_inlet_l = 100.0\nvk_inlet_inflow_only = true\nvk_inlet_face_mode = TARGET_INFLOW\n'
(stage/'caseA/conf.luwpf').write_text(txt)
for name in ['extract_r9.py','compare_r9.py']:
 t=(base.parent/'caseA_r9_2m_rerun'/name).read_text();t=t.replace("r=Path('/content/luw-aij-caseA-turb-20261014')","r=Path(__file__).resolve().parent").replace("Path('/content/caseA_observations_official.json')","r/'caseA_observations_official.json'")
 (stage/name).write_text(t)
print('stage ready; source HEAD',subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
for p in sorted(stage.rglob('*')):
 if p.is_file():print(p.relative_to(stage),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
