from pathlib import Path
import tarfile, shutil
base=Path(__file__).resolve().parent
stage=base/'precision_stage'
assert not stage.exists()
with tarfile.open(base/'luw_wp1_gate0_stage.tar.gz') as f:f.extractall(stage,filter='data')
for source in ('head','patched'):
 p=stage/source/'src/lbm.hpp';s=p.read_text();needle='public:\n';assert s.count(needle)>0
 # The first public section belongs to LBM_Domain.
 s=s.replace(needle,needle+'#ifdef WALL_GATE0\n Memory<fpxx>& gate0_fi() { return fi; }\n#endif\n',1);p.write_text(s)
fixture=(base/'gate0_fixture.hpp').read_text()
needle='            for(ulong i=0;i<N;i++) { const float v=lbm.rho[i];'
assert fixture.count(needle)==1
fixture=fixture.replace(needle,'''            auto& fi_raw=lbm.lbm_domain[0]->gate0_fi();
            fi_raw.add_host_buffer(); fi_raw.read_from_device();
            for(ulong i=0;i<(ulong)lbm.get_velocity_set()*N;i++) { const fpxx v=fi_raw[i]; out.write((const char*)&v,sizeof(v)); }
'''+needle,1)
(stage/'gate0_fixture.hpp').write_text(fixture)
with tarfile.open(base/'luw_wp1_precision.tar.gz','w:gz') as f:
 for name in ('head','patched','gate0_fixture.hpp'):f.add(stage/name,arcname=name)
print(base/'luw_wp1_precision.tar.gz')
