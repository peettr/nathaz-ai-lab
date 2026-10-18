from pathlib import Path
import shutil,hashlib,json,tarfile
R=Path(__file__).resolve().parent
S=R.parent/'approach_z0/stage_FG0z'
for tag,disable in [('FGz2r',False),('FGz2ns',True)]:
 d=R/('stage_'+tag)
 assert not d.exists(),d
 shutil.copytree(S,d,ignore=shutil.ignore_patterns('bin','obj','RESULTS','*.vtk','*.log'))
 p=d/'FluidX3D/src/setup.cpp';s=p.read_text()
 # Do not disable enable_top_sponge: it also controls extension and top BC position.
 if disable:
  old='top_sponge_active = top_sponge_grid_extend && sponge_tau_s > 0.0f && mode_supported && has_vertical_room;'
  assert s.count(old)==1
  s=s.replace(old,old+'\n        top_sponge_active = false; // diagnostic: retain extension/BC, suppress TOP_SPONGE collision force')
 anchor='''            write_avg_vtk(avg_file, lbm.get_Nx(), lbm.get_Ny(), lbm.get_Nz(),'''
 assert s.count(anchor)==1
 code='''            // INLFLOW_SPONGE_DIAG: all-y, time-window plane moments; no field export.
            {
                const uint nx=lbm.get_Nx(),ny=lbm.get_Ny(),nz=lbm.get_Nz();
                const int xs[]={5,42,120,200,300,400};
                const double uf=units.si_u(1.0f);
                std::ofstream csv(parent+"/RESULTS/full_height_planes.csv",std::ios::out|std::ios::trunc);
                csv << "x,z_index,z_agl_m,n,ux_mps,rho_ux_lattice,U_mps,k_m2s2,uw_resolved_m2s2\\n";
                for(int x:xs) for(uint z=0;z<nz;++z) {
                    double sx=0.,srux=0.,speed=0.,sk=0.,suw=0.;ulong count=0;
                    for(uint y=1;y+1<ny;++y) {
                        const ulong n=(ulong)x+(ulong)nx*((ulong)y+(ulong)ny*(ulong)z);
                        if((flags_host[n]&TYPE_S)!=0u || (flags_host[n]&TYPE_E)!=0u) continue;
                        const ulong i3=3ull*n;
                        const double ux=avg_u[i3],uy=avg_u[i3+1],uz=avg_u[i3+2];
                        const double k=.5*(M2_u[n]+M2_v[n]+M2_w[n])/(double)avg_count;
                        sx+=ux;srux+=(double)avg_rho[n]*ux;speed+=sqrt(ux*ux+uy*uy+uz*uz);
                        sk+=k;suw+=0.;++count;
                    }
                    if(count) csv<<x<<','<<z<<','<<(int)z-20<<','<<count<<','
                      <<sx/count*uf<<','<<srux/count<<','<<speed/count*uf<<','<<sk/count*uf*uf<<','
                      <<"nan"<<'\\n';
                }
                csv.flush();if(!csv) print_error("full-height plane write failed");
            }
'''
 # rho*u from product of mean fields is NOT mean rho*u. Replace with time-window exact cross moment below.
 s=s.replace(anchor,code+anchor)
 # accumulate exact rho*ux and resolved uw covariance in bounded station-height buffers per sample
 mark='''        auto accumulate_from_buffers = [&]() {'''
 assert s.count(mark)==1
 s=s.replace(mark,'''        const int sponge_diag_xs[]={5,42,120,200,300,400};
        const uint sponge_diag_nz=lbm.get_Nz();
        std::vector<double> sponge_diag_rux(6u*sponge_diag_nz,0.),sponge_diag_uw(6u*sponge_diag_nz,0.);
        auto accumulate_from_buffers = [&]() {''')
 mark2='''            ++avg_count;
            const float inv_n'''
 assert s.count(mark2)==1
 s=s.replace(mark2,'''            // Exact mean rho*ux and ux*uz sampled on same window as avg_u; exclude boundaries.
            const uint dnx=lbm.get_Nx(),dny=lbm.get_Ny();
            for(uint j=0;j<6u;++j) for(uint z=0;z<sponge_diag_nz;++z) {
                double rux=0.,uw=0.;uint count=0u;
                for(uint y=1;y+1<dny;++y) {
                    const ulong n=(ulong)sponge_diag_xs[j]+(ulong)dnx*((ulong)y+(ulong)dny*(ulong)z);
                    if((lbm.flags[n]&TYPE_S)!=0u || (lbm.flags[n]&TYPE_E)!=0u) continue;
                    rux+=(double)lbm.rho[n]*(double)lbm.u.x[n];
                    uw+=(double)lbm.u.x[n]*(double)lbm.u.z[n];++count;
                }
                if(count) {sponge_diag_rux[j*sponge_diag_nz+z]+=rux/count;
                           sponge_diag_uw[j*sponge_diag_nz+z]+=uw/count;}
            }
            ++avg_count;
            const float inv_n''')
 s=s.replace('''                for(int x:xs) for(uint z=0;z<nz;++z) {''','''                for(uint j=0;j<6u;++j) for(uint z=0;z<nz;++z) {
                    const int x=xs[j];''')
 s=s.replace('''                      <<sx/count*uf<<','<<srux/count<<','<<speed/count*uf<<','<<sk/count*uf*uf<<','
                      <<"nan"<<'\\n';''','''                      <<sx/count*uf<<','<<sponge_diag_rux[j*nz+z]/(double)avg_count<<','
                      <<speed/count*uf<<','<<sk/count*uf*uf<<','
                      <<-(sponge_diag_uw[j*nz+z]/(double)avg_count-sx/count*([&](){double v=0.;for(uint y=1;y+1<ny;++y){const ulong n=(ulong)x+(ulong)nx*((ulong)y+(ulong)ny*(ulong)z);if((flags_host[n]&TYPE_S)==0u && (flags_host[n]&TYPE_E)==0u)v+=avg_u[3ull*n+2ull];}return v/count;})())*uf*uf<<'\\n';''')
 p.write_text(s)
 files=['case/wind_bc/profile.dat','case/proj_temp/CaseE_PF.stl','case/conf.luwpf','FluidX3D/src/setup.cpp','FluidX3D/src/defines.hpp','FluidX3D/src/kernel.cpp']
 m={'tag':tag,'disable_sponge_force':disable,'z0_si':.002,'files':{f:hashlib.sha256((d/f).read_bytes()).hexdigest() for f in files}}
 (R/(tag+'_manifest.json')).write_text(json.dumps(m,indent=2)+'\n')
 with tarfile.open(R/(tag+'_inputs.tar.gz'),'w:gz') as t:
  t.add(d/'FluidX3D',arcname='FluidX3D');t.add(d/'case',arcname='case')
 print(tag,m)
