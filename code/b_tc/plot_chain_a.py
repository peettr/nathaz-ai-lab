#!/usr/bin/env python3
"""Plot station-level pilot ratios; QC follows chain_a_results.md."""
import csv,html
from pathlib import Path
p=Path(__file__).resolve().parent
rs=list(csv.DictReader((p/'pilot5/chain_a_station_rows.csv').open()))
keep=[]
for r in rs:
 if not r['ratio_sustained'] or int(r['obs_sknt_rows'])<720:continue
 if float(r['obs_peak_5sec_gust_kt'])<float(r['obs_peak_sustained_kt']):continue
 keep.append(r)
keep.sort(key=lambda r:(['IAN','IDALIA','FRANCINE','HELENE','MILTON'].index(r['event']),r['station']))
w,h=970,130+36*len(keep);x0,x1=175,850;scale=lambda v:x0+(v/2.2)*(x1-x0)
a=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',f'<rect width="{w}" height="{h}" fill="white"/>','<style>text{font:14px sans-serif} .minor{fill:#566; font-size:12px}</style>',f'<text x="20" y="28" font-size="19">Best-track + simplified Holland, predicted / observed peak wind</text>',f'<rect x="{scale(.8):.1f}" y="45" width="{scale(1.2)-scale(.8):.1f}" height="{36*len(keep)+22}" fill="#e5f5e8"/>']
for tick in (0,.4,.8,1,1.2,1.6,2,2.2):
 x=scale(tick);a +=[f'<line x1="{x:.1f}" x2="{x:.1f}" y1="45" y2="{65+36*len(keep)}" stroke="{"#556" if tick==1 else "#ddd"}"/>',f'<text x="{x:.1f}" y="{85+36*len(keep)}" text-anchor="middle" class="minor">{tick:g}</text>']
colors={'IAN':'#a50f15','FRANCINE':'#08519c','HELENE':'#006d2c','MILTON':'#6a51a3'}
for i,r in enumerate(keep):
 y=63+i*36;v=float(r['ratio_sustained']);a +=[f'<text x="20" y="{y+5}" class="minor">{html.escape(r["event"])} / {html.escape(r["station"])} ({r["obs_sknt_rows"]} min)</text>',f'<circle cx="{scale(min(v,2.2)):.1f}" cy="{y}" r="6" fill="{colors[r["event"]]}"/>',f'<text x="860" y="{y+5}" class="minor">{v:.2f}</text>']
a += [f'<text x="20" y="{h-19}" class="minor">Source: NOAA NHC HURDAT2 + ATCF b-decks; IEM/NCEI ASOS 1-min archive. Green: [0.8,1.2].</text>','</svg>']
(p/'chain_a_ratio_pilot5.svg').write_text('\n'.join(a));print(len(keep),h)
