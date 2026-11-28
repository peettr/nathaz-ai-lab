#!/usr/bin/env python3
import csv, json, re, sys
from pathlib import Path
old,new=map(Path,sys.argv[1:3])
def parse(path):
    text=path.read_text(); pairs=re.findall(r'^Time = ([^\n]+)[\s\S]*?^ExecutionTime = ([0-9.]+) s  ClockTime = ([0-9.]+) s',text,re.M)
    assert len(pairs)==5 and '\nEnd\n' in text,(path,len(pairs))
    return [(t,float(e),float(c)) for t,e,c in pairs]
a,b=parse(old/'log.dump'),parse(new/'log.control')
rows=[]; prior_a=prior_b=0.
for i,((ta,ea,ca),(tb,eb,cb)) in enumerate(zip(a,b),1):
    assert ta==tb,(ta,tb)
    da=ca-prior_a; db=cb-prior_b
    assert db>0 and da>0,(da,db)
    rows.append(dict(source='R25.2 S2-derived OpenFOAM10 t=0 paired five-step serial run',step=i,time=ta,
                     dump_clock_increment_s=da,control_clock_increment_s=db,export_increment_s=da-db,
                     export_to_control_ratio=da/db,extra_to_control_ratio=(da-db)/db,
                     dump_execution_cumulative_s=ea,control_execution_cumulative_s=eb))
    prior_a,prior_b=ca,cb
with (new/'q2_overhead.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print(json.dumps(rows,indent=2))
