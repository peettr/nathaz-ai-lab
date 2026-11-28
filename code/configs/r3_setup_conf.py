from pathlib import Path
import shutil
r=Path('/content/luw-aij-r3');assert (r/'solver.exit').exists(), 'old solver not exited';print('OLD', (r/'solver.exit').read_text())
src=r/'repo/examples/example_ProfileResearch_noDEM';dst=r/'case_fine2';assert not dst.exists();(dst/'proj_temp').mkdir(parents=True);(dst/'wind_bc').mkdir()
for rel in ['conf.luwpf','CaseE(Niigata).xls','proj_temp/CaseE_PF.stl','wind_bc/profile.dat']:shutil.copy2(src/rel,dst/rel)
p=dst/'conf.luwpf';v=p.read_text().replace('n_gpu = [2, 1, 1]','n_gpu = [1, 1, 1]').replace('angle = [0, 90, 180, 270]','angle = [0]').replace('gpu_memory = 4000','gpu_memory = 24000');v+='\n// r3 second attempt; full advection ~509 s; 24k averaging steps at estimated 43 steps/s\nrun_nstep = 28000\npurge_avg = 24000\npurge_avg_stride = 20\noutput_tke_ti_tls = []\n';p.write_text(v);print(v)
