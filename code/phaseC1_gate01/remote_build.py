import subprocess, os
p='/content/ibb_stage.tar.gz'
subprocess.run(['tar','-xzf',p,'-C','/content'],check=True)
root='/content/FluidX3D'
r=subprocess.run(['make','Linux','-j4'],cwd=root,stdout=open('/content/ibb_build.log','w'),stderr=subprocess.STDOUT)
print('BUILD_EXIT',r.returncode,flush=True)
print(''.join(open('/content/ibb_build.log').readlines()[-45:]),flush=True)
