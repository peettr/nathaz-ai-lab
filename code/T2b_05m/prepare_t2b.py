#!/usr/bin/env python3
"""Stage T2b from immutable B2u archive, patch only inlet-height map and diagnostic flags."""
import hashlib, pathlib, shutil, sys, tarfile
r=pathlib.Path(sys.argv[1]).resolve()
with tarfile.open(r/'B2u_inputs.tar.gz') as tf:
    for m in tf.getmembers():
        p=(r/m.name).resolve()
        if not p.is_relative_to(r) or m.issym() or m.islnk(): raise RuntimeError(m.name)
    tf.extractall(r,filter='data')
src=r/'FluidX3D/src'; setup=src/'setup.cpp'; text=setup.read_text()
old='''    int nmodes = k_vk_nmodes_default;
    ulong seed = 100ull;
    int update_stride = 1;'''
# The first occurrence belongs to VkInletSettings, the second to VkInletRuntimeConfig.
assert text.count(old)==2, text.count(old)
text=text.replace(old,'''    int nmodes = k_vk_nmodes_default;
    ulong seed = 100ull;
    float ground_z_lbm = 20.0f;
    float cell_size_m = 1.0f;
    int update_stride = 1;''',1) if False else text
anchor='''struct VkInletRuntimeConfig {
    bool enable = true;'''
assert text.count(anchor)==1
pre,tail=text.split(anchor)
assert tail.count(old)==1
tail=tail.replace(old,'''    int nmodes = k_vk_nmodes_default;
    ulong seed = 100ull;
    float ground_z_lbm = 20.0f;
    float cell_size_m = 1.0f;
    int update_stride = 1;''',1)
text=pre+anchor+tail
needle='''                // p.pz is lattice z; urban flat ground is at z=20 (conf base_height).'''
assert text.count(needle)==1
text=text.replace(needle,'''                // Physical height above flat ground, using runtime base_height and actual lattice spacing.''')
needle='''                const float z_agl = std::max(0.0f,p.z - 20.0f);'''
assert text.count(needle)==1
text=text.replace(needle,'''                const float z_agl = std::max(0.0f, (p.z - cfg_.ground_z_lbm) * cfg_.cell_size_m);''')
needle='''        cfg.seed = vk_inlet_settings.seed;'''
assert text.count(needle)==1
text=text.replace(needle,needle+'''
        cfg.ground_z_lbm = units.x(z_si_offset);
        cfg.cell_size_m = 1.0f / units.x(1.0f);''')
# Export native, initialized flags for z=1.5 and z=2 m and their trilinear neighboring layers.
needle='''#endif
            emit_progress_stage("interface_interpolation",
                                "Interface interpolation",
                                "Profile boundary conditions completed",'''
assert text.count(needle)==1
export='''#endif
            {
                // VTK core origin is -base_height; export both interpolation layers.
                const float grid_m = 1.0f / units.x(1.0f);
                const int base_k = (int)std::lround(units.x(z_si_offset));
                const int low = base_k + (int)std::floor(1.5f/grid_m);
                const int high = base_k + (int)std::floor(2.0f/grid_m) + 1;
                if (low<0 || high>=(int)Nz || high<low) print_error("T2b flags layer range invalid");
                std::filesystem::create_directories(parent+"/RESULTS");
                std::ofstream ff(parent+"/RESULTS/native_flags_nearground_z"+std::to_string(low)+"_"+std::to_string(high)+".bin",std::ios::binary|std::ios::trunc);
                if (!ff) print_error("T2b flags cannot open");
                for(int zf=low;zf<=high;zf++) for(uint yf=0u;yf<Ny;yf++) for(uint xf=0u;xf<Nx;xf++) {
                    const uchar fl=lbm.flags[(ulong)xf+(ulong)Nx*((ulong)yf+(ulong)Ny*(ulong)zf)];
                    ff.write((const char*)&fl,1);
                }
                ff.flush();if (!ff) print_error("T2b flag export failed");
                println("| T2b native flags | z indices " + std::to_string(low) + ".." + std::to_string(high) + " |");
            }
            emit_progress_stage("interface_interpolation",
                                "Interface interpolation",
                                "Profile boundary conditions completed",'''
text=text.replace(needle,export)
setup.write_text(text)
defines=(src/'defines.hpp').read_text();assert defines.count('//#define CITY_STABILITY_MONITOR')==1
c=(r/'case/conf.luwpf').read_text()
for a,b in [('n_gpu = [1, 1, 1]','n_gpu = [4, 1, 1]'),('cell_size = 1.0','cell_size = 0.5'),('run_nstep = 31000','run_nstep = 62000'),('purge_avg = 20000','purge_avg = 40000'),('purge_avg_stride = 40','purge_avg_stride = 80')]:
    assert c.count(a)==1,(a,c.count(a));c=c.replace(a,b)
for frozen in ('si_z_cfd = [0.000000, 270.000000]','base_height = 20.0','z_limit = 250'): assert frozen in c
case=r/'case_4gpu';case.mkdir(exist_ok=False)
for rel in ('wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):
    (case/rel).parent.mkdir(exist_ok=True);shutil.copyfile(r/'case'/rel,case/rel)
(case/'conf.luwpf').write_text(c)
for p in (case/'conf.luwpf',case/'wind_bc/profile.dat',case/'proj_temp/CaseE_PF.stl',setup,src/'defines.hpp'):
    print('FROZEN',p.relative_to(r),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
print('GRID_EXPECTED 1000 1000 940; CORE_VTK 1000 1000 540; FLAGS indices 43..45 (physical 1.5..2.5m)',flush=True)
