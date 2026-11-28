#!/usr/bin/env python3
"""Third-chain SPIN descriptive return levels; correlated paths, no gate/CI."""
import csv,json,pathlib,numpy as np,zipfile,collections
import postprocess_v3 as pp
R=pathlib.Path('/content/b2');O=R/'spin_products_v4';O.mkdir(exist_ok=True)
files=sorted((R/'spin_results_v4').glob('spin_*.npz'))
assert files
chunks=[np.load(p) for p in files];ids=np.concatenate([x['ids'] for x in chunks]);years=np.concatenate([x['years'] for x in chunks]);peaks=np.concatenate([x['peaks'] for x in chunks]);meta=json.loads((R/'spin_results_v4'/'complete.json').read_text())
assert len(ids)==len(set(ids))==meta['counts']['selected'] and years.max()<meta['sample_file_years']
Nyears=meta['sample_file_years'];Nstorm=meta['counts']['storm_raw'];sites=list(csv.DictReader((R/'sites.csv').open()));rows=[]
for j,st in enumerate(sites):
 row={'site':st['site'],'spin_v50_ms':pp.return_value(peaks[:,0,j],50,Nyears,Nstorm),'spin_v700_ms':pp.return_value(peaks[:,0,j],700,Nyears,Nstorm),'nonzero_storms':int(np.sum(peaks[:,0,j]>0)),'asce_v700_ms':st['asce_v700_ms']}
 rows.append(row)
with (O/'spin_return_levels.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
summary={'files_years':Nyears,'independent_neuralgcm_member_years':557,'storm_raw':Nstorm,'storm_selected':len(ids),'malformed_storms':meta['counts']['malformed'],'failed':meta['counts']['failed'],'v700_nonnull':sum(v['spin_v700_ms'] is not None for v in rows),'note':'FAST 10 intensity realizations share NeuralGCM paths; Pc/RMW borrowed from RAFT equations, no CI or gate.'}
(O/'spin_summary.json').open('x').write(json.dumps(summary,ensure_ascii=False,indent=2));print(summary)
