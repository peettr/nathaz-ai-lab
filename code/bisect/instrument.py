from pathlib import Path
r=Path(__file__).parent/'stage/FluidX3D/src'
p=r/'kernel.cpp';s=p.read_text()
needle=')+"#ifdef FORCE_FIELD"+R(\n)+R(kernel void update_force_field'
assert s.count(needle)==1
s=s.replace(needle,''')+"#ifdef CITY_STABILITY_MONITOR"+R(
)+R(kernel void bisect_first_bad(const global float* rho, const global float* u, const global uchar* flags, global uint* first) {
 const uint n=get_global_id(0);
 if(n>=def_N || (flags[n]&TYPE_BO)==TYPE_S) return;
 const float x=u[n], y=u[def_N+(ulong)n], z=u[2ul*def_N+(ulong)n], r=rho[n];
 if(!(r>=0.8f&&r<=1.2f) || !(x*x+y*y+z*z<=0.0625f)) atomic_min((volatile global uint*)first,n);
})
)+"#endif"+R(
'''+needle,1)
p.write_text(s)
p=r/'setup.cpp';s=p.read_text()
needle='        auto monitor_city = [&]() {'
assert s.count(needle)==1
s=s.replace(needle,'''        auto* bis_dom=lbm.lbm_domain[0];
        Memory<uint> bis_bad(bis_dom->get_device(),1u);
        Kernel bis_kernel(bis_dom->get_device(),mon_n,"bisect_first_bad",bis_dom->rho,bis_dom->u,bis_dom->flags,bis_bad);
        std::ofstream bis_out(parent+"/RESULTS/bisect_event.csv",std::ios::out|std::ios::trunc);
        bis_out << "step,index,x,y,z,flag,rho,ux,uy,uz,link_direction_q_owner_backflags\\n" << std::flush;
        auto bisect_check = [&]() {
#ifndef UPDATE_FIELDS
            bis_dom->enqueue_update_fields();
#endif
            bis_bad[0]=0xffffffffu;bis_bad.write_to_device();bis_kernel.enqueue_run();bis_bad.read_from_device();
            if(bis_bad[0]==0xffffffffu) return;
            const size_t ix=bis_bad[0], nx=lbm.get_Nx(), ny=lbm.get_Ny();
            bis_dom->rho.enqueue_read_from_device();bis_dom->u.enqueue_read_from_device();bis_dom->finish_queue();
            const size_t x=ix%nx,y=(ix/nx)%ny,z=ix/(nx*ny);
            bis_out<<lbm.get_t()<<','<<ix<<','<<x<<','<<y<<','<<z<<','<<(unsigned)bis_dom->flags.x[ix]<<','<<bis_dom->rho.x[ix]<<','<<bis_dom->u.x[ix]<<','<<bis_dom->u.y[ix]<<','<<bis_dom->u.z[ix]<<',';
            // Link annotation is joined offline from the exact run CSR and native flags.

            bis_out<<'\\n'<<std::flush;
            print_error("BISECT_FIRST_BAD step="+std::to_string(lbm.get_t())+" index="+std::to_string(ix));
        };
        auto monitor_city = [&]() {''',1)
# avoid reading 470 MB CSR every event? only one event, yes
needle='            if(lbm.get_t()%50ull==0ull) monitor_city();'
assert s.count(needle)==2
s=s.replace(needle,'            bisect_check();\n'+needle)
p.write_text(s)
print('instrumented',r)
