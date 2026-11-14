import subprocess,os
root='/content/off_test/FluidX3D'
for variant in ('type_s','ibb'):
 for kind in ('couette','poiseuille'):
  env=os.environ.copy();env['IBB_TEST_KIND']=kind;env['IBB_TEST_OUT']=f'/content/new_{variant}_{kind}.csv'
  if variant=='ibb': env['LUW_IBB_CSR']='/content/floor_half.csr'
  else:env.pop('LUW_IBB_CSR',None)
  with open(f'/content/new_{variant}_{kind}.log','w') as f:
   r=subprocess.run([root+'/bin/FluidX3D'],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
  print(variant,kind,r.returncode,'rows',sum(1 for _ in open(env['IBB_TEST_OUT'])) if os.path.exists(env['IBB_TEST_OUT']) else 0,flush=True)
  if r.returncode:print(''.join(open(f'/content/new_{variant}_{kind}.log').readlines()[-15:]),flush=True)
