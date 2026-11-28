from pathlib import Path
import shutil,hashlib,subprocess
R=Path(__file__).resolve().parent
V3=R.parent/'run_20261123_0100_v3'
BASE=V3/'BASE.cl'
assert BASE.is_file()
assert not (R/'unified').exists()
shutil.copytree(V3/'unified',R/'unified')
# Restore the exact legacy container when all T18 switches are off. Other
# branches retain the selected variant's K3a WALE source and host C++ guards.
p=R/'unified/src/kernel.cpp'
s=p.read_text()
assert s.count('string opencl_c_container() {')==1
s=s.replace('string opencl_c_container() {', '''string opencl_c_container() {
#if !defined(T18_CS013) && !defined(T18_CS010) && !defined(GROUND_WALL_SGS_DAMP) && !defined(T18_TRT_WALE)
 return R"T18BASE('''+BASE.read_text()+''')T18BASE";
#else''',1)
# This generator returns at the end of the function: close the variant branch.
close=s.rfind('\n} // ################################')
assert close>0
s=s[:close]+'\n#endif'+s[close:]
p.write_text(s)
for variant in ('B0','K1a','K1b','K2','K3a','K3b'):
 dst=R/'variants'/variant
 shutil.copytree(R/'unified',dst)
 src=V3/'variants'/variant/'src/defines.hpp'
 shutil.copyfile(src,dst/'src/defines.hpp')
print('copied all variants')
