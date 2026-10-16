from pathlib import Path
r=Path(__file__).parent
base='luw-aij-caseA-zcheck'; new='luw-aij-caseA-turb-20261014'
for src,dst in [('bootstrap_caseA_zcheck.py','bootstrap_caseA_turb.py'),('launch_caseA_zcheck.py','launch_caseA_turb.py'),('extract_caseA_zcheck.py','extract_caseA_turb.py')]:
    s=(r/src).read_text().replace(base,new)
    if src.startswith('bootstrap'):
        s=s.replace("(case/'conf.luwpf').write_text(txt)", "txt+='\\nvk_inlet_ti = 0.1468030617\\nvk_inlet_l = 100.0\\nvk_inlet_inflow_only = true\\nvk_inlet_face_mode = TARGET_INFLOW\\n'\n(case/'conf.luwpf').write_text(txt)")
    if src.startswith('extract'):
        s=s.replace("m.close()", "upstream=[{'x_from_inlet_m':x,'x_from_building_m':336-x,'z_m':z,'sample':interp(x+dx,352+dx,z+dx)} for z in (4.,40.,64.,128.) for x in (4.,24.,56.,96.,136.,176.,216.,256.,296.)]\n m.close()")
        s=s.replace("'UH':obs['UH']}","'UH':obs['UH'],'upstream':upstream}")
        s=s.replace('samples_caseA_zcheck.json','samples_caseA_turb.json')
    (r/dst).write_text(s)
print('generated unique scripts',new)
