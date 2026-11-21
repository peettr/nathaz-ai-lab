#!/usr/bin/env python3
"""Isolated try13 source staging; never executes solver on host."""
from pathlib import Path
import shutil,hashlib,tarfile,json,difflib
R=Path(__file__).resolve().parent; S=R.parent/'try12'
assert not any((R/f'FluidX3D_{v}').exists() for v in ('noshear','native'))
for variant in ('noshear','native'):
    D=R/f'FluidX3D_{variant}'; shutil.copytree(S/f'FluidX3D_{variant}',D)
    sp=D/'src/setup.cpp'; old=sp.read_text(); new=old.replace('try12_', 'try13_')
    assert new!=old
    sp.write_text(new)
    if variant=='noshear':
        kp=D/'src/kernel.cpp'; oldk=kp.read_text()
        marker=')+"#ifdef GROUND_WALL_MODEL"+R(\n// A specular link is activated'
        insert=''' )+"#ifdef GROUND_WALL_MODEL"+R(
// Post-initialize repair on a separate dispatch: initialize has already stored all
// populations. One owner per wall-adjacent fluid cell, no concurrent init writes.
// The four specular diagonal reads already take neighboring fluid feq from
// initialize's store_f; only the native normal read still takes solid feq.
kernel void ground_initialize_incoming(global fpxx* fi, const global float* rho,
                                       const global float* u, const global uchar* flags) {
    const uxx n=get_global_id(0);
    if(n>=(uxx)def_N || is_halo(n) || (flags[n]&TYPE_BO)!=0u) return;
    const uint3 xyz=coordinates(n);
    const uint xy=def_Nx*def_Ny;
    if((int)xyz.z+def_Oz==def_ground_first_fluid_z &&
       (flags[n-xy]&TYPE_BO)==TYPE_S) {
        float feq[def_velocity_set];
        calculate_f_eq(rho[n],u[n],u[def_N+(ulong)n],u[2ul*def_N+(ulong)n],feq);
        // t=0 load_f f5 reads n/slot6, overwritten by solid initialize.
        store(fi,index_f(n,6u),feq[5]);
    }
)+"#ifdef WALL_GATE0"+R(
    // Fixture-only upper wall: t=0 f6 reads solid above in slot5.
    if(xyz.z+2u==def_Nz && (flags[n+xy]&TYPE_BO)==TYPE_S) {
        float feq[def_velocity_set];
        calculate_f_eq(rho[n],u[n],u[def_N+(ulong)n],u[2ul*def_N+(ulong)n],feq);
        store(fi,index_f(n+xy,5u),feq[6]);
    }
)+"#endif"+R(
}
)+"#endif"+R(

'''
        assert oldk.count(marker)==1
        newk=oldk.replace(marker,insert+marker);kp.write_text(newk)
        lp=D/'src/lbm.cpp'; oldl=lp.read_text()
        a='kernel_initialize = Kernel(device, N, "initialize", fi, rho, u, flags);'
        assert oldl.count(a)==1
        newl=oldl.replace(a,a+'\n#ifdef GROUND_WALL_MODEL\n\tkernel_ground_initialize_incoming = Kernel(device, N, "ground_initialize_incoming", fi, rho, u, flags);\n#endif')
        b='\tcommunicate_fi(); // time step must be odd here'
        assert newl.count(b)==1
        newl=newl.replace(b,b+'\n#ifdef GROUND_WALL_MODEL\n\tfor(uint d=0u; d<get_D(); d++) lbm_domain[d]->enqueue_ground_initialize_incoming();\n#endif')
        a='void LBM_Domain::enqueue_initialize() { // call kernel_initialize\n\tkernel_initialize.enqueue_run();'
        assert newl.count(a)==1
        newl=newl.replace(a,a+'\n}\n#ifdef GROUND_WALL_MODEL\nvoid LBM_Domain::enqueue_ground_initialize_incoming() { kernel_ground_initialize_incoming.enqueue_run(); }\n#endif\n/*TRY13_END*/')
        # Remove the original method-closing brace immediately after the insertion.
        newl=newl.replace('/*TRY13_END*/\n}', '/*TRY13_END*/',1)
        lp.write_text(newl)
        hp=D/'src/lbm.hpp'; oldh=hp.read_text()
        # Exact declaration anchors are validated before editing.
        for needle in ('Kernel kernel_initialize','void enqueue_initialize()'):
            assert needle in oldh,needle
        newh=oldh.replace('Kernel kernel_initialize','Kernel kernel_ground_initialize_incoming;\n\tKernel kernel_initialize',1)
        newh=newh.replace('void enqueue_initialize();','void enqueue_initialize();\n#ifdef GROUND_WALL_MODEL\n\tvoid enqueue_ground_initialize_incoming();\n#endif',1)
        hp.write_text(newh)
        diff=''.join(difflib.unified_diff(oldk.splitlines(True),newk.splitlines(True),fromfile='try12/kernel.cpp',tofile='try13/kernel.cpp'))
        for fn,old,new in [('lbm.cpp',oldl,newl),('lbm.hpp',oldh,newh)]:
            diff+=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=f'try12/{fn}',tofile=f'try13/{fn}'))
        (R/'initialization.patch').write_text(diff)
    source=D/'src'; names=('setup.cpp','kernel.cpp','lbm.cpp','lbm.hpp','defines.hpp')
    hashes={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in names}
    archive=R/f'try13_{variant}.tar.gz'
    with tarfile.open(archive,'w:gz') as tf:tf.add(D,arcname='FluidX3D_gate0')
    (R/f'{variant}_manifest.json').write_text(json.dumps({'sources':hashes,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},indent=2)+'\n')
    print(variant,hashes)
