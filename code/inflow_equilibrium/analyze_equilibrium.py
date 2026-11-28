#!/usr/bin/env python3
"""Read-only reduction of archived 1–30 m mean-speed and resolved-k profiles."""
import csv, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=pathlib.Path(__file__).resolve().parent
sources=[('FG0A70','approach_full','profiles_full.csv'),('FG0A100','approach_full','profiles_full.csv'),('FG0z','approach_z0','profiles_z0.csv'),('FG0zA70','approach_z0','profiles_z0.csv'),('FGz2','approach_z0b','profiles_z0b.csv'),('FGz6','approach_z0b','profiles_z0b.csv')]
def trap(vals): return sum((a+b)/2 for a,b in zip(vals,vals[1:]))
rows=[]
for tag,d,name in sources:
    data={(int(float(r['x_m'])),int(float(r['z_m']))):r for r in csv.DictReader(open(ROOT/d/name,newline='')) if r['tag']==tag}
    assert len(data)==120 and all((x,z) in data for x in (5,42,120,200) for z in range(1,31))
    for x in (5,42,120,200):
        for z in (2,5,10,15,20,30):
            r=data[x,z]; base=data[5,z]
            rows.append(dict(tag=tag,x_m=x,z_m=z,U_mps=r['U_mps'],U_change_from_x5_pct=(float(r['U_mps'])/float(base['U_mps'])-1)*100,k_m2s2=r['k_m2s2'],k_change_from_x5_pct=(float(r['k_m2s2'])/float(base['k_m2s2'])-1)*100))
        for low,high in ((1,5),(5,15),(15,30),(1,30)):
            values=[float(data[x,z]['U_mps']) for z in range(low,high+1)]
            bvalues=[float(data[5,z]['U_mps']) for z in range(low,high+1)]
            kvals=[float(data[x,z]['k_m2s2']) for z in range(low,high+1)]
            kb=[float(data[5,z]['k_m2s2']) for z in range(low,high+1)]
            rows.append(dict(tag=tag,x_m=x,z_m=f'{low}-{high} integral',U_mps=trap(values),U_change_from_x5_pct=(trap(values)/trap(bvalues)-1)*100,k_m2s2=trap(kvals)/(high-low),k_change_from_x5_pct=(trap(kvals)/trap(kb)-1)*100))
with open(DEST/'profile_reductions.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for tag,_,_ in sources:
 print(tag)
 for r in rows:
  if r['tag']==tag and r['x_m']==200:print(r['z_m'],f"dU={r['U_change_from_x5_pct']:+.2f}%",f"dk={r['k_change_from_x5_pct']:+.2f}%")
