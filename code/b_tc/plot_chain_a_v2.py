#!/usr/bin/env python3
"""Unclipped figure with explicit measurement definition."""
import csv,html
from pathlib import Path
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'pilot5/chain_a_station_rows.csv').open()))
r=[x for x in rows if x['ratio_sustained'] and int(x['obs_sknt_rows'])>=720 and float(x['obs_peak_5sec_gust_kt'])>=float(x['obs_peak_sustained_kt'])]
r.sort(key=lambda x:(['IAN','FRANCINE','HELENE','MILTON'].index(x['event']),x['station']))
w,h=1020,145+35*len(r);x0,x1=180,900;scale=lambda v:x0+v/4.2*(x1-x0)
a=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',f'<rect width="{w}" height="{h}" fill="white"/>','<style>text{font:13px sans-serif} .small{font-size:11px;fill:#556}</style>','<text x="18" y="25" font-size="18">Best-track Holland screening: predicted / ASOS sustained-wind proxy</text>',f'<rect x="{scale(.8):.1f}" y="45" width="{scale(1.2)-scale(.8):.1f}" height="{35*len(r)+20}" fill="#ddf0dc"/>']
for tick in (0,.5,1,1.5,2,2.5,3,3.5,4):
 x=scale(tick);a += [f'<line x1="{x:.1f}" x2="{x:.1f}" y1="45" y2="{68+35*len(r)}" stroke="{"#444" if tick==1 else "#ddd"}"/>',f'<text x="{x:.1f}" y="{86+35*len(r)}" text-anchor="middle" class="small">{tick:g}</text>']
for i,x in enumerate(r):
 y=62+i*35;v=float(x['ratio_sustained']);a += [f'<text x="18" y="{y+5}" class="small">{html.escape(x["event"])} / {html.escape(x["station"])} ({x["obs_sknt_rows"]} min)</text>',f'<circle cx="{scale(v):.1f}" cy="{y}" r="6" fill="{dict(IAN="#a50f15",FRANCINE="#08519c",HELENE="#006d2c",MILTON="#6a51a3")[x["event"]]}"/>',f'<text x="915" y="{y+5}" class="small">{v:.2f}</text>']
a += [f'<text x="{(x0+x1)/2}" y="{h-42}" text-anchor="middle">Predicted / observed peak ASOS sustained wind (ratio)</text>',f'<text x="18" y="{h-19}" class="small">NOAA NHC HURDAT2 + ATCF b-decks; IEM/NCEI ASOS 1-min reports (approx. 2-min mean); 0.8–1.2 shaded.</text>','</svg>']
(p/'chain_a_ratio_pilot5_v2.svg').write_text('\n'.join(a))
