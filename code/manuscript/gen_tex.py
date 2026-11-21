import json,sys
M=json.load(open(sys.argv[1]))['metrics']; FIG=sys.argv[2]
rows=[]
for L,Ln in [('12h','12 h'),('24-72h','24--72 h'),('96-168h','96--168 h')]:
    for a in ['CMA','JTWC','JMA']:
        for v,vn in [('P','$P_{\\min}$ (hPa)'),('V','$V_{\\max}$ (m/s)')]:
            z=M[L]['agencies'][a][v]; b=z['bootstrap']; lo,hi=b['ci90']
            dg='$^\\dagger$' if a=='JMA' else ''
            rows.append(f"{Ln} & {a}{dg} & {vn} & {z['lq']['n']} & {z['lq']['mae']:.2f} & {z['sr']['mae']:.2f} & {z['R']:.3f} & {b['difference_sr_minus_pangu']:.2f} [{lo:.2f}, {hi:.2f}] \\\\")
tab='\n'.join(rows)
tex=open(sys.argv[3] if len(sys.argv)>3 else 'template.tex',encoding='utf-8').read().replace('%%TABLE%%',tab).replace('%%FIG%%',FIG)
open(sys.argv[4] if len(sys.argv)>4 else 'L26.28_manuscript.tex','w',encoding='utf-8').write(tex)
