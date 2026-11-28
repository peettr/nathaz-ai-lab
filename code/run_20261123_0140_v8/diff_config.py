from pathlib import Path
import difflib,hashlib,json
R=Path(__file__).resolve().parent
BASE=R.parents[2]/'R21.4a_T17_periodic_ABL/big6v3_periodic_t15_k2_20261121_103455/dry_content_t15_v3/t17b/pack_stage/periodic_t15_k2/src'
for name in ('kernel.cpp','lbm.cpp','lbm.hpp','t17_b_native.inc','defines.hpp'):
 a=(BASE/name).read_text().splitlines(True);b=(R/'pack_stage/B0/src'/name).read_text().splitlines(True)
 (R/('BASE_'+name+'.diff')).write_text(''.join(difflib.unified_diff(a,b,fromfile='frozen/'+name,tofile='T18-unified/'+name)))
manifest=json.loads((R/'t17b_manifest.json').read_text());seals=json.loads((R/'PREFLIGHT.ok').read_text())
(R/'CONFIG_SHA256.json').write_text(json.dumps({'archive_sha256':seals['t17b_stage.tar.gz'],'common_kernel_sha256':manifest['variants']['B0']['kernel.cpp'],'defines_sha256':{v:h['defines.hpp'] for v,h in manifest['variants'].items()},'worker_sha256':seals['worker_native.py'],'controller_sha256':seals['controller_t18.py'],'assert_T18_sha256':hashlib.sha256((R/'assert_T18.py').read_bytes()).hexdigest(),'macro_off_evidence':str(R.parent/'run_20261123_0136_v7/gate/macro_off.json')},indent=2)+'\n')
print('DIFF_AND_CONFIG_OK')
