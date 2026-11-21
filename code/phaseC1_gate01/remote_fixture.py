import subprocess,os
root='/content/FluidX3D'
subprocess.run(['tar','-xzf','/content/ibb_fixture_stage.tar.gz','-C','/content'],check=True)
subprocess.run(['make','clean'],cwd=root,check=True,stdout=subprocess.DEVNULL)
r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=open('/content/ibb_fixture_build.log','w'),stderr=subprocess.STDOUT)
print('build',r.returncode,flush=True)
if r.returncode: print(''.join(open('/content/ibb_fixture_build.log').readlines()[-35:]));raise SystemExit(1)
for variant in ('baseline','ibb'):
 for kind in ('couette','poiseuille'):
  env=os.environ.copy();env['IBB_TEST_KIND']=kind;env['IBB_TEST_OUT']=f'/content/{variant}_{kind}.csv'
  if variant=='ibb':env['LUW_IBB_CSR']='/content/floor_half.csr'
  else:env.pop('LUW_IBB_CSR',None)
  with open(f'/content/{variant}_{kind}.log','w') as f:
   r=subprocess.run([root+'/bin/FluidX3D'],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=450)
  print(variant,kind,'exit',r.returncode,'tail',''.join(open(f'/content/{variant}_{kind}.log').readlines()[-8:]),flush=True)
  if r.returncode: break
