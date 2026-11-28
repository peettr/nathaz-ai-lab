#!/usr/bin/env python3
"""Stage a private B2u deck, modifying diagnostics only; fail closed."""
import hashlib, pathlib, sys, tarfile, shutil
r=pathlib.Path(sys.argv[1]).resolve()
with tarfile.open(r/'B2u_inputs.tar.gz') as tf:
    for m in tf.getmembers():
        p=(r/m.name).resolve()
        if not p.is_relative_to(r) or m.issym() or m.islnk(): raise RuntimeError(m.name)
    tf.extractall(r, filter='data')
src=r/'FluidX3D/src'; p=src/'setup.cpp'; s=p.read_text(); d=src/'defines.hpp'; text=d.read_text()
assert text.count('//#define CITY_STABILITY_MONITOR')==1
# Keep the full baseline monitor schema and cadence. Use global Memory_Container indexing
# (same global indexing as the B2u volume-mean accumulator) across four domains.
a=s.index('        auto monitor_city = [&]() {'); b=s.index('        };\n#endif',a)
block=s[a:b]
for old,new,n in [
 ('            if(lbm.get_D()!=1u) print_error("city monitor requires one subdomain");\n','',1),
 ('            auto* dom=lbm.lbm_domain[0];\n','',1),
 ('dom->flags.x[','lbm.flags[',0),
 ('dom->rho.x[','lbm.rho[',0),
 ('dom->u.x[','lbm.u.x[',0),
 ('dom->u.y[','lbm.u.y[',0),
 ('dom->u.z[','lbm.u.z[',0)]:
    assert (block.count(old)==n if n else block.count(old)>0),(old,block.count(old))
    block=block.replace(old,new)
s=s[:a]+block+s[b:]
# The old one-domain native-flags export is diagnostic only; retain byte layout.
old='if (lbm.get_D()!=1u || Nx!=500u || Ny!=500u || Nz<22u) print_error("stage3 flag export grid mismatch");'
assert s.count(old)==1
s=s.replace(old,'if (Nx!=500u || Ny!=500u || Nz<22u) print_error("stage3 flag export grid mismatch");')
assert s.count('const uchar fl=lbm.flags[')==1
p.write_text(s);d.write_text(text.replace('//#define CITY_STABILITY_MONITOR','#define CITY_STABILITY_MONITOR'))
c0=(r/'case/conf.luwpf').read_text();assert c0.count('n_gpu = [1, 1, 1]')==1
c=c0.replace('n_gpu = [1, 1, 1]','n_gpu = [4, 1, 1]')
case=r/'case_4gpu';case.mkdir(exist_ok=False)
(case/'wind_bc').mkdir();(case/'proj_temp').mkdir()
for rel in ('wind_bc/profile.dat','proj_temp/CaseE_PF.stl'):shutil.copyfile(r/'case'/rel,case/rel)
(case/'conf.luwpf').write_text(c)
for f in (p,d,case/'conf.luwpf',case/'wind_bc/profile.dat',case/'proj_temp/CaseE_PF.stl'):
    print('FROZEN',str(f.relative_to(r)),hashlib.sha256(f.read_bytes()).hexdigest(),flush=True)
