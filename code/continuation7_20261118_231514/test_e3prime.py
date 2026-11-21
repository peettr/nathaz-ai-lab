import csv,json,math,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parent;O=R/'fixture_e3prime';O.mkdir(exist_ok=False)
keys=['step','x','y','tau_f_x_lattice','tau_f_y_lattice','tau_f_abs_lattice','applied_force_x_lattice','applied_force_y_lattice','area_lattice','match_ux_previous','match_uy_previous','match_rho_previous','epsilon_device','match_speed_lattice','tau_w_theory_lattice','relative_error']
eps=.5;u=.035;theory=(.4*u/math.log((1.5+.024)/.024))**2;trace=[];evol=[]
for step in range(101):
 if step:evol.append({'step':step,'mean_match_speed':5.,'epsilon_device':eps,'Tf_steps':2.})
 for y in (2,5,8,11,14,17,19,21):
  for x in (2,5,8,11,14,17,19,21):
   tau=theory*(1-(1-eps)**step)
   trace.append(dict(zip(keys,[step,x,y,tau,0,tau,-tau,0,1,u,0,1,eps if step else 0,u,theory,0])))
def put(path,rows,fields):
 with path.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
put(O/'good.csv',trace,keys);put(O/'evolution.csv',evol,['step','mean_match_speed','epsilon_device','Tf_steps'])
top_keys=['step','top_ux','adjacent_ux','top_uy','adjacent_uy','delta_ux','top_shear_proxy']
put(O/'top.csv',[dict(zip(top_keys,[step,u,u,0,0,0,0])) for step in range(101)],top_keys)
wrong=[dict(r) for r in trace];wrong[-1]['tau_f_x_lattice']=float(wrong[-1]['tau_f_x_lattice'])*1.1;wrong[-1]['tau_f_abs_lattice']=wrong[-1]['tau_f_x_lattice'];wrong[-1]['applied_force_x_lattice']=-wrong[-1]['tau_f_x_lattice']
put(O/'bad.csv',wrong,keys)
for kind,expected in [('good',0),('bad',2)]:
 p=subprocess.run([sys.executable,str(R/'assert_e3prime.py'),str(O/(kind+'.csv')),str(O/'evolution.csv'),'--top',str(O/'top.csv'),'--comparison',str(O/(kind+'_compare.csv'))],capture_output=True,text=True)
 print(kind,'exit',p.returncode,p.stdout.strip(),p.stderr.strip(),flush=True)
 assert p.returncode==expected,(kind,p.returncode,p.stderr)
