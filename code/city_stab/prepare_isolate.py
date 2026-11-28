"""Create immutable Case E input bundle with read-only diagnostic instrumentation."""
from pathlib import Path
import shutil, tarfile, hashlib
ROOT=Path(__file__).resolve().parent
src=ROOT/'stage2'
out=ROOT/'isolate_stage_v2'
assert not out.exists(), 'refuse overwrite'
shutil.copytree(src,out,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.csv','*.log'))
p=out/'FluidX3D/src/setup.cpp'
s=p.read_text()
a=s.index('#ifdef CITY_STABILITY_MONITOR\n        std::ofstream city_monitor')
b=s.index('#endif\n\n#ifdef TEMPERATURE',a)+len('#endif')
block=r'''#ifdef CITY_STABILITY_MONITOR
        std::ofstream city_monitor(parent+"/RESULTS/city_stability.csv",std::ios::out|std::ios::trunc);
        if(!city_monitor) print_error("cannot open city stability trace");
        city_monitor << "step,max_u_lattice,min_rho,max_rho,mass_fluid,up25_u2_lattice,up42_u2_lattice,flux_west,flux_east,flux_south,flux_north,flux_top,flux_net_out,first_nonfinite_xyz_component,flag,neighbors_s_e_fluid,ground_first,building_adjacent,previous_step,previous_rho,previous_speed,previous_wall_force\n" << std::flush;
        const size_t mon_n=(size_t)lbm.get_Nx()*lbm.get_Ny()*lbm.get_Nz();
        std::vector<float> last_rho(mon_n, std::numeric_limits<float>::quiet_NaN());
        std::vector<float> last_speed(mon_n, std::numeric_limits<float>::quiet_NaN());
        ulong last_step=0ull;
        auto monitor_city = [&]() {
            if(lbm.get_D()!=1u) print_error("city monitor requires one subdomain");
            enqueue_read_u_rho();
            const size_t nx=lbm.get_Nx(), ny=lbm.get_Ny(), nz=lbm.get_Nz();
            const size_t N=nx*ny*nz;
            if(N!=mon_n) print_error("city monitor dimensions changed");
            auto* dom=lbm.lbm_domain[0];
            auto idx=[&](size_t x,size_t y,size_t z){return x+nx*(y+ny*z);};
            auto fluid=[&](size_t i){return (dom->flags.x[i]&0x03u)!=TYPE_S;};
            double mass=0.0, max_u2=0.0, flux[5]={0.,0.,0.,0.,0.};
            float lo=std::numeric_limits<float>::infinity(),hi=-std::numeric_limits<float>::infinity();
            size_t bad=N; const char* component="";
            for(size_t z=0;z<nz;z++) for(size_t y=0;y<ny;y++) for(size_t x=0;x<nx;x++) {
                const size_t i=idx(x,y,z);
                if(!fluid(i)) continue;
                const float r=dom->rho.x[i],u=dom->u.x[i],v=dom->u.y[i],w=dom->u.z[i];
                if(!std::isfinite(r)||!std::isfinite(u)||!std::isfinite(v)||!std::isfinite(w)) {
                    if(bad==N){bad=i;component=!std::isfinite(r)?"rho":!std::isfinite(u)?"ux":!std::isfinite(v)?"uy":"uz";}
                    continue;
                }
                mass+=r;lo=std::min(lo,r);hi=std::max(hi,r);
                const double u2=(double)u*u+(double)v*v+(double)w*w;
                max_u2=std::max(max_u2,u2);
                // Physical outward normals, lattice-unit flux per face cell; corners deliberately count per face.
                if(x==0) flux[0]-=(double)r*u;
                if(x+1==nx) flux[1]+=(double)r*u;
                if(y==0) flux[2]-=(double)r*v;
                if(y+1==ny) flux[3]+=(double)r*v;
                if(z+1==nz) flux[4]+=(double)r*w;
                last_rho[i]=r;last_speed[i]=(float)std::sqrt(u2);
            }
            const size_t pz=std::min(nz-1u,(size_t)21u);
            auto at=[&](size_t x)->float {const size_t i=idx(std::min(nx-1u,x),ny/2u,pz);return dom->u.x[i];};
            std::string location="", neigh="", flag="", ground="",adj="",oldrho="",oldspeed="",oldforce="unavailable";
            if(bad<N) {
                const size_t bz=bad/(nx*ny),by=(bad/nx)%ny,bx=bad%nx;
                location=std::to_string(bx)+":"+std::to_string(by)+":"+std::to_string(bz)+":"+component;
                flag=std::to_string((unsigned)dom->flags.x[bad]);
                unsigned ns=0,ne=0,nf=0; bool touching=false;
                for(int dz=-1;dz<=1;dz++) for(int dy=-1;dy<=1;dy++) for(int dx=-1;dx<=1;dx++) {
                    if(!dx&&!dy&&!dz)continue;
                    const int xx=(int)bx+dx,yy=(int)by+dy,zz=(int)bz+dz;
                    if(xx<0||xx>=(int)nx||yy<0||yy>=(int)ny||zz<0||zz>=(int)nz)continue;
                    const unsigned f=dom->flags.x[idx((size_t)xx,(size_t)yy,(size_t)zz)]&0x03u;
                    ns+=(f==TYPE_S);ne+=(f==TYPE_E);nf+=(f!=TYPE_S&&f!=TYPE_E);
                    if(f==TYPE_S&&zz>0)touching=true;
                }
                neigh=std::to_string(ns)+":"+std::to_string(ne)+":"+std::to_string(nf);
                ground=(bz==21 && (dom->flags.x[idx(bx,by,bz-1)]&0x03u)==TYPE_S)?"1":"0";adj=touching?"1":"0";
                if(last_step>0&&std::isfinite(last_rho[bad])) {oldrho=std::to_string(last_rho[bad]);oldspeed=std::to_string(last_speed[bad]);}
                // The current 3D force buffer is not a historical per-cell snapshot; never mislabel it as one.
            }
            double total=0.;for(double f:flux)total+=f;
            city_monitor << lbm.get_t()<<','<<std::setprecision(12)<<std::sqrt(max_u2)<<','<<lo<<','<<hi<<','<<mass<<','<<at(25u)<<','<<at(42u);
            for(double f:flux)city_monitor<<','<<f;
            city_monitor<<','<<total<<','<<location<<','<<flag<<','<<neigh<<','<<ground<<','<<adj<<','<<last_step<<','<<oldrho<<','<<oldspeed<<','<<oldforce<<'\n'<<std::flush;
            if(bad<N) {println("CITY_FIRST_NONFINITE step="+std::to_string(lbm.get_t())+" cell="+location+" flags="+flag+" neighbors="+neigh+" prior_step="+std::to_string(last_step));print_error("nonfinite city field");}
            last_step=lbm.get_t();
        };
#endif'''
# The raw template spells C++ newline with two slashes; reduce it to one.
block=block.replace(chr(92)*2+'n',chr(92)+'n')
s=s[:a]+block+s[b:]
p.write_text(s)
# Exact code compares are limited to read-only instrumentation and normal stability controller.
archive=ROOT/'city_isolate_inputs_v2.tar.gz'
assert not archive.exists(),'refuse overwrite archive'
with tarfile.open(archive,'w:gz') as tar:
    tar.add(out/'FluidX3D',arcname='FluidX3D')
    tar.add(out/'case',arcname='case')
print('bundle',archive,'sha256',hashlib.sha256(archive.read_bytes()).hexdigest())
