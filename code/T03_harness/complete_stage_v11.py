from pathlib import Path
import re,json
root=Path('/groups/kareem/[用户]/L22_6/L22_6_T03_v11_20261021_01')
p=root/'B1/constant/boundaryData/inlet'
assert not (p/'psi').exists()
text=(p/'points').read_text()
zz=[float(m.group(1)) for m in re.finditer(r'\(\s*-2\.100000e\+00\s+[0-9.eE+-]+\s+([0-9.eE+-]+)\s*\)',text)]
assert len(zz)==164,len(zz)
(p/'psi').write_text(f'{len(zz)}\n(\n'+''.join(f'{min(20.,max(0.,20*z/1.8)):.10f}\n' for z in zz)+')\n')
manifest={'source':'/groups/kareem/[用户]/petw_runs/cfd/weuq_e7_tinf_20261018T0750Z_v2/case','root':str(root),'mesh_cells':[4,44,36],'inlet_probes':50,'sampling_dt':.005,'end_time':40,'run_tags':['B0','B1'],'notes':'Assumptions: 40s including first 5s transient; 0.2m y probe spacing; five z levels. B1 original BC ignores psi.'}
(root/'stage.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(manifest)
