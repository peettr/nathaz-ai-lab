#!/usr/bin/env python3
"""Make frozen C1 SA package from read-only B2 templates."""
from pathlib import Path
import re,shutil,hashlib
base=Path(__file__).resolve().parent
b=base.parent/'B_distinguish'/'B2_only'
for f in ('rank_launcher_v5.py','launch_solve.sh','watchdog.py','harvest.py','snappyHexMeshDict_B2','update_cells.py'):
    shutil.copy2(b/f,base/f)
s=(b/'fvSolution').read_text().replace('(U|k|omega)','(U|nuTilda)')
(base/'fvSolution_C1').write_text(s)
(base/'fvSolution_C1_adjust').write_text(s.replace('p 0.2;','p 0.1;').replace(')" 0.5;',')" 0.3;'))
d=(b/'b2_driver.py').read_text()
d=d.replace("import openmdao.api as om\n", "import openmdao.api as om\n")
d=d.replace(" 'inputInfo':{'beta':{'type':'field','fieldName':'betaFIOmega','fieldType':'scalar','distributed':False,'components':['solver','function']}},", "")
d=d.replace("'nut':0.1,'phi':1.,'k':0.5,'omega':5.","'nut':0.1,'phi':1.,'nuTilda':0.1")
d=d.replace("    self.add_subsystem('dvs',om.IndepVarComp(),promotes=['*'])\n", "")
d=d.replace(" def configure(self):\n    self.dvs.add_output('beta',val=np.ones(n),distributed=False)\n    self.connect('beta','scenario1.beta');self.add_design_var('beta',lower=.2,upper=5.)\n    self.add_objective('scenario1.aero_post.roofCp')", "")
d=d.replace("case=Path.cwd(); sample=json.loads((case/'sample_cells.json').read_text())\nids=sample['cell_ids']; n=sample['mesh_cells']\nassert len(ids)==5 and len(set(ids))==5 and all(0<=i<n for i in ids)","case=Path.cwd(); sample=json.loads((case/'sample_cells.json').read_text()); n=sample['mesh_cells']")
d=d.replace("name='scenario1.aero_post.roofCp'; beta=np.ones(n)","name='scenario1.aero_post.roofCp'")
d=d.replace(" prob.set_val('beta',beta)\n", "")
d=d.replace("fields=['Ux','Uy','Uz','p','k','omega']", "fields=['Ux','Uy','Uz','p','nuTilda']")
d=d.replace("  assert len(res['p'])==3*len(res['Ux']), 'p corrector count mismatch'", "  assert len(res['p'])==3*len(res['Ux']), 'p corrector count mismatch'")
d=d.replace("'steps_by_field':{f:len(res.get(f,[])) for f in fields}","'steps_by_field':{f:len(res.get(f,[])) for f in fields}")
assert "'nuTilda']" in d and 'beta' not in d and "res['p']=res['p'][0::3]" in d
(base/'c1_driver.py').write_text(d)
# Recompute nuTilda inlet face-by-face against the final ASCII mesh, following G1 build_inlet.py.
i=(base.parent/'build_inlet.py').read_text()
i=i.replace("vals={x:[] for x in ('U','k','omega')};zs=[]","vals={x:[] for x in ('U','nuTilda')};zs=[]")
i=i.replace("    vals['U'].append(f'({ustar/kappa*math.log((z+z0)/z0):.12g} 0 0)')\n    vals['k'].append(f'{ustar**2/math.sqrt(cmu):.12g}')\n    vals['omega'].append(f'{ustar/(kappa*math.sqrt(cmu)*(z+z0)):.12g}')", "    vals['U'].append(f'({ustar/kappa*math.log((z+z0)/z0):.12g} 0 0)')\n    vals['nuTilda'].append(f'{kappa*ustar*(z+z0):.12g}')")
i=i.replace("print('INLET',n,'HEIGHT',min(zs),max(zs),'USTAR',ustar)","print('SA_INLET',n,'HEIGHT',min(zs),max(zs),'USTAR',ustar,'MIN',min(map(float,vals['nuTilda'])),'MAX',max(map(float,vals['nuTilda'])))")
(base/'build_sa_inlet.py').write_text(i)
print('generated',[(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in base.iterdir() if p.is_file()])
