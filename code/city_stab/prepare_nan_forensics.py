"""Create isolated stage4 instrumentation from immutable stage3; no solver on 工作站."""
from pathlib import Path
import shutil, tarfile
R=Path(__file__).resolve().parent
D=R/'stage4_nan'; S=R/'stage3'
assert not D.exists(), D
shutil.copytree(S,D,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
p=D/'FluidX3D/src/defines.hpp';s=p.read_text();s=s.replace('//#define CITY_STABILITY_MONITOR','//#define CITY_STABILITY_MONITOR\n#define CITY_NAN_FORENSICS');p.write_text(s)
p=D/'FluidX3D/src/kernel.cpp';s=p.read_text()
anchor=') + R(kernel void update_fields) + "("'
assert s.count(anchor)==1
kern='''
)+"#ifdef CITY_NAN_FORENSICS"+R(
// Build compact corner-candidate list exactly once after native flags have been initialized.
kernel void city_corner_index(const global uchar* flags, global uint* ids, global uint* count) {
 const uint n=get_global_id(0); if(n>=def_N) return;
 const uint xy=def_Nx*def_Ny, z=n/xy, y=(n/def_Nx)%def_Ny, x=n%def_Nx;
 if(x==0u||x+1u==def_Nx||y==0u||y+1u==def_Ny||z==0u||z+1u==def_Nz||((flags[n]&TYPE_BO)==TYPE_S))return;
 uint solid=0u;
 for(int dz=-1;dz<=1;dz++)for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++){
  if(!dx&&!dy&&!dz)continue;
  const uint j=n+dx+def_Nx*dy+xy*dz;
  solid+=((flags[j]&TYPE_BO)==TYPE_S);
 }
 if(solid>=12u){ const uint k=atomic_inc((volatile global uint*)count);ids[k]=n; }
}
// The ring is cell-major [slot,candidate,32] and holds *post-step* streamed DDFs.
// Stored fields: rho,ux,uy,uz, T, effective omega, 19 f_i, 7 g_i.
kernel void city_corner_snapshot(const global uint* ids, const uint count, const uint slot,
 const global fpxx* fi,const global float* rho,const global float* u,const global uchar* flags,
 const ulong t, global float* ring
#ifdef TEMPERATURE
 ,const global fpxx* gi,const global float* T
#endif
){
 const uint k=get_global_id(0);if(k>=count)return;
 const uxx n=(uxx)ids[k]; const ulong base=((ulong)slot*count+k)*32ul;
 uxx j[def_velocity_set];neighbors(n,j);float f[def_velocity_set];load_f(n,f,fi,j,t);
 ring[base]=rho[n];ring[base+1ul]=u[n];ring[base+2ul]=u[def_N+n];ring[base+3ul]=u[2ul*def_N+n];
 float r=0.0f;for(uint i=0u;i<def_velocity_set;i++)r+=f[i];r+=1.0f;
 float feq[def_velocity_set];calculate_f_eq(r,u[n],u[def_N+n],u[2ul*def_N+n],feq);
 float Hxx=0.0f,Hyy=0.0f,Hzz=0.0f,Hxy=0.0f,Hxz=0.0f,Hyz=0.0f;
 for(uint i=1u;i<def_velocity_set;i++){
  const float df=f[i]-feq[i], cx=c(i),cy=c(def_velocity_set+i),cz=c(2u*def_velocity_set+i);
  Hxx+=cx*cx*df;Hyy+=cy*cy*df;Hzz+=cz*cz*df;
  Hxy+=cx*cy*df;Hxz+=cx*cz*df;Hyz+=cy*cz*df;
 }
 const float Q=sq(Hxx)+sq(Hyy)+sq(Hzz)+2.0f*(sq(Hxy)+sq(Hxz)+sq(Hyz));
 ring[base+5ul]=2.0f/(1.0f/def_w+sqrt(sq(1.0f/def_w)+0.76421222f*sqrt(Q)/r));
 for(uint i=0u;i<19u;i++)ring[base+6ul+i]=i<def_velocity_set?f[i]:NAN;
#ifdef TEMPERATURE
 ring[base+4ul]=T[n];uxx j7[7];neighbors_temperature(n,j7);float g[7];load_g(n,g,gi,j7,t);
 for(uint i=0u;i<7u;i++)ring[base+25ul+i]=g[i];
#else
 ring[base+4ul]=NAN;for(uint i=0u;i<7u;i++)ring[base+25ul+i]=NAN;
#endif
}
kernel void city_nan_min(const global float* rho,const global float* u,const global uchar* flags,global uint* result){
 const uint n=get_global_id(0);if(n>=def_N||((flags[n]&TYPE_BO)==TYPE_S))return;
 if(!isfinite(rho[n])||!isfinite(u[n])||!isfinite(u[def_N+n])||!isfinite(u[2ul*def_N+n]))
  atomic_min((volatile global uint*)result,n);
}
// Gather current 27-cell neighborhood on GPU, preserving DDFs' current Esoteric-Pull time layer.
kernel void city_nan_neighborhood(const global fpxx* fi,const global float* rho,const global float* u,
 const global uchar* flags,const ulong t,const uint center,global float* out
#ifdef TEMPERATURE
 ,const global fpxx* gi,const global float* T
#endif
){
 const uint k=get_global_id(0);if(k>=27u)return;
 const int dx=(int)(k%3u)-1,dy=(int)((k/3u)%3u)-1,dz=(int)(k/9u)-1;
 const uint xy=def_Nx*def_Ny,x=center%def_Nx,y=(center/def_Nx)%def_Ny,z=center/xy;
 const ulong base=(ulong)k*34ul;
 if((int)x+dx<0||(int)x+dx>=(int)def_Nx||(int)y+dy<0||(int)y+dy>=(int)def_Ny||(int)z+dz<0||(int)z+dz>=(int)def_Nz){for(uint i=0u;i<34u;i++)out[base+i]=NAN;return;}
 const uxx n=center+dx+(int)def_Nx*dy+(int)xy*dz;
 out[base]=as_float((uint)flags[n]);out[base+1ul]=rho[n];
 out[base+2ul]=u[n];out[base+3ul]=u[def_N+n];out[base+4ul]=u[2ul*def_N+n];
 uxx j[def_velocity_set];neighbors(n,j);float f[def_velocity_set];load_f(n,f,fi,j,t);
 for(uint i=0u;i<19u;i++)out[base+5ul+i]=i<def_velocity_set?f[i]:NAN;
#ifdef TEMPERATURE
 out[base+24ul]=T[n];uxx j7[7];neighbors_temperature(n,j7);float g[7];load_g(n,g,gi,j7,t);for(uint i=0u;i<7u;i++)out[base+25ul+i]=g[i];
#else
 for(uint i=24u;i<32u;i++)out[base+i]=NAN;
#endif
 out[base+32ul]=0.0f;out[base+33ul]=0.0f;
}
)+"#endif"+R(

'''
s=s.replace(anchor,kern+anchor);p.write_text(s)
p=D/'FluidX3D/src/setup.cpp';s=p.read_text();anchor='        auto render_frame_before_step = [&]() {';assert s.count(anchor)==1
init='''#ifdef CITY_NAN_FORENSICS
        if(lbm.get_D()!=1u||lbm.get_N()>0xffffffffull)print_error("forensics requires single uint-indexed GPU domain");
        auto* nd=lbm.lbm_domain[0];auto& dev=const_cast<Device&>(nd->get_device());
        const ulong nn=lbm.get_N();
        Memory<uint> ids(dev,nn,1u,false), count(dev,1u), bad(dev,1u);
        Kernel build(dev,nn,"city_corner_index",nd->flags,ids,count);
        count.x[0]=0u;count.write_to_device();build.enqueue_run();nd->finish_queue();count.read_from_device();
        const uint nc=count.x[0];if(nc==0u)print_error("no corner candidate cells");
        ids.add_host_buffer(); // one-off compact transfer; no per-step full-domain readback
        Memory<float> ring(dev,(ulong)nc*5ull*32ull,1u,false);
        Memory<float> hood(dev,27ull*34ull);
        Kernel snap(dev,nc,"city_corner_snapshot",ids,nc,0u,nd->fi,nd->rho,nd->u,nd->flags,lbm.get_t(),ring);
#ifdef TEMPERATURE
        snap.add_parameters(nd->gi,nd->T);
#endif
        Kernel scan(dev,nn,"city_nan_min",nd->rho,nd->u,nd->flags,bad);
        Kernel gather(dev,27ull,"city_nan_neighborhood",nd->fi,nd->rho,nd->u,nd->flags,lbm.get_t(),0u,hood);
#ifdef TEMPERATURE
        gather.add_parameters(nd->gi,nd->T);
#endif
        std::ofstream event(parent+"/RESULTS/nan_event.txt",std::ios::out|std::ios::trunc);
        event<<"candidate_count="<<nc<<" grid="<<lbm.get_Nx()<<","<<lbm.get_Ny()<<","<<lbm.get_Nz()<<"\\n"<<std::flush;
        println("CITY_NAN_CANDIDATES "+std::to_string(nc));
        auto check_nan = [&]() {
            const ulong tt=lbm.get_t();const uint slot=(uint)(tt%5ull);
            snap.set_parameters(2u,slot);snap.set_parameters(7u,tt).enqueue_run();
            bad.x[0]=0xffffffffu;bad.write_to_device();scan.enqueue_run();bad.read_from_device();
            if(bad.x[0]==0xffffffffu)return;
            const uint n=bad.x[0],nx=lbm.get_Nx(),ny=lbm.get_Ny(),xy=nx*ny;
            event<<"first_detected_step="<<tt<<" min_index="<<n<<" xyz="<<(n%nx)<<","<<((n/nx)%ny)<<","<<(n/xy)<<"\\n"<<std::flush;
            gather.set_parameters(4u,tt,n).enqueue_run();nd->finish_queue();hood.read_from_device();
            std::ofstream current(parent+"/RESULTS/nan_neighborhood.csv",std::ios::out|std::ios::trunc);
            current<<"offset,flag_as_float,rho,ux,uy,uz,fi0..18,T,gi0..6,unused0,unused1\\n";
            for(uint k=0;k<27u;k++){current<<k;for(uint j=0;j<34u;j++)current<<','<<std::setprecision(9)<<hood.x[(ulong)k*34ull+j];current<<'\\n';}current.flush();
            ids.read_from_device(0ull,(ulong)nc);size_t found=nc;
            for(size_t k=0;k<nc;k++)if(ids.x[k]==n){found=k;break;}
            event<<"candidate_rank="<<(found==nc?-1ll:(long long)found)<<"\\n"<<std::flush;
            if(found!=nc){
                std::ofstream hist(parent+"/RESULTS/nan_history.csv",std::ios::out|std::ios::trunc);
                hist<<"step,rho,ux,uy,uz,T,omega,fi0..18,gi0..6\\n";
                for(int lag=4;lag>=0;lag--){if(tt<(ulong)lag)continue;const ulong t0=tt-(ulong)lag;
                    const ulong off=((ulong)(t0%5ull)*nc+found)*32ull;
                    float local[32];dev.get_cl_queue().enqueueReadBuffer(ring.get_cl_buffer(),CL_TRUE,off*sizeof(float),sizeof(local),local);
                    hist<<t0;for(uint j=0;j<32u;j++)hist<<','<<std::setprecision(9)<<local[j];hist<<'\\n';
                }hist.flush();
            }
            print_error("CITY_NAN_FIRST step="+std::to_string(tt)+" idx="+std::to_string(n));
        };
#endif
'''
s=s.replace(anchor,init+anchor)
# initialize in GRAPHICS branch before candidate builder
old='        lbm.run(0u, total_steps); // initialize fields and graphics buffers\n';assert s.count(old)==1
s=s.replace(old,old) # already before render_frame
s=s.replace('            maybe_write_unsteady_u();\n            const bool avg_sampled = process_post_step_samples();', '            maybe_write_unsteady_u();\n#ifdef CITY_NAN_FORENSICS\n            check_nan();\n#endif\n            const bool avg_sampled = process_post_step_samples();')
# also non graphics branch: local variables need own init, disable non-GRAPHICS using explicit guard
assert '#define GRAPHICS' in (D/'FluidX3D/src/defines.hpp').read_text()
p.write_text(s)
archive=R/'city_nan_stage4_inputs.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz') as tar:
 tar.add(D/'FluidX3D',arcname='FluidX3D');tar.add(D/'case',arcname='case')
print('prepared',archive,archive.stat().st_size)
