#!/usr/bin/env python3
"""Stage new immutable BG v4 controller roots from verified v3 inputs; no solver locally."""
from pathlib import Path
import hashlib,json,shutil,py_compile,re,zipfile
base=Path(__file__).resolve().parent
for kind in ('BG_1H','BG_3H'):
 old=base/f'{kind}_v3_20261115_1001';new=base/f'{kind}_v4_20261115_1050'
 new.mkdir(exist_ok=False)
 files=('verify_source.py','verify_diagnostic_upload.py','v3_alignment.py','remote_BG.py','launch.py','gpu_probe.py','diagnostic_extract.py','controller.py','check.py','bg_stage.tar.gz')
 for name in files:shutil.copyfile(old/name,new/name)
 for name in files:
  if not name.endswith('.py'):continue
  p=new/name;s=p.read_text()
  s=s.replace('v3-20261115_1001','v4-20261115_1050')
  s=s.replace('v3_alignment','v4_alignment')
  if name=='controller.py':
   s=s.replace('deadline=start+1.96/rate*3600','deadline=start+1.96/rate*3600').replace('deadline=start+2.90/rate*3600','deadline=start+1.96/rate*3600')
   s=s.replace("('A100','G4','L4','H100')","('A100','G4','L4')")
   s=s.replace("'BG_1H_result.zip'","'BG_1H_v4_result.zip'").replace("'BG_3H_result.zip'","'BG_3H_v4_result.zip'")
   s=s.replace("'--no-remind','--detach'","'--no-remind','--detach'")
   s=s.replace("'--max-hours','2'","'--max-hours','1'")
   s=s.replace("'--final-pull',REMOTE+'/result.zip:'+str(D)","'--final-pull',REMOTE+'/result.zip:'+str(D/'final_pull')")
   s=s.replace("assert json.loads(z.read('solver_exit.json'))['exit']==0","assert json.loads(z.read('solver_exit.json'))['exit']==0\n    assert pts['selected_offset_xy_m']==[2,2] and len(pts['offset_0_2_rows'])==len(pts['rows'])")
   s=s.replace("with owner.open('x') as f:f.write(","with owner.open('x') as f:f.write(")
  if name=='remote_BG.py':
   s=s.replace("assert sha('/content/v4_alignment.py')=='0c87fab2d94e504634c42b4bb7d3200fd878a1a1bec5ebe7c24ef62dedd2b31c'", "assert sha('/content/v4_alignment.py')==ALIGN_SHA")
   s=s.replace("assert remaining>=350", "assert remaining>=350")
   s=s.replace("from v4_alignment import register","from v4_alignment import register")
  if name=='v3_alignment.py':
   s=s.replace("# Ties prefer smaller shift, and uncertainty is preserved in the evidence.\n        best=max(scores,key=lambda q:(q['iou'],-sum(q['offset_xy_m'])))", """# Frozen tie-break: each axis follows the positive native-solid centroid displacement.
        maxima=[q for q in scores if q['iou']==max(s['iou'] for s in scores)]
        assert [2,2] in [q['offset_xy_m'] for q in maxima],maxima
        # The nine native 2 m components occupy a 3x3 group; compare to STL component centres.
        expected_groups=components(level_data[2.][0]);assert len(expected_groups)==9
        k=level_data[2.][1]; evidence_centroids=[]
        for group in expected_groups:
            cx=sum(o[0]+i*sp[0] for i,j in group)/len(group)
            cy=sum(o[1]+j*sp[1] for i,j in group)/len(group)
            ii=[a for a,b in group];jj=[b for a,b in group]
            native={(o[0]+i*sp[0],o[1]+j*sp[1]) for j in range(max(0,min(jj)-2),min(dims[1],max(jj)+3)) for i in range(max(0,min(ii)-2),min(dims[0],max(ii)+3)) if not mask(i,j,k)}
            assert native, (cx,cy)
            nx=sum(x for x,y in native)/len(native);ny=sum(y for x,y in native)/len(native)
            evidence_centroids.append({'stl_xy_m':[cx,cy],'native_xy_m':[nx,ny],'delta_xy_m':[nx-cx,ny-cy]})
        assert all(q['delta_xy_m'][0]>0 and q['delta_xy_m'][1]>0 for q in evidence_centroids),evidence_centroids
        best=next(q for q in maxima if q['offset_xy_m']==[2,2])""")
   s=s.replace("'per_building':per_building,","'per_building':per_building,'centroid_tiebreak_evidence':evidence_centroids,'tie_rule':'IoU maximum tie: each axis independently follows native-solid centroid displacement, before observing velocity errors',")
   s=s.replace("rows=[];zero=[]","rows=[];zero=[];mid=[]")
   s=s.replace("zero.append({**info,**one(0,0)})","zero.append({**info,**one(0,0)});mid.append({**info,**one(0,2)})")
   s=s.replace("'zero_offset_rows':zero,","'zero_offset_rows':zero,'offset_0_2_rows':mid,")
   (new/'v4_alignment.py').write_text(s);p.unlink();continue
  p.write_text(s)
 # Fully checked remote hash goes into immutable worker before VM creation.
 alignsha=hashlib.sha256((new/'v4_alignment.py').read_bytes()).hexdigest()
 p=new/'remote_BG.py';p.write_text(p.read_text().replace('ALIGN_SHA',repr(alignsha)))
 (new/'final_pull').mkdir()
 for name in ('controller.py','launch.py','check.py','remote_BG.py','v4_alignment.py','diagnostic_extract.py'):
  py_compile.compile(str(new/name),doraise=True)
 # Guard frozen input archive and each point count before paying for VM.
 with zipfile.ZipFile(old/f'{kind}_result.zip') as z:
  prev=json.loads(z.read('pointvalues.json'))
 assert len(prev['rows'])== (195 if kind=='BG_1H' else 200)
 assert hashlib.sha256((old/'bg_stage.tar.gz').read_bytes()).hexdigest()==hashlib.sha256((new/'bg_stage.tar.gz').read_bytes()).hexdigest()
 assert 'v3-20261115_1001' not in ''.join((new/name).read_text() for name in ('controller.py','launch.py','check.py','remote_BG.py'))
 assert 'v3_alignment' not in ''.join((new/name).read_text() for name in ('controller.py','remote_BG.py'))
 assert "deadline=start+1.96/rate*3600" in (new/'controller.py').read_text()
 print(kind,'PREFLIGHT_OK',new,'alignment_sha256',alignsha)
