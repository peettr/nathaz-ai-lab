import os,subprocess,pathlib
for mode,archive in (('head','head_fixture.tar.gz'),('off','ibb_fixture_stage.tar.gz')):
    basedir=f'/content/{mode}_test';os.makedirs(basedir,exist_ok=True)
    subprocess.run(['tar','-xzf','/content/'+archive,'-C',basedir],check=True)
    root=basedir+'/FluidX3D'
    with open(f'/content/{mode}_build.log','w') as f:
        r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=f,stderr=subprocess.STDOUT)
    print(mode,'BUILD',r.returncode,flush=True)
    if r.returncode:
        print(''.join(open(f'/content/{mode}_build.log').readlines()[-30:]),flush=True);continue
    for kind in ('couette','poiseuille'):
        env=os.environ.copy();env.update(IBB_TEST_KIND=kind,IBB_TEST_STEPS='500',IBB_TEST_OUT=f'/content/{mode}_{kind}_500.csv');env.pop('LUW_IBB_CSR',None)
        with open(f'/content/{mode}_{kind}_500.log','w') as f:
            r=subprocess.run([root+'/bin/FluidX3D'],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120)
        print(mode,kind,'EXIT',r.returncode,'HASH',next((line.strip() for line in open(f'/content/{mode}_{kind}_500.csv') if line.startswith('HASH500')),'none'),flush=True)
