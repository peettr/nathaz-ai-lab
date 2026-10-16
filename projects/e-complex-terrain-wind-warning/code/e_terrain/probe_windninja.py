import subprocess,os,glob
p='/content/e_terrain/wn_env/bin/WindNinja_cli'
print('exists',os.path.exists(p),flush=True)
r=subprocess.run([p,'--help'],capture_output=True,text=True,timeout=30,env={**os.environ,'WINDNINJA_DATA':'/content/e_terrain/wn_env/share/windninja'})
print('return',r.returncode,'stdout',r.stdout[:2400],'stderr',r.stderr[:1500],flush=True)
print('data',glob.glob('/content/e_terrain/wn_env/share/**/*',recursive=True)[:30])
