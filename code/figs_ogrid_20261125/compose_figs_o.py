"""Compose figures d, e, f for the 11d summary: original medium renders (../figs_mesh_20261125/render/png) vs the new
O-type mesh renders (render/png from job 1820640). Same views/extents as figs_mesh_20261125/compose_figs.py."""
import json, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Rectangle
here = os.path.dirname(os.path.abspath(__file__))
RM = os.path.join(here, '..', 'figs_mesh_20261125', 'render', 'png'); RO = os.path.join(here, 'render', 'png')
meta = json.load(open(os.path.join(RM, 'render_meta.json'))); meta.update(json.load(open(os.path.join(RO, 'render_meta.json'))))
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
def show(ax, key, title, flip_u=False, xl='$x/D$', yl='$y/D$', cyl=True):
    m = meta[key]; img = mpimg.imread(os.path.join(RO if key.startswith('ogrid') else RM, key + '.png'))
    u0, u1, v0, v1 = m['extent']
    if flip_u: img = img[:, ::-1]
    ax.imshow(img, extent=[u0, u1, v0, v1], origin='upper', interpolation='lanczos')
    if cyl and m['normal'] == 'z': ax.add_patch(Rectangle((-0.5, -0.5), 1, 1, fc='0.35', ec='k', lw=0.8, zorder=3))
    ax.set_xlim(u0, u1); ax.set_ylim(v0, v1); ax.set_aspect('equal'); ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(title, fontsize=10)
out = lambda n: os.path.join(here, n)
fig, axs = plt.subplots(1, 2, figsize=(10, 8), dpi=220)
show(axs[0], 'medium_yz_span', 'Original medium: 40 layers, $\\Delta z = 0.10D$', flip_u=True, xl='$y/D$', yl='$z/D$', cyl=False)
show(axs[1], 'ogrid_yz_span', 'New O-type: 80 layers, $\\Delta z = 0.05D$', flip_u=True, xl='$y/D$', yl='$z/D$', cyl=False)
fig.suptitle('(d) Spanwise resolution: $y$–$z$ section at $x = 1.0D$ (behind the cylinder), $L_z = 4D$', fontsize=11); fig.tight_layout(); fig.savefig(out('fig_d_spanwise.png'), facecolor='w'); plt.close(fig)
fig, axs = plt.subplots(2, 2, figsize=(13, 10.5), dpi=220)
show(axs[0, 0], 'medium_xy_near', 'Original medium (1.97 M): near the cylinder')
show(axs[0, 1], 'ogrid_xy_near', 'New O-type (6.04 M): near the cylinder')
show(axs[1, 0], 'medium_xy_corner', 'Original medium: front-top corner (first cell 0.0046$D$)')
show(axs[1, 1], 'ogrid_xy_corner', 'New O-type: front-top corner (first cell 0.001$D$)')
fig.suptitle('(e) Original vs new mesh, same views ($x$–$y$ section at $z = 2.03D$)', fontsize=11); fig.tight_layout(); fig.savefig(out('fig_e_medium_vs_ogrid.png'), facecolor='w'); plt.close(fig)
fig, axs = plt.subplots(1, 2, figsize=(14, 5.6), dpi=220, gridspec_kw={'width_ratios': [1.4, 1]})
show(axs[0], 'ogrid_xy_full', 'New O-type mesh (6.04 M cells): full domain')
show(axs[1], 'ogrid_xy_wake', 'Separated shear layer and near wake')
fig.suptitle('(f) New O-type mesh, $x$–$y$ section at $z = 2.03D$: ring of radius $2D$ around the cylinder', fontsize=11); fig.tight_layout(); fig.savefig(out('fig_f_ogrid_xy.png'), facecolor='w'); plt.close(fig)
print('composed')
