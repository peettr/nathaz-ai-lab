from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent; L=R.parents[1]
a=np.load(L/'wp1b_ibm/phaseC2_caseE_prep/step4_flags_z0_90.npz')['flags']
np.savez_compressed(R/'native_flags_z20_30.npz',flags=a[20:31]);print((R/'native_flags_z20_30.npz').stat().st_size)
