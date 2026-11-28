import csv, hashlib, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/'diagA1b3_sealed_20261119_151419'/'session_luw-t17-a1b-0e0ecbd4'/'evidence'
IMPULSE=(1.0*0.00120843*(1/78)**2/1.0)*(256*128*64)*8975
OUT={"source":str(SRC),"impulse_reference":{"definition":"I=(rho*F*dt^2/dx)*Nx*Ny*H*round(T/2); lattice momentum; rho=1 kg/m3, F=0.00120843 m/s2, dt=1/78 s, dx=1 m, Nx=256, Ny=128, H=64, round(T/2)=8975","value":IMPULSE},"cases":{},"sha256":{}}
for label in ('d1','d2'):
    files=[SRC/f'{label}_{kind}.csv' for kind in ('ledger','layers')]
    for file in files:
        actual=hashlib.sha256(file.read_bytes()).hexdigest(); side=file.with_name(file.name+'.sha256').read_text().split()[0]
        assert actual==side, file
        OUT['sha256'][file.name]=actual
    ledger=list(csv.DictReader(files[0].open())); layers=list(csv.DictReader(files[1].open()))
    L={int(r['step']):r for r in ledger};Z={}
    for r in layers: Z.setdefault(int(r['step']),{})[int(r['z'])]=float(r['px_lattice'])
    assert len(L)==191 and len(Z)==191 and all(len(v)==64 for v in Z.values())
    assert set(L)==set(Z) and all(abs(sum(Z[s].values())-float(L[s]['px_fluid_lattice']))<1e-5 for s in L)
    p=lambda s:float(L[s]['px_fluid_lattice']); m=lambda s:float(L[s]['mass_fluid_lattice'])
    vals=[p(s) for s in sorted(L) if s>=1];range_px=max(vals)-min(vals)
    changes={str(end):{str(z):Z[end][z]-Z[0][z] for z in range(1,65)} for end in (1,10,100,1000)}
    result={'sample_count':len(L),'layer_rows':len(layers),'steps':sorted(L),'p_at':{str(s):p(s) for s in (0,1,10,100,1000)},'m_at':{str(s):m(s) for s in (0,1,10,100,1000)},'delta_p_0_1':p(1)-p(0),'delta_p_1_1000':p(1000)-p(1),'relative_delta_0_1':(p(1)-p(0))/p(0) if p(0) else None,'relative_delta_1_1000':(p(1000)-p(1))/p(1) if p(1) else None,'range_p_1_1000':range_px,'range_over_a7_impulse':range_px/IMPULSE,'max_abs_p_0_1000':max(abs(p(s)) for s in L),'from_step1_pass_1e_minus5':abs((p(1000)-p(1))/p(1))<=1e-5 if p(1) else p(1000)==0,'layer_changes':changes,'top_absolute_layer_delta_0_1':sorted(({'z':z,'delta':changes['1'][str(z)]} for z in range(1,65)), key=lambda d:abs(d['delta']),reverse=True)[:10], 'layer_band_delta_0_1':{name:sum(Z[1][z]-Z[0][z] for z in band) for name,band in {'bottom_1_2':range(1,3),'interior_3_62':range(3,63),'top_63_64':range(63,65)}.items()},'mass_relative_delta_0_1000':(m(1000)-m(0))/m(0)}
    OUT['cases'][label]=result
    for tag,rows in [('ledger',ledger),('layers',layers)]:
        target=ROOT/f'{label}_{tag}_verified.csv'
        with target.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
# lightweight SVG, preserving all measured samples
W,H=1050,630
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="white"/><style>text{{font-family:sans-serif;font-size:14px}} .axis{{stroke:#444;fill:none}} .line{{fill:none;stroke-width:2}}</style>']
for ix,label in enumerate(('d1','d2')):
    y0=60+ix*290; y1=y0+220; x0=110;x1=1000
    ledger=list(csv.DictReader((SRC/f'{label}_ledger.csv').open()));v=[float(r['px_fluid_lattice']) for r in ledger]
    lo=min(v);hi=max(v);pad=max((hi-lo)*.06,1 if label=='d2' else 0.1);lo-=pad;hi+=pad
    parts += [f'<path class="axis" d="M{x0},{y0}V{y1}H{x1}"/>',f'<text x="{x0}" y="{y0-13}">{label.upper()} Px(t) (lattice momentum), {len(v)} samples</text>',f'<text x="8" y="{y0+10}">{hi:.3f}</text>',f'<text x="8" y="{y1}">{lo:.3f}</text>',f'<text x="{x0}" y="{y1+20}">0</text>',f'<text x="{x1-35}" y="{y1+20}">1000 step</text>']
    coords=' '.join(f'{x0+890*int(r["step"])/1000:.2f},{y1-220*(float(r["px_fluid_lattice"])-lo)/(hi-lo):.2f}' for r in ledger)
    parts.append(f'<polyline class="line" stroke="{("#1463ad" if label=="d1" else "#b64432")}" points="{coords}"/>')
parts.append('<text x="110" y="623">Px = sum over fluid cells of rho*u_x; DDF population momentum not measured. M(t) is in the verified CSV.</text></svg>')
(ROOT/'PX_M_layers.svg').write_text('\n'.join(parts))
layer_svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="590"><rect width="100%" height="100%" fill="white"/>']
for i,label in enumerate(('d1','d2')):
    mid=145+285*i
    layer_svg.append(f'<text x="70" y="{25+285*i}" font-family="sans-serif">{label.upper()} ΔPx(z) vs step 0</text><path d="M70 {mid}H970 M70 {mid-110}V{mid+110}" stroke="#555"/>')
    for step,color in zip((1,10,100,1000),('#a00','#d80','#1868a0','#4a4')):
        vals=OUT['cases'][label]['layer_changes'][str(step)]
        pts=' '.join(f'{70+(z-1)*900/63:.1f},{mid-float(vals[str(z)])*.27:.1f}' for z in range(1,65))
        layer_svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{pts}"/>')
layer_svg.append('<text x="70" y="575" font-family="sans-serif">z 1..64; red=step 1, orange=10, blue=100, green=1000; same y scale</text></svg>')
(ROOT/'LAYER_DELTA.svg').write_text('\n'.join(layer_svg))
(ROOT/'RESULT.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{key:value for key,value in obj.items() if key not in ('steps','layer_changes')} for k,obj in OUT['cases'].items()},ensure_ascii=False,indent=2))
print('IMPULSE',IMPULSE)
