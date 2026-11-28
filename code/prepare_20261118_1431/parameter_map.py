#!/usr/bin/env python3
import pathlib,re,json
R=pathlib.Path(__file__).resolve().parent
base=R.parents[1]/'R21.4a_T4_groundWM/phaseB_v2/stage/FluidX3D_on/src'
new=R/'FluidX3D_on/src'
def extract(path):
 s=path.read_text()
 a=s.index(')+R(kernel void stream_collide)');b=s.index(')+") {"+R(',a)
 return s[a:b]
old=extract(base/'kernel.cpp');newk=extract(new/'kernel.cpp')
assert newk.replace(')\n#ifdef SECOND_LAYER_WM\n+R(\n    , const global float* second_layer_stress_xy\n)\n#endif\n+"#ifdef WALL_GATE0"',')+"#ifdef WALL_GATE0"')==old, 'signature differs outside one extra parameter'
s=(new/'lbm.cpp').read_text(); a=s.index('kernel_stream_collide = Kernel(');b=s.index('#ifdef FORCE_FIELD',a)
text=s[a:b]
for token in ['ground_tau_sum, ground_tau_count','kernel_stream_collide.add_parameters(second_layer_new)','set_parameters(13u,(t&1ull) ? second_layer_old : second_layer_new)']:
 assert token in s
m={'base_order':['fi','rho','u','flags','t','fx','fy','fz','omega_x','omega_y','omega_z','ground_tau_sum','ground_tau_count'],
 't15_extra':['second_layer_stress_xy (argument 13; ping-pong buffer)'],
 'stream_collide_set_parameters_4':['t','fx','fy','fz','omega_x','omega_y','omega_z'],
 'auxiliary_kernels':['second_layer_partial(u,flags,partial,blocks)','second_layer_mean(partial,mean,blocks)','second_layer_stress(rho,u,flags,mean,old_stress,new_stress)'],
 'source_paths':[str(new/'kernel.cpp'),str(new/'lbm.cpp')]}
(R/'PARAMETER_MAP.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
print('STREAM_COLLIDE_PARAMETER_ORDER_PASS',m['base_order'],m['t15_extra'])
