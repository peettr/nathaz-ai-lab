#!/usr/bin/env python3
"""Read-only reduction of hash-verified longspin window JSON; no solver rerun."""
import csv, hashlib, json, math
from pathlib import Path
R=Path(__file__).resolve().parent
E=R/'session_luw-t17-a100-df21176d/evidence'
O=R/'terminal_analysis_20261120'
O.mkdir(exist_ok=True)
rows=[]
for i in range(1,16):
 p=E/f'window_{i:02d}.json'
 assert hashlib.sha256(p.read_bytes()).hexdigest()==(E/(p.name+'.sha256')).read_text().split()[0]
 v=json.loads(p.read_text());assert v['window']==i and v['T_range']==[2*(i-1),2*i]
 assert all(math.isfinite(x) for x in v.values() if isinstance(x,float))
 rows.append(v)
for n in ['solver.log','timing.csv','producer.done','handoff.json','run.failed','native_compile.log']:
 p=E/n;assert hashlib.sha256(p.read_bytes()).hexdigest()==(E/(n+'.sha256')).read_text().split()[0]
assert (E/'producer.done').read_text().strip()=='538500'
manifest=json.loads((E/'handoff.json').read_text())['sha256']
assert all((E/n).exists() and hashlib.sha256((E/n).read_bytes()).hexdigest()==h for n,h in manifest.items())
assert set(manifest)=={'native_compile.log','solver.log','timing.csv','producer.done'}|{f'window_{i:02d}.json' for i in range(1,16)}
cols=['window','T_start','T_end','V1_ratio','R_uu_x_half','R_uu_y_half','Px_begin','Px_end','Px_mean','k_res_z9p5','k_res_over_ustar_sq','e_2p5','S2b_rms','frames']
with (O/'WINDOWS.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(cols)
 for v in rows:w.writerow([v['window'],*v['T_range'],*(v[c] for c in cols[3:])])
pass_v1=[.95<=v['V1_ratio']<=1.05 for v in rows]
pass_v3=[abs(v['R_uu_x_half'])<=.1 and abs(v['R_uu_y_half'])<=.1 for v in rows]
def sustained(g):
 return next((rows[i]['T_range'][0] for i in range(len(g)) if all(g[i:])),None)
summary={'windows':15,'last_step':rows[-1]['step_range'][-1], 'V1_sustained_start_T':sustained(pass_v1), 'V3_sustained_start_T':sustained(pass_v3), 'V1_pass_by_window':pass_v1,'V3_pass_by_window':pass_v3,'curve_last_two':[{k:v for k,v in r.items() if k in ('window','T_range','correlation_curve')} for r in rows[-2:]],'result_status':'solver completed 30T; host-verified 15 windows; worker run.failed due ACK deadline; no run.done'}
(O/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with (O/'CORRELATION.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(['window','T_start','T_end','direction','shift_m','R_uu','multiple_of_32m'])
 for v in rows[-2:]:
  for direction,curve in v['correlation_curve'].items():
   for shift,val in curve.items():w.writerow([v['window'],*v['T_range'],direction,int(shift),val,int(shift)>0 and int(shift)%32==0])
# Self-contained SVG plotting from archived values; no graphics dependency.
def svg(path,series,title,ylabel):
 width,height=900,380; left,right,top,bottom=75,25,40,55
 vals=[y for _,pairs in series for _,y in pairs];lo=min(vals);hi=max(vals)
 if hi==lo:hi=lo+1
 pad=(hi-lo)*.08;lo-=pad;hi+=pad
 xmax=max(x for _,pairs in series for x,_ in pairs)
 def X(x):return left+(width-left-right)*x/xmax
 def Y(y):return top+(height-top-bottom)*(hi-y)/(hi-lo)
 colors=['#1453a1','#ca4828','#22834d','#9646a7','#d49216','#444444']
 b=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',f'<rect width="{width}" height="{height}" fill="white"/>',f'<text x="{left}" y="24" font-size="17">{title}</text>',f'<path d="M {left} {top} V {height-bottom} H {width-right}" fill="none" stroke="black"/>']
 for j in range(5):
  y=lo+(hi-lo)*j/4;b.append(f'<text x="4" y="{Y(y)+4:.1f}" font-size="12">{y:.3g}</text>')
 for j in range(6):
  x=xmax*j/5;b.append(f'<text x="{X(x)-8:.1f}" y="{height-bottom+18}" font-size="12">{x:g}</text>')
 for q,(name,pairs) in enumerate(series):
  pts=' '.join(f'{X(x):.2f},{Y(y):.2f}' for x,y in pairs)
  b.append(f'<polyline points="{pts}" fill="none" stroke="{colors[q]}" stroke-width="2"/>')
  b.append(f'<text x="{left+q*145}" y="{height-10}" fill="{colors[q]}" font-size="12">{name}</text>')
 b.append(f'<text x="{width-85}" y="{height-bottom+33}" font-size="12">{ylabel}</text></svg>')
 path.write_text('\n'.join(b)+'\n')
svg(O/'WINDOW_TRENDS.svg',[(k,[(v['T_range'][1],v[key]) for v in rows]) for k,key in [('V1','V1_ratio'),('Rx','R_uu_x_half'),('Ry','R_uu_y_half'),('k/u*²','k_res_over_ustar_sq'),('e2.5','e_2p5'),('S2b','S2b_rms')]],'T17 30T windows (descriptive)','T end')
svg(O/'PX.svg',[('Px begin',[(v['T_range'][1],v['Px_begin']) for v in rows]),('Px end',[(v['T_range'][1],v['Px_end']) for v in rows])],'Px in 2T windows','T end')
series=[]
for v in rows[-2:]:
 for direction in ['x_m','y_m']:
  series.append((f"{v['T_range'][0]}-{v['T_range'][1]}T {direction[0]}",[(int(x),y) for x,y in v['correlation_curve'][direction].items()]))
svg(O/'CORRELATION.svg',series,'R_uu last two windows; 32m multiples in CSV','shift m')
print(json.dumps({'summary':{k:v for k,v in summary.items() if k not in ('curve_last_two','V1_pass_by_window','V3_pass_by_window')},'V1':[round(v['V1_ratio'],6) for v in rows],'Rx':[round(v['R_uu_x_half'],6) for v in rows],'Ry':[round(v['R_uu_y_half'],6) for v in rows],'output':str(O)},ensure_ascii=False))
