from pathlib import Path
R=Path(__file__).resolve().parent/'work/pack_stage'
for variant in ('periodic_bounce','periodic_t4','periodic_t15_k2','periodic_t15_k3'):
    src=R/variant/'src'
    kp=src/'kernel.cpp'; s=kp.read_text()
    old='''#ifdef PERIODIC_ABL_TOP_MIRROR
+R(
\tconst uint3 periodic_xyz=coordinates(n);
\tif(periodic_xyz.z==def_Nz-2u && (flags[j[5]]&TYPE_BO)==TYPE_S) {
\t\tconst float sx=fhn[10]; fhn[10]=fhn[15]; fhn[15]=sx;
\t\tconst float sy=fhn[12]; fhn[12]=fhn[17]; fhn[17]=sy;
\t}
)
#endif'''
    new='''#ifdef PERIODIC_ABL_TOP_MIRROR
+R(
\tconst uint3 periodic_xyz=coordinates(n);
\tif(periodic_xyz.z==def_Nz-2u && (flags[j[5]]&TYPE_BO)==TYPE_S) {
\t\t// Link-wise top mirror: packet comes from the previous step's
\t\t// tangentially shifted fluid endpoint, not from the zero-velocity
\t\t// solid equilibrium. Esoteric-Pull alternates slot parity.
\t\tfhn[10]=load(fi,index_f(j[1],t%2ul ? 16u : 15u));
\t\tfhn[15]=load(fi,index_f(j[5],t%2ul ?  9u : 10u));
\t\tfhn[12]=load(fi,index_f(j[3],t%2ul ? 18u : 17u));
\t\tfhn[17]=load(fi,index_f(j[5],t%2ul ? 11u : 12u));
\t}
)
#endif'''
    assert s.count(old)==1,(variant,'top original count',s.count(old));s=s.replace(old,new)
    marker=''')+"#endif"+R(

)+"#ifdef GROUND_WALL_MODEL"+R(
// A specular link'''
    inject=''')+"#endif"+R(

)+"#ifdef PERIODIC_ABL_TOP_MIRROR"+R(
// Called after initialize/communicate_fi. The solid top's equilibrium
// overwrites the normal incoming slot, exactly as at the bottom wall.
// The tangential diagonal incoming packets use shifted fluid/solid
// stores from initialize(t=1), so repair only the normal direction.
kernel void top_initialize_incoming(global fpxx* fi, const global float* rho,
                                    const global float* u, const global uchar* flags) {
    const uxx n=get_global_id(0);
    if(n>=(uxx)def_N || is_halo(n) || (flags[n]&TYPE_BO)!=0u) return;
    const uint3 xyz=coordinates(n);
    if(xyz.z!=def_Nz-2u) return;
    uxx j[def_velocity_set]; neighbors(n,j);
    if((flags[j[5]]&TYPE_BO)!=TYPE_S) return;
    float feq[def_velocity_set];
    calculate_f_eq(rho[n],u[n],u[def_N+(ulong)n],u[2ul*def_N+(ulong)n],feq);
    store(fi,index_f(j[5],5u),feq[5]);
}
)+"#endif"+R(

)+"#ifdef GROUND_WALL_MODEL"+R(
// A specular link'''
    assert s.count(marker)==1,(variant,'marker');s=s.replace(marker,inject)
    kp.write_text(s)
    hp=src/'lbm.hpp'; h=hp.read_text();marker='\tKernel kernel_ground_initialize_incoming;';assert h.count(marker)==1;h=h.replace(marker,marker+'\n#ifdef PERIODIC_ABL_TOP_MIRROR\n\tKernel kernel_top_initialize_incoming;\n#endif') if 'GROUND_WALL_MODEL' in h else h
    # Top mirror also exists in bounce build, outside the ground-model guard.
    if variant=='periodic_bounce':
        h=(src/'lbm.hpp').read_text(); pos='\tKernel kernel_initialize;'; assert pos in h
        h=h.replace(pos,pos+'\n#ifdef PERIODIC_ABL_TOP_MIRROR\n\tKernel kernel_top_initialize_incoming;\n#endif')
    else:
        # Reposition independent of GROUND_WALL_MODEL.
        h=h.replace(marker+'\n#ifdef PERIODIC_ABL_TOP_MIRROR\n\tKernel kernel_top_initialize_incoming;\n#endif',marker)
        pos='\tKernel kernel_initialize;';assert pos in h;h=h.replace(pos,pos+'\n#ifdef PERIODIC_ABL_TOP_MIRROR\n\tKernel kernel_top_initialize_incoming;\n#endif')
    pos='\tvoid enqueue_initialize();';assert pos in h;h=h.replace(pos,pos+'\n#ifdef PERIODIC_ABL_TOP_MIRROR\n\tvoid enqueue_top_initialize_incoming();\n#endif');hp.write_text(h)
    lp=src/'lbm.cpp';b=lp.read_text();mark='\tkernel_initialize = Kernel(device, N, "initialize", fi, rho, u, flags);';assert b.count(mark)==1;b=b.replace(mark,mark+'\n#ifdef PERIODIC_ABL_TOP_MIRROR\n\tkernel_top_initialize_incoming = Kernel(device, N, "top_initialize_incoming", fi, rho, u, flags);\n#endif')
    mark='void LBM_Domain::enqueue_initialize() { // call kernel_initialize';assert b.count(mark)==1;b=b.replace(mark,'#ifdef PERIODIC_ABL_TOP_MIRROR\nvoid LBM_Domain::enqueue_top_initialize_incoming() { kernel_top_initialize_incoming.enqueue_run(); }\n#endif\n'+mark)
    mark='\tcommunicate_fi(); // time step must be odd here';assert b.count(mark)==1;b=b.replace(mark,mark+'\n#ifdef PERIODIC_ABL_TOP_MIRROR\n\tfor(uint d=0u;d<get_D();d++) lbm_domain[d]->enqueue_top_initialize_incoming();\n#endif')
    lp.write_text(b)
print('patched four periodic variants')
