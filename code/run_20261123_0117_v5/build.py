from pathlib import Path
import shutil
R=Path(__file__).resolve().parent
V4=R.parent/'run_20261123_0112_v4'
shutil.copytree(V4/'unified',R/'unified')
p=R/'unified/src/kernel.cpp';s=p.read_text()
# Host preprocessor selects Cw before the R(...) string is formed.
s=s.replace(')+"#ifdef T18_CW325"+R(\n const float nut=0.325f*0.325f*numerator/denominator;\n)+"#else"+R(\n const float nut=0.200f*0.200f*numerator/denominator;\n)+"#endif"+R(',''')
#ifdef T18_CW325
+R(
 const float nut=0.325f*0.325f*numerator/denominator;
)
#else
+R(
 const float nut=0.200f*0.200f*numerator/denominator;
)
#endif
+R(''')
# OpenCL has no T18_CS macros; select host-side outside the raw string.
s=s.replace(')+"#if defined(T18_CS013)"+R(\n\t\tw = 2.0f/(tau0+sqrt(sq(tau0)+0.430203766f*sgs_length_factor*sqrt(Q)/rhon));\n)+"#elif defined(T18_CS010)"+R(\n\t\tw = 2.0f/(tau0+sqrt(sq(tau0)+0.254558f*sgs_length_factor*sqrt(Q)/rhon));\n)+"#else"+R(\n\t\tw = 2.0f/(tau0+sqrt(sq(tau0)+0.76421222f*sgs_length_factor*sqrt(Q)/rhon));\n)+"#endif"+R(',''')
#ifdef T18_CS013
+R(
		w = 2.0f/(tau0+sqrt(sq(tau0)+0.430203766f*sgs_length_factor*sqrt(Q)/rhon));
)
#elif defined(T18_CS010)
+R(
		w = 2.0f/(tau0+sqrt(sq(tau0)+0.254558441f*sgs_length_factor*sqrt(Q)/rhon));
)
#else
+R(
		w = 2.0f/(tau0+sqrt(sq(tau0)+0.76421222f*sgs_length_factor*sqrt(Q)/rhon));
)
#endif
+R(''')
assert '#ifdef T18_CW325\n+R' in s and '#ifdef T18_CS013\n+R' in s
p.write_text(s)
for variant in ('B0','K1a','K1b','K2','K3a','K3b'):
 dst=R/'variants'/variant
 shutil.copytree(R/'unified',dst)
 shutil.copyfile(V4/'variants'/variant/'src/defines.hpp',dst/'src/defines.hpp')
print('generated host-selected constants')
