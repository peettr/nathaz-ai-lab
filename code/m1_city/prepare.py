from pathlib import Path
import tarfile, shutil, hashlib
R=Path(__file__).resolve().parent
P=R.parent/'m1_run'
for name,source in [('city',P/'city_m1.tar.gz'),('reg',P/'reg_m1.tar.gz')]:
 d=R/name;d.mkdir(exist_ok=True)
 with tarfile.open(source) as t:t.extractall(d,filter='data')
city=R/'city/stage/FluidX3D/src'
k=city/'kernel.cpp';s=k.read_text()
anchor=')+"#endif"+R(\n)+"#ifdef FORCE_FIELD"+R('
assert s.count(anchor)==1
addition=''' )+R(kernel void ibb_f0_minimum(const global fpxx* fi, const global uchar* flags, global uint* min_ordered) {
 const uint n=get_global_id(0);
 if(n>=def_N || (flags[n]&TYPE_BO)==TYPE_S) return;
 const float v=load(fi,index_f(n,0u));
 const uint b=as_uint(v);
 const uint ordered=(b&0x80000000u)?~b:(b^0x80000000u);
 atomic_min((volatile global uint*)min_ordered, ordered);
} // ibb_f0_minimum()
'''
s=s.replace(anchor,addition+anchor,1);k.write_text(s)
setup=city/'setup.cpp';s=setup.read_text()
anchor='        auto* bis_dom=lbm.lbm_domain[0];'
assert s.count(anchor)==1
# extra f0 min reduction, separate from large host scan
s=s.replace(anchor,'''        std::ofstream f0_out(parent+"/RESULTS/f0_minimum.csv",std::ios::out|std::ios::trunc);
        f0_out << "step,min_f0\\n" << std::flush;
'''+anchor,1)
anchor='        auto monitor_city = [&]() {'
assert s.count(anchor)==1
s=s.replace(anchor,'''        Memory<uint> f0_ordered(bis_device,1u);
        Kernel f0_kernel(bis_device,mon_n,"ibb_f0_minimum",bis_dom->fi,bis_dom->flags,f0_ordered);
        auto sample_f0 = [&]() {
            f0_ordered[0]=0xffffffffu;f0_ordered.write_to_device();
            f0_kernel.enqueue_run();f0_ordered.read_from_device();
            const uint ordered=f0_ordered[0];
            const uint bits=(ordered&0x80000000u)?(ordered^0x80000000u):~ordered;
            float v;std::memcpy(&v,&bits,sizeof(v));
            f0_out<<lbm.get_t()<<','<<std::setprecision(12)<<v<<'\\n'<<std::flush;
        };
'''+anchor,1)
anchor='            if(lbm.get_t()%200ull==0ull) { bisect_check(); monitor_city(); }'
assert s.count(anchor)==2
s=s.replace(anchor,'            if(lbm.get_t()%50ull==0ull) sample_f0();\n'+anchor)
setup.write_text(s)
# D80 instrument also deserves f0 minimum: DFG fixture not the city monitor; city requirement only.
for tag,d in [('city',R/'city'),('reg',R/'reg')]:
 out=R/(tag+'.tar.gz')
 with tarfile.open(out,'w:gz') as t:
  for p in d.iterdir():t.add(p,arcname=p.name)
 print(tag,out.stat().st_size,hashlib.sha256(out.read_bytes()).hexdigest())
