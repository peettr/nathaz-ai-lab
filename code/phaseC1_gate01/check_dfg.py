import os
for p in ('/content/dfg_full_progress.log','/content/D20_ibb_full_solver.log','/content/D20_ibb_full.csv'):
 if os.path.exists(p):
  print(p,'bytes',os.path.getsize(p),'tail',open(p).read()[-350:])
