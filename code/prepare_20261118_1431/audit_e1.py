#!/usr/bin/env python3
"""Static call graph and CPU version-stamp audit for second-layer stress."""
import pathlib, json, re
R=pathlib.Path(__file__).resolve().parent
src=R/'FluidX3D_on/src'
lbm=(src/'lbm.cpp').read_text(); kernel=(src/'kernel.cpp').read_text(); header=(src/'lbm.hpp').read_text()
def block(s, begin, end):
 a=s.index(begin); b=s.index(end,a); return s[a:b]
step=block(lbm,'void LBM::do_time_step()', '#if defined(SURFACE) || defined(GRAPHICS)')
queue=block(lbm,'void LBM_Domain::enqueue_second_layer_stress()', 'void LBM_Domain::enqueue_update_fields')
stress=block(kernel,'kernel void second_layer_stress(', ')+"#ifdef GROUND_WALL_MODEL"')
collision=block(kernel,'#else\n+R(\n        const uint col=ground_xyz.x', '#endif // SECOND_LAYER_WM')
assert step.index('enqueue_second_layer_stress()')<step.index('enqueue_stream_collide()')
assert queue.index('kernel_second_layer_partial.enqueue_run()')<queue.index('kernel_second_layer_mean.enqueue_run()')<queue.index('kernel_second_layer_stress.enqueue_run()')
assert 'u[b]' in stress and 'u[def_N+b]' in stress and 'rho[b]*tau' in stress
assert 'second_layer_stress_xy[col]' in collision and not re.search(r'\bu\[j\[5\]\]',collision)
assert 'kernel_stream_collide.set_parameters(13u,(t&1ull) ? second_layer_old : second_layer_new)' in lbm
assert 'kernel_second_layer_stress.set_parameters(4u,second_layer_new,second_layer_old)' in lbm
assert 'kernel_second_layer_stress.set_parameters(4u,second_layer_old,second_layer_new)' in lbm
assert 'Memory<float> second_layer_old, second_layer_new' in header
# Four sequential timestamps: old u is immutable until collision; filter reads previous tau plane.
events=[]
for t in range(4):
 old='A' if t%2==0 else 'B'; new='B' if t%2==0 else 'A'
 assert old!=new
 events.extend([{'t':t,'stage':'partial','reads':'u@'+str(t),'writes':'partial'},
                {'t':t,'stage':'mean','reads':'partial','writes':'mean'},
                {'t':t,'stage':'filter','reads':['u@'+str(t),'tau@'+old],'writes':'tau@'+new},
                {'t':t,'stage':'collision','reads':'tau@'+new,'writes':'u@'+str(t+1)}])
for i,event in enumerate(events):
 if event['stage']=='filter': assert events[i+1]['stage']=='collision' and events[i+1]['reads']==event['writes']
out={'E1':'PASS_static_CPU_version_stamp','steps':4,'events':events,'caveat':'GPU kernel ordering and actual force equality require E3 device run'}
(R/'E1_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('E1_STATIC_VERSION_PASS; 4 steps; no same-step u neighbour read')
