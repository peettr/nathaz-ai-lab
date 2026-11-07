"""Write isolated source diff against E1 base without running solver."""
from pathlib import Path
import difflib
R=Path(__file__).resolve().parent
base=R.parents[1]/'wp1b_ibm/resolution_split/stage_E1/FluidX3D/src'
changed=R/'stage_E1Wv5/FluidX3D/src'
out=[]
for name in ('defines.hpp','lbm.hpp','lbm.cpp','kernel.cpp'):
 a=(base/name).read_text().splitlines(keepends=True);b=(changed/name).read_text().splitlines(keepends=True)
 out.extend(difflib.unified_diff(a,b,fromfile='a/'+name,tofile='b/'+name))
(R/'wale_trial_vs_E1.diff').write_text(''.join(out))
print(len(out))
