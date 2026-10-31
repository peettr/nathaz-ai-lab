from pathlib import Path
import shutil,tarfile
R=Path(__file__).parent
for n in ['M1','M2']:
 p=R/n/'FluidX3D/src/setup.cpp';s=p.read_text()
 # Avoid needless 50-step monitor and per-step bisect; mass comparisons sampled every 200 steps.
 a='            bisect_check();\n            if(lbm.get_t()%50ull==0ull) monitor_city();'
 assert s.count(a)==2
 s=s.replace(a,'            if(lbm.get_t()%200ull==0ull) { bisect_check(); monitor_city(); }')
 # Do not add another output to preexisting stage. Build fresh fast tree.
 dst=R/(n+'fast');assert not dst.exists()
 shutil.copytree(R/n,dst)
 (dst/'FluidX3D/src/setup.cpp').write_text(s)
 with tarfile.open(R/(n+'fast.tar.gz'),'w:gz') as f:f.add(dst,arcname='stage')
 print(n,'prepared')
