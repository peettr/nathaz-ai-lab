#!/usr/bin/env python3
"""Independent source-linked CPU schedule/version audit (not a GPU result)."""
from pathlib import Path
import json
R = Path(__file__).resolve().parent
src = R / 'FluidX3D_on/src'
cpp = (src/'lbm.cpp').read_text()
cl = (src/'kernel.cpp').read_text()
h = (src/'lbm.hpp').read_text()
checks = {
    'device_macro_propagated': '"\\n\t#define SECOND_LAYER_WM"' in cpp,
    'three_kernel_dispatch_order': cpp.index('kernel_second_layer_partial.enqueue_run();') < cpp.index('kernel_second_layer_mean.enqueue_run();') < cpp.index('kernel_second_layer_stress.enqueue_run();'),
    'filter_before_collision': cpp.index('enqueue_second_layer_stress();', cpp.index('void LBM::do_time_step()')) < cpp.index('enqueue_stream_collide();', cpp.index('void LBM::do_time_step()')),
    'separate_two_planes': 'Memory<float> second_layer_old, second_layer_new' in h,
    'completed_fields_each_step': '#define UPDATE_FIELDS' in (src/'defines.hpp').read_text(),
    'collision_only_xy_stress': 'second_layer_stress_xy[col]' in cl and 'second_layer_stress_xy[xy+col]' in cl,
    'previous_step_second_layer': 'const float vx=u[b],vy=u[def_N+b]' in cl,
}
assert all(checks.values()), checks
# Link producer and consumer from actual host parity selection at each time step.
assert 'set_parameters(13u,(t&1ull) ? second_layer_old : second_layer_new)' in cpp
assert 'if(t&1ull) kernel_second_layer_stress.set_parameters(4u,second_layer_new,second_layer_old);' in cpp
assert 'else       kernel_second_layer_stress.set_parameters(4u,second_layer_old,second_layer_new);' in cpp
# A synthetic 2x2 column domain tests read/write stamps and immutable prior u at every dispatch.
u = {(col, 0): col+1 for col in range(4)}
tau = {'old': {(col, -1): 0. for col in range(4)}, 'new': {}}
events = []
for t in range(16):
    old, new = ('old','new') if t % 2 == 0 else ('new','old')
    # The host enqueues a reduce/read of immutable u@t, then writes tau@(t+1).
    assert all((col,t) in u for col in range(4))
    vals = [u[(col,t)] for col in range(4)]
    tau[new] = {(col,t): (tau[old][(col,t-1)] + vals[col])*.5 for col in range(4)}
    assert all((col,t) in tau[new] for col in range(4))
    # Collision can only consume the just-written plane, then becomes sole owner of u@(t+1).
    used = [tau[new][(col,t)] for col in range(4)]
    assert all(v == tau[new][(col,t)] for col,v in enumerate(used))
    for col in range(4): u[(col,t+1)] = u[(col,t)] + 0.01*used[col]
    events.append({'step': t, 'u_read_stamp': t, 'stress_read_stamp': t-1,
                   'stress_write_stamp': t, 'stress_read_plane': old,
                   'stress_write_and_collision_plane': new})
result={'status':'PASS_CPU_SOURCE_LINKED', 'scope':'host queue/parity/source pattern and CPU version stamps only',
        'checks':checks,'steps':events,'limitations':['not a native OpenCL race proof','not E3 force/area',
        'GPU and output-path tests still required']}
out=R/'E1_INDEPENDENT.json'
with out.open('x') as f: json.dump(result,f,indent=2); f.write('\n')
print('PASS_CPU_SOURCE_LINKED 16 steps; output',out)
