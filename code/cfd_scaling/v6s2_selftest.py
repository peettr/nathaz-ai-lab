"""Small synthetic interface tests, NOT UrbanTALES scores."""
import json
from pathlib import Path
import numpy as np
from v6s2_baselines import B0, B1, B2, score_cases
from v6s2_analyze import power_fit

root = Path(__file__).resolve().parent
manifest = json.loads((root/'v6_nested_subsets.json').read_text())
for seed, rows in manifest['seeds'].items():
    assert [rows[k]['actual_groups'] for k in ('50','100','200','all')] == sorted(rows[k]['actual_groups'] for k in ('50','100','200','all'))
    assert set(rows['50']['cases']) <= set(rows['100']['cases']) <= set(rows['200']['cases']) <= set(rows['all']['cases'])
    assert len(rows['all']['cases']) == 371

def case(name, offset):
    grid = np.arange(16,dtype=float).reshape(4,4)
    return dict(name=name, mask=np.ones((4,4),bool),target=grid+offset,
                height=grid,sdf=grid,upwind_height=grid+1,
                upwind_distance=grid+2,direction_degrees=45)
train=[case('train',1)]
val=[case('val',2)]
test=[case('test',3)]
for method in (B0().fit(train), B1().fit(train), B2().fit(train,val)):
    scored=score_cases(method.predict,test)
    assert scored['cases'][0]['case']=='test' and np.isfinite(scored['pooled_rmse'])
assert power_fit([50,100,200,371],[4,3,2.5,2.2])['b']>0
print('PASS: manifest nesting, three synthetic baseline fits, scoring, positive power fit')
