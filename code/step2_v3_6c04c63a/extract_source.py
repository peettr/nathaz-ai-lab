import ast
from pathlib import Path
base = Path('./26_Quick_Trials/06_Logs/L26.30')
src = base / 'step1a_final/community_wind_simulation.py'
out = base / 'step2_v3_6c04c63a/source_extracted.py'
s = src.read_text(encoding='utf-8-sig')
lines = s.splitlines(keepends=True)
functions = {'make_bounds','write_bmd','body_U_meanABL','body_k','body_omega','body_nut'}
constants = {'TEMPLATE','TP_RANSkwSST','P_BODY','SIDE_MAP','TP_RANSC','TP_PROFILE','TP_PLANE','TP_transportProperty','TP_surfFeat','TP_fvSch_RANS','TP_fvSol_RANS'}
sel = []
for n in ast.parse(s).body:
    if isinstance(n, ast.FunctionDef) and n.name in functions:
        sel.append(n)
    elif isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id in constants for x in n.targets):
        sel.append(n)
assert len(sel) == len(functions) + len(constants)
pieces = ['# Verbatim excerpts from community_wind_simulation.py\n']
for n in sel:
    pieces.append(f'# original lines {n.lineno}-{n.end_lineno}\n' + ''.join(lines[n.lineno-1:n.end_lineno]) + '\n')
out.write_text(''.join(pieces))
print(out)
