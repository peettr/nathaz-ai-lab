#!/usr/bin/env python3
"""Analyze native C1/C2 ledger, verify SHA, render a lightweight SVG chart."""
import csv, hashlib, json, math, pathlib
R=pathlib.Path(__file__).resolve().parent
E=next(R.glob('session_*/evidence'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files={}
for side in E.glob('*.sha256'):
    data=E/side.name[:-7]
    assert data.is_file() and digest(data)==side.read_text().strip(),side
    files[data.name]=digest(data)
assert json.loads((E/'run.done').read_text())['verified_cases']==['c1','c2']
rate=5.4; dx=1.; dt=1/78; F=1.20843e-3; rho=1.; n=256*128*64; half=8975
f_lat=rho*F*dt*dt/dx
impulse=f_lat*n*half
summary={'input_sha256':files,'reference_drive_impulse_lattice':{'formula':'rho_lat * F_SI * dt_SI^2 / dx_SI * (256*128*64) * 8975','rho_lat':rho,'F_SI':F,'dt_SI':dt,'f_lat':f_lat,'fluid_cells':n,'half_turnover_steps':half,'impulse_lattice':impulse},'cases':{}}
series={}
for case in ('c1','c2'):
    with (E/(case+'_ledger.csv')).open() as f: rows=list(csv.DictReader(f))
    steps=[int(x['step']) for x in rows]
    assert steps==list(range(101))+list(range(110,1001,10)),steps
    px=[float(x['px_fluid_lattice']) for x in rows]
    m=[float(x['mass_fluid_lattice']) for x in rows]
    before=[float(x['px_before_update_fields']) for x in rows]
    assert all(math.isfinite(v) for v in px+m+before)
    r={'row_count':len(rows),'px_0':px[0],'px_1':px[1],'px_1000':px[-1],
       'mass_0':m[0],'mass_1':m[1],'mass_1000':m[-1],
       'jump_0_1':px[1]-px[0],'jump_0_1_rel':(px[1]-px[0])/px[0],
       'drift_1_1000':px[-1]-px[1], 'drift_1_1000_rel':(px[-1]-px[1])/px[1],
       'sampled_range_1_1000':max(px[1:])-min(px[1:]),
       'sampled_range_over_A7_impulse':(max(px[1:])-min(px[1:]))/impulse,
       'jump_over_A7_impulse':abs(px[1]-px[0])/impulse,
       'passes_if_start_step1':abs((px[-1]-px[1])/px[1])<=1e-5,
       'max_abs_update_fields_difference':max(abs(a-b) for a,b in zip(px,before)),
       'max_abs_mass_update_fields_difference':max(abs(float(x['mass_before_update_fields'])-y) for x,y in zip(rows,m)),
       'mass_range':max(m)-min(m), 'px_min_step':steps[px.index(min(px))], 'px_max_step_after1':steps[1+px[1:].index(max(px[1:]))]}
    summary['cases'][case]=r;series[case]=(steps,px,m)
# SVG, two panels, direct native records (step0 included, nonlinearity visible).
W,H=1050,600; x0,x1=80,1010
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<rect width="100%" height="100%" fill="white"/>','<style>text{font:14px sans-serif}.title{font:bold 19px sans-serif}</style>','<text class="title" x="65" y="30">T17 A1(b): native C1/C2 Px and mass (post-update_fields)</text>']
for idx,(field,top,bottom) in enumerate((('px',65,295),('mass',345,565))):
    vals=[v for _,px,m in series.values() for v in (px if field=='px' else m)]
    lo,hi=min(vals),max(vals);pad=max((hi-lo)*.08,0.001);lo-=pad;hi+=pad
    y=lambda v:bottom-(v-lo)/(hi-lo)*(bottom-top)
    parts+= [f'<line x1="{x0}" y1="{bottom}" x2="{x1}" y2="{bottom}" stroke="black"/>', f'<line x1="{x0}" y1="{top}" x2="{x0}" y2="{bottom}" stroke="black"/>',f'<text x="8" y="{top+15}">{field} (lattice)</text>', f'<text x="{x0}" y="{bottom+20}">0</text>',f'<text x="{x1-30}" y="{bottom+20}">1000 steps</text>',f'<text x="5" y="{top+35}">{hi:.5f}</text>',f'<text x="5" y="{bottom-8}">{lo:.5f}</text>']
    for case,color in (('c1','#1555cc'),('c2','#df6b10')):
        steps,px,m=series[case];values=px if field=='px' else m
        points=' '.join(f'{x0+(x1-x0)*s/1000:.2f},{y(v):.2f}' for s,v in zip(steps,values))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.6"/>')
parts += ['<text x="805" y="50" fill="#1555cc">C1 uniform</text>','<text x="925" y="50" fill="#df6b10">C2 perturbation</text>','</svg>']
(R/'PX_M.svg').write_text('\n'.join(parts)+'\n')
(R/'RESULT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':summary['cases'],'drive_impulse':impulse,'verified_files':len(files),'chart':'PX_M.svg'},ensure_ascii=False,indent=2))
