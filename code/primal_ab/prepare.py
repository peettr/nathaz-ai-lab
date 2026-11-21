from pathlib import Path
import hashlib, shutil
p=Path(__file__).resolve().parent
src=p.parent

def change(text,a,b):
    assert text.count(a)==1,a
    return text.replace(a,b)

for name, steps in [('A',3000),('B',3000),('C',6000)]:
    dest=p/'cases'/name
    shutil.copytree(src/'case',dest)
    def edit(file,a,b):
        f=dest/'system'/file
        f.write_text(change(f.read_text(),a,b))
    if name=='A': edit('fvSchemes','gradSchemes {default Gauss linear;}','gradSchemes {default Gauss linear; grad(U) cellLimited Gauss linear 1;}')
    if name=='B': edit('fvSchemes','div(phi,U) bounded Gauss linearUpwind grad(U);','div(phi,U) bounded Gauss upwind;')
    if name=='C':
        edit('fvSolution','fields {p 0.2;} equations {"(U|nuTilda)" 0.5;}','fields {p 0.1;} equations {"(U|nuTilda)" 0.3;}')
        edit('controlDict','endTime 3000;','endTime 6000;')
    # Output-only change common to all arms: save terminal fields for patch y+.
    edit('controlDict','writeInterval 999999;',f'writeInterval {steps};')
    (dest/'sample_cells.json').write_text('{"mesh_cells":227656,"cell_ids":[]}\n')
    (dest/'expected_steps').write_text(str(steps)+'\n')

driver=(src/'cube_driver.py').read_text().split('# Save one common converged state')[0]
driver=change(driver,'assert all(len(r[f])==3000 for f in fields)','assert all(len(r[f])==int((case/\'expected_steps\').read_text()) for f in fields)')
driver=change(driver,"initial_state=solver.DASolver.getStates().copy()\n",'')
start=driver.index('# Wrap the actual OpenMDAO adjoint solve:')
end=driver.index('def status(',start)
driver=driver[:start]+driver[end:]
(p/'primal_driver.py').write_text(driver+'status(\'PRIMAL_GATE_PASSED\')\n')
for q in sorted((p/'cases').rglob('*')):
    if q.is_file(): print(hashlib.sha256(q.read_bytes()).hexdigest(), q.relative_to(p))
