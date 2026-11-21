from pathlib import Path
import shutil,tarfile
base=Path('./24_Urban_Wind_LBM/06_Logs/wp1_nearwall')
out=Path(__file__).resolve().parent
src=base/'A_impl/stage_precision_full'
stage=out/'stage';assert not stage.exists()
shutil.copytree(src/'FluidX3D',stage/'FluidX3D');shutil.copytree(src/'case',stage/'case')
p=stage/'FluidX3D/src'
def edit(name,old,new):
 f=p/name;s=f.read_text();assert s.count(old)==1,(name,old,s.count(old));f.write_text(s.replace(old,new))
edit('lbm.hpp','Memory<float> ground_tau_count; // actual step counts, one writer per column','Memory<float> ground_tau_count; // actual step counts, one writer per column\n\tMemory<float> stress_nut_probe; // 3 x locations, 5 y lines, 30 heights; lattice units')
edit('lbm.cpp','kernel_stream_collide.add_parameters(ground_tau_sum, ground_tau_count);','kernel_stream_collide.add_parameters(ground_tau_sum, ground_tau_count);\n\tstress_nut_probe = Memory<float>(device, 450ul);\n\tkernel_stream_collide.add_parameters(stress_nut_probe);')
edit('kernel.cpp','global float* ground_tau_sum, global float* ground_tau_count\n','global float* ground_tau_sum, global float* ground_tau_count, global float* stress_nut_probe\n')
# export actual relaxation coefficient from the same collision, only 450 distinct writes per step
needle='\t} // modity LBM relaxation rate by increasing effective viscosity in regions of high strain rate (add turbulent eddy viscosity), nu_eff = nu_0+nu_t\n'
replacement=needle+'''
)+"#ifdef GROUND_WALL_MODEL"+R(
    { const uint3 xyz=coordinates(n); const int iz=(int)xyz.z+def_Oz-21;
      const int ix=xyz.x==200u ? 0 : (xyz.x==300u ? 1 : (xyz.x==400u ? 2 : -1));
      const int iy=xyz.y==40u ? 0 : (xyz.y==70u ? 1 : (xyz.y==100u ? 2 : (xyz.y==130u ? 3 : (xyz.y==160u ? 4 : -1))));
      if(ix>=0 && iy>=0 && iz>=0 && iz<30)
          stress_nut_probe[(ix*5+iy)*30+iz]=(1.0f/w-1.0f/def_w)/3.0f;
    }
)+"#endif"+R(
'''
edit('kernel.cpp',needle,replacement)
# host covariance and sampled viscosity, using same 500 samples/40step avg window
needle='        auto accumulate_from_buffers = [&]() {\n'
replacement='''        std::vector<double> stress_u(450,0.),stress_w(450,0.),stress_uw(450,0.),stress_nut(450,0.);
        auto accumulate_stress = [&]() {
            auto* dom=lbm.lbm_domain[0];
            dom->stress_nut_probe.read_from_device();
            for(int ix=0;ix<3;ix++) for(int iy=0;iy<5;iy++) for(int iz=0;iz<30;iz++) {
                const uint x=200u+100u*(uint)ix, y=40u+30u*(uint)iy,z=21u+(uint)iz;
                const size_t i=(size_t)x+(size_t)y*500u+(size_t)z*500u*200u;
                const size_t j=(size_t)(ix*5+iy)*30u+(size_t)iz;
                const double ux=dom->u.x[i],uz=dom->u.z[i];
                stress_u[j]+=ux;stress_w[j]+=uz;stress_uw[j]+=ux*uz;
                stress_nut[j]+=dom->stress_nut_probe.x[j];
            }
        };
        auto write_stress = [&]() {
            if(!avg_count)return;
            std::ofstream out(parent+"/RESULTS/stress_samples.csv");
            out << "x,y,z,n,u_lu,w_lu,uw_lu,nut_lu\\n";
            for(int ix=0;ix<3;ix++) for(int iy=0;iy<5;iy++) for(int iz=0;iz<30;iz++) {
                const size_t j=(size_t)(ix*5+iy)*30u+(size_t)iz;
                out << 200+100*ix << ',' << 40+30*iy << ',' << iz+1 << ',' << avg_count << ','
                    << stress_u[j]/avg_count << ',' << stress_w[j]/avg_count << ','
                    << stress_uw[j]/avg_count << ',' << stress_nut[j]/avg_count << '\\n';
            }
        };
        auto accumulate_from_buffers = [&]() {
            accumulate_stress();
'''
edit('setup.cpp',needle,replacement)
edit('setup.cpp','        finalize_avg();\n#ifdef GROUND_WALL_MODEL\n        write_ground_tau_actual();','        finalize_avg();\n#ifdef GROUND_WALL_MODEL\n        write_stress();\n        write_ground_tau_actual();') if False else None
# two run branches
f=p/'setup.cpp';s=f.read_text();old='        finalize_probes();\n#ifdef GROUND_WALL_MODEL\n        write_ground_tau_actual();';assert s.count(old)==2;s=s.replace(old,'        finalize_probes();\n#ifdef GROUND_WALL_MODEL\n        write_stress();\n        write_ground_tau_actual();');f.write_text(s)
with tarfile.open(out/'stress_inputs.tar.gz','w:gz') as t:
 t.add(stage/'FluidX3D',arcname='FluidX3D');t.add(stage/'case',arcname='case')
print(out/'stress_inputs.tar.gz')
