from pathlib import Path
p=Path(__file__).resolve().parent/'stage_C1v2/FluidX3D/src/setup.cpp'
s=p.read_text()
a='float lo=std::numeric_limits<float>::infinity(),hi=-std::numeric_limits<float>::infinity();'
b=a+'\n            size_t loidx=N,hiidx=N;'
assert s.count(a)==1;s=s.replace(a,b)
a='mass+=r;lo=std::min(lo,r);hi=std::max(hi,r);'
b='mass+=r;if(r<lo){lo=r;loidx=i;}if(r>hi){hi=r;hiidx=i;}'
assert s.count(a)==1;s=s.replace(a,b)
a='city_monitor << "step,max_u_lattice,min_rho,max_rho,mass_fluid,'
b='city_monitor << "step,max_u_lattice,min_rho,max_rho,mass_fluid,'
# Keep existing column contract; write extrema to separate trace to avoid parser incompatibility.
a='        const size_t mon_n=(size_t)lbm.get_Nx()*lbm.get_Ny()*lbm.get_Nz();'
b='            std::ofstream extrema_monitor(parent+"/RESULTS/extrema.csv",std::ios::out|std::ios::trunc);\n            extrema_monitor << "step,min_x,min_y,min_z,max_x,max_y,max_z,min_rho,max_rho\\n" << std::flush;\n'+a
assert s.count(a)==1;s=s.replace(a,b)
# identify exact write site
marker="<<oldforce<<'\\n'<<std::flush;"
assert s.count(marker)==1;s=s.replace(marker,marker+'\n            extrema_monitor << lbm.get_t() << "," << loidx%nx << "," << (loidx/nx)%ny << "," << loidx/(nx*ny) << "," << hiidx%nx << "," << (hiidx/nx)%ny << "," << hiidx/(nx*ny) << "," << lo << "," << hi << "\\n" << std::flush;')
s=s.replace('native_flags_z0_24.bin','native_flags_z0_90.bin').replace('Nz<25u','Nz<91u').replace('zf<25u','zf<91u')
p.write_text(s)
print('instrumented',p)
