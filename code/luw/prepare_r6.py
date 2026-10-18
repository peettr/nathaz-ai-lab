"""Derive r6 scripts from verified r5 scripts; never edit r5 artifacts."""
from pathlib import Path
p = Path(__file__).parent

def derive(source, target, substitutions):
    text = (p/source).read_text()
    for old, new in substitutions:
        count = text.count(old)
        assert count == (2 if old == '/content/luw-aij-r5' and source == 'launch_r5.py' else 1), (source, old, count)
        text = text.replace(old, new)
    dest = p/target
    if dest.exists():
        print('EXISTS', dest)
        return
    dest.write_text(text)
    compile(text, str(dest), 'exec')
    print(dest)

root = ('/content/luw-aij-r5', '/content/luw-aij-r6')
derive('bootstrap_r5.py', 'bootstrap_r6.py', [root,
    ('x0,x1,y0,y1=760.,1260.,750.,1250.', 'x0,x1,y0,y1=300.,1260.,750.,1250.'),
    ('[500,500]', '[960,500]'),
    ('LUW Case E official-size base r5', 'LUW Case E west-extended base r6'),
    ('si_x_cfd = [0.000000, 500.000000]', 'si_x_cfd = [0.000000, 960.000000]'),
    ('# Measured prior run: 1 SI second ~78 lattice steps. 11000/78=141 s >500/3.92864=127 s.', '# Prior 1 SI second ~78 steps. (31000-11000)/78=256.4s >960/3.92864=244.4s.'),
    ('run_nstep = 20000', 'run_nstep = 31000')])
derive('launch_r5.py', 'launch_r6.py', [root,
    ("assert not (r/'solver.exit').exists()", "assert not (r/'solver.exit').exists();assert not (r/'solver.lock').exists();(r/'solver.lock').open('x').close()")])
derive('extract_r5.py', 'extract_r6.py', [root,
    ("35-org[0]", "495-org[0]"), ("465-org[0]", "925-org[0]"),
    ("+1010.50008-760", "+1010.50008-300"),
    ("('plus_dx',(dx,dx,dx))", "('plus_dx',(dx,dx,0.))"),
    ("for x in (5.,15.,25.,35.,42.):", "for x in (50.,150.,250.,350.,400.,502.):"),
    ("r.joinpath('offset_samples_r5.json')", "r.joinpath('offset_samples_r6.json')")])
# The r5 full-fluid selection was already supported by mask; redo shift fit independently in r6.
derive('compare_r5.py', 'compare_r6.py', [
    ("offset_samples_best_r5.json", "offset_samples_r6.json"),
    ("('no_offset','plus_dx','best_xy_plus_dx_z0')", "('no_offset','plus_dx')"),
    ("plt.subplots(3,2", "plt.subplots(2,2"),
    ("crop PF x760..1260 y750..1250", "crop PF x300..1260 y750..1250"),
    ("CaseE_W_scatter_r5.png", "CaseE_W_scatter_r6.png"),
    ("CaseE_W_points_r5.csv", "CaseE_W_points_r6.csv"),
    ("CaseE_W_metrics_r5.json", "CaseE_W_metrics_r6.json"),
    ("'sim_best_xy_plus_dx_z0','fluid_corners_no_offset','fluid_corners_plus_dx','fluid_corners_best'", "'fluid_corners_no_offset','fluid_corners_plus_dx'"),
    ("p['sample']['best_xy_plus_dx_z0']['sim_ratio'],", ""),
    ("p['sample']['best_xy_plus_dx_z0']['fluid_corners']", "")])
