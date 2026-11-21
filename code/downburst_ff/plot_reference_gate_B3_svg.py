"""Small no-solver reference gate line chart from Colab metrics."""
import json, pathlib, html
p=pathlib.Path(__file__).resolve().parent
rows=[json.loads(x) for x in (p/'reference_metrics_B3_final.jsonl').read_text().splitlines()]
seeds=[112,203,317]
assert len(rows)==6 and all(x['rc']==0 for x in rows)
W,H=700,430; l,r,t,b=85,30,45,75
X=lambda i:l+i*(W-l-r)/2
Y=lambda v:H-b-(v-.18)/(.40-.18)*(H-b-t)
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<rect width="100%" height="100%" fill="white"/>','<text x="350" y="25" text-anchor="middle" font-family="sans-serif" font-size="17">Task52 author-chain NTM 16 m/s · NREL 5 MW</text>']
for v in (.20,.25,.30,.35,.40):
 y=Y(v);parts += [f'<line x1="{l}" y1="{y}" x2="{W-r}" y2="{y}" stroke="#ddd"/>',f'<text x="{l-8}" y="{y+4}" text-anchor="end" font-size="12">{v:.2f}</text>']
for i,s in enumerate(seeds):parts.append(f'<text x="{X(i)}" y="{H-b+25}" text-anchor="middle" font-size="13">{s}</text>')
parts += [f'<text x="{W//2}" y="{H-15}" text-anchor="middle" font-size="13">TurbSim random seed</text>',f'<text x="20" y="{H//2}" transform="rotate(-90 20 {H//2})" text-anchor="middle" font-size="13">RotSpeed std, 100–600 s (rpm)</text>']
for g,color in [('FB','#1f77b4'),('FF','#d62728')]:
 vals=[next(z['RotSpeed_std_rpm'] for z in rows if z['seed']==s and z['group']==g) for s in seeds]
 pts=' '.join(f'{X(i)},{Y(v)}' for i,v in enumerate(vals));parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
 for i,v in enumerate(vals):parts += [f'<circle cx="{X(i)}" cy="{Y(v)}" r="4" fill="{color}"/>',f'<text x="{X(i)+8}" y="{Y(v)-8}" fill="{color}" font-size="12">{v:.3f}</text>']
 parts.append(f'<text x="{W-r-35}" y="{t+20 if g=="FB" else t+42}" fill="{color}" font-size="14">{g}</text>')
parts.append('</svg>')
out=p/'reference_gate_line_B3.svg';assert not out.exists();out.write_text('\n'.join(parts));print(out)
