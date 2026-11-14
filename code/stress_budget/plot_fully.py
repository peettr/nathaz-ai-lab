from pathlib import Path
import csv,html
b=Path(__file__).resolve().parent
rows=list(csv.DictReader((b/'fully_stress_profile.csv').open()));W,H=760,630
import json; wall={int(k):v["actual_tau"] for k,v in json.loads((b/"fully_stress_summary.json").read_text()).items()}; colors={200:'#1769aa',300:'#e78b11',400:'#21945c'}
x0,y0,x1,y1=100,540,640,65
px=lambda v:x0+(v/.08)*(x1-x0)
py=lambda z:y0-z/30*(y0-y1)
out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<rect width="100%" height="100%" fill="white"/>','<text x="100" y="30" font-size="20">FP32 near-ground stress (20,000-step mean)</text>']
for v in (0,.02,.04,.06,.08):
 out += [f'<line x1="{px(v)}" y1="{y0}" x2="{px(v)}" y2="{y1}" stroke="#ddd"/>',f'<text x="{px(v)-10}" y="{y0+23}" font-size="13">{v:.2f}</text>']
for z in (0,5,10,15,20,25,30):
 out += [f'<line x1="{x0}" y1="{py(z)}" x2="{x1}" y2="{py(z)}" stroke="#ddd"/>',f'<text x="{x0-35}" y="{py(z)+4}" font-size="13">{z}</text>']
for x in (200,300,400):
 q=sorted((r for r in rows if int(r['x'])==x),key=lambda r:int(r['z']))
 coords=' '.join(f"{px(float(r['total'])):.1f},{py(int(r['z'])):.1f}" for r in q)
 out.append(f'<polyline fill="none" stroke="{colors[x]}" stroke-width="2.4" points="{coords}"/>')
 out.append(f'<line x1="{px(wall[x]):.1f}" y1="{py(1):.1f}" x2="{px(wall[x]):.1f}" y2="{py(5):.1f}" stroke="{colors[x]}" stroke-dasharray="5 4"/>')
out += [f'<line x1="{px(.2418545**2)}" y1="{y0}" x2="{px(.2418545**2)}" y2="{y1}" stroke="#b52c44" stroke-dasharray="8 5"/>','<text x="250" y="605" font-size="15">resolved + SGS + molecular stress (m²/s²)</text>','<text x="45" y="50" font-size="15">z (m)</text>']
for i,x in enumerate((200,300,400)):out.append(f'<text x="660" y="{100+i*24}" fill="{colors[x]}" font-size="14">x={x} m</text>')
out += ['<text x="660" y="200" fill="#b52c44" font-size="12">specified u*²</text>','<text x="660" y="228" font-size="12">short dashed:</text>','<text x="660" y="245" font-size="12">actual wall tau</text>','</svg>']
(b/'total_stress_fully.svg').write_text('\n'.join(out))
