#!/usr/bin/env python3
"""Synthetic 360-tap fixtures, no production observations."""
import csv, tempfile
from pathlib import Path
from compare_r1_vs_s2 import evaluate
fields=['tap_id','zone']+[f'neg_{p}_{v}' for p in ('50','90') for v in ('LES','halfA_LES','halfB_LES')]
with tempfile.TemporaryDirectory() as td:
    paths=[Path(td)/f'{i}.csv' for i in range(3)]
    for case,path in enumerate(paths):
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for i in range(1,361):
                row={'tap_id':i,'zone':'side_separated' if i<=216 else 'windward'}
                for p in ('50','90'):
                    for v in ('LES','halfA_LES','halfB_LES'):
                        row[f'neg_{p}_{v}']=-1.-(.2 if case==1 else 0)
                if case==2 and i==3:row['neg_50_LES']=''
                w.writerow(row)
    for index,expected in [(0,'无影响'),(1,'有影响'),(2,'不判（数据闸门）')]:
        result=evaluate(paths[0],paths[index])
        assert result['verdict']==expected,result
        print(index,expected,result['metrics'])
