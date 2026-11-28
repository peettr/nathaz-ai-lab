#!/usr/bin/env python3
"""Create a full-height fine-grid B2u deck in an unused TACC root."""
import hashlib,pathlib,shutil,sys,tarfile
r=pathlib.Path(sys.argv[1]).resolve()
with tarfile.open(r/'B2u_inputs.tar.gz') as tf:
 for m in tf.getmembers():
  p=(r/m.name).resolve()
  if not p.is_relative_to(r) or m.issym() or m.islnk():raise RuntimeError(m.name)
 tf.extractall(r,filter='data')
src=r/'FluidX3D/src';defines=(src/'defines.hpp').read_text()
assert defines.count('//#define CITY_STABILITY_MONITOR')==1
# Keep the 500x500 monitor disabled; add only a read-only near-ground flag export.
src_setup=src/'setup.cpp';text=src_setup.read_text()
needle='''#endif
            emit_progress_stage("interface_interpolation",
                                "Interface interpolation",
                                "Profile boundary conditions completed",'''
assert text.count(needle)==1
export='''#endif
            { // T2 read-only native flags, first 24 levels at 0.5 m, x fastest.
                if (Nx!=1000u || Ny!=1000u || Nz!=940u) print_error("T2 full-grid dimensions mismatch");
                std::filesystem::create_directories(parent+"/RESULTS");
                std::ofstream ff(parent+"/RESULTS/native_flags_z0_23.bin",std::ios::binary|std::ios::trunc);
                if (!ff) print_error("T2 flags cannot open");
                for(uint zf=0u;zf<24u;zf++) for(uint yf=0u;yf<Ny;yf++) for(uint xf=0u;xf<Nx;xf++) {
                    const uchar fl=lbm.flags[(ulong)xf+(ulong)Nx*((ulong)yf+(ulong)Ny*(ulong)zf)];
                    ff.write((const char*)&fl,1);
                }
                ff.flush();if (!ff) print_error("T2 flag export failed");
            }
            emit_progress_stage("interface_interpolation",
                                "Interface interpolation",
                                "Profile boundary conditions completed",'''
src_setup.write_text(text.replace(needle,export))
c=(r/'case/conf.luwpf').read_text()
for old,new in [('n_gpu = [1, 1, 1]','n_gpu = [4, 1, 1]'),('cell_size = 1.0','cell_size = 0.5'),('run_nstep = 31000','run_nstep = 62000'),('purge_avg = 20000','purge_avg = 40000'),('purge_avg_stride = 40','purge_avg_stride = 80')]:
 assert c.count(old)==1,(old,c.count(old));c=c.replace(old,new)
for frozen in ('si_z_cfd = [0.000000, 270.000000]','base_height = 20.0','z_limit = 250'):
 assert frozen in c,frozen
case=r/'case_4gpu';case.mkdir(exist_ok=False)
(case/'wind_bc').mkdir();(case/'proj_temp').mkdir()
for rel in ('wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):shutil.copyfile(r/'case'/rel,case/rel)
(case/'conf.luwpf').write_text(c)
for p in (case/'conf.luwpf',case/'wind_bc/profile.dat',case/'proj_temp/CaseE_PF.stl',src/'setup.cpp',src/'defines.hpp'):
 print('FROZEN',p.relative_to(r),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
print('GRID_EXPECTED 1000 1000 940; CORE_VTK 1000 1000 540; PHYS_BOX_M 500 500 470',flush=True)
