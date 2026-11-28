import csv, json, math, hashlib
from pathlib import Path
r=Path(__file__).resolve().parent
e=r/'session_luw-t17-a1b-f8299a6c/evidence'
with (e/'d1_ledger.csv').open() as f: led={int(x['step']):x for x in csv.DictReader(f)}
with (e/'d1_layers.csv').open() as f: rows=list(csv.DictReader(f))
layer={(int(x['step']),int(x['z'])):float(x['px_lattice']) for x in rows}
steps=sorted(led); zs=sorted({k[1] for k in layer})
assert len(zs)==64 and zs==list(range(1,65))
assert steps[0]==0 and steps[-1]==1000
for s in steps:
 assert all((s,z) in layer for z in zs)
 assert abs(sum(layer[s,z] for z in zs)-float(led[s]['px_fluid_lattice']))<1e-4 # independent sum order changes final rounding
base=lambda s:float(led[s]['px_fluid_lattice'])
delta={z:layer[1000,z]-layer[1,z] for z in zs}
ordered=sorted(delta.items(),key=lambda x:abs(x[1]),reverse=True)
interesting=[0,1,2,10,50,100,200,500,1000]
summary={
 'rows_ledger':len(steps),'rows_layers':len(rows),'steps':steps,'layer_z':zs,
 'px':{str(s):base(s) for s in interesting},
 'mass':{str(s):float(led[s]['mass_fluid_lattice']) for s in interesting},
 'jump_0_1':base(1)-base(0),'jump_0_1_relative':(base(1)-base(0))/base(0),
 'delta_1_1000':base(1000)-base(1),'relative_1_1000':(base(1000)-base(1))/base(1),
 'layer_delta_1_1000':{str(z):delta[z] for z in zs},
 'largest_layers':ordered[:12],
 'bottom_top':{str(z):{str(s):layer[s,z] for s in interesting} for z in [1,2,32,63,64]},
 'per_step_top_bottom':{str(z):[{'step':s,'px':layer[s,z],'delta_from_previous':layer[s,z]-layer[steps[i-1],z] if i else None} for i,s in enumerate(steps[:101])] for z in [1,64]},
 'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in e.iterdir() if p.is_file() and not p.name.endswith('.sha256')},
}
assert all(summary['source_sha256'][p.name]==(e/(p.name+'.sha256')).read_text().strip() for p in e.iterdir() if p.is_file() and not p.name.endswith('.sha256'))
(r/'D1_ANALYSIS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with (r/'D1_LAYER_DELTA.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['z','px_step1','px_step1000','delta_1_1000']);w.writerows((z,layer[1,z],layer[1000,z],delta[z]) for z in zs)
# Pure SVG line and bar plots, no external plotting dependencies.
def svg_line(values,title,out):
 W,H=900,390; lo=min(y for _,y in values);hi=max(y for _,y in values); hi=hi if hi>lo else lo+1
 x0,x1=70,W-20;y0,y1=35,H-60
 pts=' '.join(f'{x0+(x/1000)*(x1-x0):.2f},{y1-(y-lo)/(hi-lo)*(y1-y0):.2f}' for x,y in values)
 out.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="white"/><text x="70" y="22" font-size="18">{title}</text><path d="M{x0} {y0}V{y1}H{x1}" fill="none" stroke="black"/><polyline points="{pts}" fill="none" stroke="#155da5" stroke-width="2"/><text x="70" y="{H-18}" font-size="13">step 0–1000; y range {lo:.9g} to {hi:.9g} (lattice Px)</text></svg>')
svg_line([(s,base(s)) for s in steps],'A13-repaired D1: whole-domain Px',r/'D1_PX.svg')
svg_line([(s,layer[s,64]) for s in steps],'A13-repaired D1: top layer z=64 Px',r/'D1_TOP_PX.svg')
lo=min(delta.values());hi=max(delta.values()); span=max(abs(lo),abs(hi),1e-9)
lines=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="450"><rect width="100%" height="100%" fill="white"/><text x="70" y="22" font-size="18">D1 layer ΔPx (step 1→1000)</text><path d="M70 210H880" stroke="black"/>']
for z in zs:
 x=75+(z-1)*12.3;y=210-175*delta[z]/span
 lines.append(f'<line x1="{x:.1f}" y1="210" x2="{x:.1f}" y2="{y:.1f}" stroke="#155da5" stroke-width="5"/>')
lines.append(f'<text x="70" y="425" font-size="13">layer z=1..64; Δ range {lo:.9g} to {hi:.9g} lattice Px</text></svg>')
(r/'D1_LAYER_DELTA.svg').write_text(''.join(lines))
print(json.dumps({k:summary[k] for k in ('rows_ledger','rows_layers','px','jump_0_1','jump_0_1_relative','delta_1_1000','relative_1_1000','largest_layers','bottom_top')},ensure_ascii=False,indent=2))
