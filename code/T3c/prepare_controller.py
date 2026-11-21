#!/usr/bin/env python3
"""Clone T3b_r2 orchestration to an independent T3c session and paths."""
from pathlib import Path
import re,hashlib
R=Path(__file__).resolve().parent;P=R.parent/'T3b_r2'
for old,new in [('controller_t3b.py','controller_t3c.py'),('remote_worker_t3b.py','remote_worker_t3c.py'),('launch_t3b.py','launch_t3c.py'),('check_t3b.py','check_t3c.py'),('ack_t3b.py','ack_t3c.py'),('analyze_t3b.py','analyze_t3c.py')]:
 out=R/new;assert not out.exists(),out
 text=(P/old).read_text()
 for a,b in [('t3_t3b','t3_t3c'),('t3b_r2','t3c'),('t3b','t3c'),('T3B','T3C'),('T3b','T3c'),('103','105'),('104','106'),('1115','1116')]:text=text.replace(a,b)
 if old=='controller_t3b.py':
  text=text.replace('rate=6.81','rate=6.81').replace('(56/rate)*3600','(42/rate)*3600')
  text=text.replace('parser=R.parent/\'run2/remote_worker_run2.py\'','parser=R.parent/\'run2/remote_worker_run2.py\'')
  text=text.replace("for ext in ('_solver.log','_exit.json','_thin_meta.json'):","for ext in ('_solver.log','_exit.json','_thin_meta.json','_geometry_gate.csv'):")
  # Starting a GPU job entails keepalive; status errors never imply remote failure.
 if old=='remote_worker_t3b.py':
  anchor="  (OUT/f'{case}_exit.json').write_text(json.dumps({'case':case,'solver_exit':p.returncode,'elapsed_s':time.time()-t})+'\\n')"
  assert text.count(anchor)==1
  insertion="""  # Native pre-solver gate exists even on solver failure. Preserve it before any verdict.
  gate=base/'RESULTS/t3c_geometry_gate.csv'
  if gate.is_file():
   import shutil,csv
   shutil.copyfile(gate,OUT/f'{case}_geometry_gate.csv')
   with gate.open() as gf:rows=list(csv.DictReader(gf))
   assert len(rows)==5 and all(row['pass']=='1' and abs(float(row['first_fluid_z_m'])-dx)<1e-4 for row in rows),'native geometry gate failed'
  else:raise RuntimeError('native geometry gate output absent '+case)
"""
  text=text.replace(anchor,anchor+'\n'+insertion.rstrip())
 if old=='analyze_t3b.py':
  text=text.replace("result['first_fluid_k_at_xc']=first_fluid_k", "result['first_fluid_k_at_xc']=first_fluid_k\n result['x0_G_at_physical_z2_mps']=sample(0.,2.-wall)['G_mps']")
  text=text.replace("'side_G_over_center_at_xc':", "'x0_G_physical_z2_mps':{k:v['x0_G_at_physical_z2_mps'] for k,v in cases.items()},'side_G_over_center_at_xc':")
  # Important: analysis verifies each archived column is at the expected wall height.
  text=text.replace("wall=oz+(first_fluid_k-.5)*dx", "wall=oz+(first_fluid_k-.5)*dx\n assert abs((oz+first_fluid_k*dx)-dx)<1e-4,'incorrect geometry at xc'")
  text=text.replace('first_fluid_k=next(', 'first_fluid_k=next(')
  text=text.replace("R/'stage_fixed/stage_manifest.json'", "R/'stage_fixed/stage_manifest.json'")
 out.write_text(text)
print('generated',[(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in R.glob('*t3c.py')])
