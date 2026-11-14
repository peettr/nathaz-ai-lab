from pathlib import Path
import tarfile,shutil
b=Path(__file__).resolve().parent
s=b/'FluidX3D/src/setup.cpp';t=s.read_text();needle='            std::ofstream out(parent+"/RESULTS/wall_tau_actual.csv");'
assert t.count(needle)==1
inject='''            std::ofstream along(parent+"/RESULTS/wall_force_x.csv");
            along << "x,columns,count_min,count_max,fx_over_rho_lattice_sum,mean_tau_over_rho_lattice\\n";
            for(uint x=100u;x<=400u;x++) {
                double fxsum=0.0,tausum=0.0;float cmin=1e30f,cmax=0.0f;uint cols=0u;
                for(uint y=1u;y+1u<lbm.get_Ny();y++) {
                    const size_t i=(size_t)x+(size_t)y*lbm.get_Nx();
                    const float count=d->ground_tau_count.x[i];
                    if(count<=0.0f) continue;
                    fxsum+=d->ground_tau_sum.y[i]/count;
                    tausum+=d->ground_tau_sum.x[i]/count;
                    cmin=fminf(cmin,count);cmax=fmaxf(cmax,count);cols++;
                }
                along << x << ',' << cols << ',' << cmin << ',' << cmax << ',' << fxsum << ',' << tausum << '\\n';
            }
'''
t=t.replace(needle,inject+needle)
# stage only within the owned directory; don't modify the previous candidate
p=b/'stage_precision_full';assert not p.exists();shutil.copytree(b/'FluidX3D',p/'FluidX3D');shutil.copytree(b/'case',p/'case');(p/'FluidX3D/src/setup.cpp').write_text(t)
with tarfile.open(b/'precision_full_inputs.tar.gz','w:gz') as f:
 f.add(p/'FluidX3D',arcname='FluidX3D');f.add(p/'case',arcname='case')
print('staged',b/'precision_full_inputs.tar.gz')
