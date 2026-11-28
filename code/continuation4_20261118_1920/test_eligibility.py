#!/usr/bin/env python3
"""Red/green regression for the actual generated-kernel flag predicate."""
from pathlib import Path
s=(Path(__file__).parent/'stage/FluidX3D_e3/src/kernel.cpp').read_text()
segment=s.split('kernel void second_layer_partial(',1)[1].split('kernel void second_layer_mean(',1)[0]
stress=s.split('kernel void second_layer_stress(',1)[1].split(')+"#endif',1)[0]
for name,part in [('partial',segment),('stress',stress)]:
    assert '(flags[a]&TYPE_BO)!=TYPE_F' not in part, f'{name}: TYPE_F=8 cannot pass TYPE_BO=3'
    assert '(flags[b]&TYPE_BO)!=TYPE_F' not in part, f'{name}: TYPE_F=8 cannot pass TYPE_BO=3'
    assert '(flags[a]&TYPE_BO)!=0u' in part and '(flags[b]&TYPE_BO)!=0u' in part
    for fluid in (0,8):
        assert (fluid & 3)==0
    for boundary in (1,2):
        assert (boundary & 3)!=0
print('PASS: both kernels accept ordinary/TYPE_F fluid, reject solid/equilibrium')
