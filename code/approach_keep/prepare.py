"""Prepare isolated LUW input decks only; never run a solver on 工作站."""
from pathlib import Path
import shutil,tarfile,hashlib,json
R=Path(__file__).resolve().parent
SRC=R.parents[1]/'wp1b_ibm/resolution_split/stage_E1'
assert SRC.exists(), SRC
for tag in ('E1G0','E1W','E1G0W'):
 out=R/('stage_'+tag)
 assert not out.exists(),out
 shutil.copytree(SRC,out,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 src=out/'FluidX3D/src'
 defs=src/'defines.hpp'
 s=defs.read_text()
 if 'G0' in tag:
  assert s.count('//#define GROUND_WALL_MODEL')==1
  s=s.replace('//#define GROUND_WALL_MODEL','#define GROUND_WALL_MODEL')
 if 'W' in tag:
  s=s.replace('#define SUBGRID // enables','#define WALE_SGS // mutually exclusive with SUBGRID collision branch\n#define SUBGRID // enables')
 defs.write_text(s)
 if 'W' in tag:
  p=src/'lbm.hpp';s=p.read_text();key='\tKernel kernel_update_fields;'
  assert s.count(key)==1
  s=s.replace(key,'#ifdef WALE_SGS\n\tMemory<float> wale_omega;\n\tKernel kernel_wale_omega;\n#endif\n'+key);p.write_text(s)
  p=src/'lbm.cpp';s=p.read_text();key='\tkernel_update_fields = Kernel(device, N, "update_fields", fi, rho, u, flags, t, fx, fy, fz, omega_x, omega_y, omega_z);'
  assert s.count(key)==1
  s=s.replace(key,key+'\n#ifdef WALE_SGS\n\twale_omega=Memory<float>(device,N);\n\tkernel_wale_omega=Kernel(device,N,"wale_prepare",u,flags,wale_omega);\n\tkernel_stream_collide.add_parameters(wale_omega);\n#endif')
  key='\tfor(uint d=0u; d<get_D(); d++) lbm_domain[d]->enqueue_stream_collide();'
  assert s.count(key)==1
  s=s.replace(key,'#ifdef WALE_SGS\n\tif(get_D()!=1u) print_error("WALE_SGS initial single-domain implementation");\n\tfor(uint d=0u;d<get_D();d++) lbm_domain[d]->enqueue_wale_omega(); // old-step u, before collision\n#endif\n'+key)
  s=s.replace('void LBM_Domain::enqueue_stream_collide() {','#ifdef WALE_SGS\nvoid LBM_Domain::enqueue_wale_omega() { kernel_wale_omega.enqueue_run(); }\n#endif\nvoid LBM_Domain::enqueue_stream_collide() {')
  p2=src/'lbm.hpp';h=p2.read_text();key2='\tvoid enqueue_stream_collide();';assert h.count(key2)==1
  h=h.replace(key2,'#ifdef WALE_SGS\n\tvoid enqueue_wale_omega();\n#endif\n'+key2);p2.write_text(h)
  # kernel_wale_omega exposed as public like other kernels
  p.write_text(s)
  p=src/'kernel.cpp';s=p.read_text();key=')+R(kernel void initialize)'
  wale='''
)+"#ifdef WALE_SGS"+R(
// Fixed old-step velocity-gradient pass; no cross-thread access to u during collision.
// Cw=.325, Δ=1 lattice; one-sided fluid differences next to TYPE_S, zero if both blocked.
kernel void wale_prepare(const global float* u, const global uchar* flags, global float* wale_omega) {
 const uxx n=get_global_id(0);
 if(n>=(uxx)def_N||is_halo(n)) return;
 if((flags[n]&TYPE_BO)==TYPE_S) { wale_omega[n]=def_w; return; }
 uxx j[def_velocity_set]; neighbors(n,j);
 const float3 uc=load3(n,u);
 float g[9];
 for(uint a=0u;a<3u;a++) {
  const uxx ip=j[1u+2u*a],im=j[2u+2u*a];
  const bool vp=(flags[ip]&TYPE_BO)!=TYPE_S,vm=(flags[im]&TYPE_BO)!=TYPE_S;
  const float3 grad=vp&&vm ? 0.5f*(load3(ip,u)-load3(im,u)) :
     (vp ? load3(ip,u)-uc : (vm ? uc-load3(im,u) : (float3)(0.0f,0.0f,0.0f)));
  g[a]=grad.x;g[3u+a]=grad.y;g[6u+a]=grad.z;
 }
 float gg[9];
 for(uint i=0u;i<3u;i++) for(uint j0=0u;j0<3u;j0++)
  gg[3u*i+j0]=g[3u*i+0u]*g[0u+j0]+g[3u*i+1u]*g[3u+j0]+g[3u*i+2u]*g[6u+j0];
 const float trace=(gg[0]+gg[4]+gg[8])/3.0f;
 float s2=0.0f,sd2=0.0f;
 for(uint i=0u;i<3u;i++) for(uint j0=0u;j0<3u;j0++) {
  const uint ij=3u*i+j0,ji=3u*j0+i;
  const float sij=0.5f*(g[ij]+g[ji]);
  const float sdij=0.5f*(gg[ij]+gg[ji])-(i==j0 ? trace : 0.0f);
  s2+=sij*sij;sd2+=sdij*sdij;
 }
 const float numerator=pow(sd2,1.5f);
 const float denominator=pow(s2,2.5f)+pow(sd2,1.25f)+1.0e-30f;
 const float nut=0.325f*0.325f*numerator/denominator;
 const float nu0=(1.0f/def_w-0.5f)/3.0f;
 wale_omega[n]=clamp(1.0f/(0.5f+3.0f*(nu0+nut)),0.01f,1.999f);
}
)+"#endif"+R( // WALE_SGS

'''
  assert s.count(key)==1
  s=s.replace(key,wale+key)
  key=')+"#ifdef FORCE_FIELD"+R(\n\t, const global float* F'
  assert s.count(key)>=1
  pos=s.index(')+R(kernel void stream_collide)')
  idx=s.index(key,pos)
  s=s[:idx]+')+"#ifdef WALE_SGS"+R(\n\t, const global float* wale_omega\n)+"#endif"+R( // WALE_SGS\n'+s[idx:]
  pos=s.index(')+R(kernel void stream_collide)')
  idx=s.index(')+"#ifdef SUBGRID"+R(',pos)
  s=s[:idx]+s[idx:].replace(')+"#ifdef SUBGRID"+R(',')+"#if defined(SUBGRID) && !defined(WALE_SGS)"+R(',1)
  end=s.index(')+"#endif"+R( // SUBGRID',idx)
  s=s[:end]+')+"#ifdef WALE_SGS"+R(\n\tw=wale_omega[n]; // νeff already reduced from frozen old-step u; Guo factor below follows w.\n)+"#endif"+R( // WALE_SGS\n'+s[end:]
  p.write_text(s)
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp','FluidX3D/src/lbm.cpp','FluidX3D/src/lbm.hpp']
 manifest={f:hashlib.sha256((out/f).read_bytes()).hexdigest() for f in files}
 (R/(tag+'_manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:
  t.add(out/'FluidX3D',arcname='FluidX3D');t.add(out/'case',arcname='case')
 print(tag,manifest)
