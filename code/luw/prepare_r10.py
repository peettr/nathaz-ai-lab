"""Prepare isolated r10 Colab scripts from verified r7 workflow; solver source untouched."""
from pathlib import Path
import shutil
b=Path(__file__).parent
out=b/'run_r10_20261014'
out.mkdir(exist_ok=False)
base=(b/'bootstrap_r7.py').read_text().replace("Path('/content/luw-aij-r7')","Path('/content/luw-aij-r10')")
base=base.replace("# Measured prior run: 1 SI second", "# Measured prior run: 1 SI second")
base += '''\n# Four cases share cloned repo/build and geometry; only listed conf settings differ.\nsource=case\nfor variant in ('a','b','c','d'):\n target=r/('case_'+variant);shutil.copytree(source,target)\n p=target/'conf.luwpf';text=p.read_text();assert 'vk_inlet_ti' not in text\n text+='\\nvk_inlet_ti = 0.1621087892\\nvk_inlet_l = 100.0\\nvk_inlet_inflow_only = true\\nvk_inlet_face_mode = TARGET_INFLOW\\n'\n if variant=='b':text=text.replace('flux_correction = false','flux_correction = true')\n if variant=='c':text=text.replace('si_z_cfd = [0.000000, 270.000000]','si_z_cfd = [0.000000, 300.000000]').replace('z_limit = 250','z_limit = 280')\n if variant=='d':text=text.replace('run_nstep = 31000','run_nstep = 51000').replace('purge_avg = 20000','purge_avg = 40000')\n p.write_text(text);print('VARIANT',variant,p.read_text(),flush=True)\n'''
(out/'bootstrap_r10.py').write_text(base)
launch=(b/'launch_r7.py').read_text().replace("Path('/content/luw-aij-r7')","Path('/content/luw-aij-r10')").replace("case=r/'case_west'","case=r/'case_VARIANT'").replace("r/'solver.exit'","r/'solver_VARIANT.exit'").replace("r/'solver.lock'","r/'solver_VARIANT.lock'").replace("r/'solver.start'","r/'solver_VARIANT.start'").replace("r/'solver.log'","r/'solver_VARIANT.log'").replace("r/'solver.metrics'","r/'solver_VARIANT.metrics'").replace("r/'solver_wrapper.py'","r/'solver_wrapper_VARIANT.py'").replace("r/'solver_wrapper.log'","r/'solver_wrapper_VARIANT.log'")
for v in 'abcd':(out/f'launch_{v}_r10.py').write_text(launch.replace('VARIANT',v))
extract=(b/'extract_r7.py').read_text().replace("Path('/content/luw-aij-r7')","Path('/content/luw-aij-r10')").replace("case_west/","case_VARIANT/").replace("r/'case_west/", "r/'case_VARIANT/").replace("r.joinpath('solver.exit')","r.joinpath('solver_VARIANT.exit')").replace("r.joinpath('offset_samples_r7.json')","r.joinpath('offset_samples_VARIANT_r10.json')").replace("r.joinpath('points_w_r7.json')","r.joinpath('points_w_r7.json')")
# All crop cases preserve the same physical measured points; c changes upper roof only.
for v in 'abcd':(out/f'extract_{v}_r10.py').write_text(extract.replace('VARIANT',v))
shutil.copy2(b/'points_w_r7.json',out/'points_w_r7.json')
print('prepared',out,sorted(p.name for p in out.iterdir()))
