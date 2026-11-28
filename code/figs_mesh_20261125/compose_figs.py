"""Compose mesh figures b-e from pvbatch renders (render/png/*.png + render_meta.json): add axes in D units and labels."""
import json, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import Rectangle
here = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(here, 'render', 'png')
meta = json.load(open(os.path.join(R, 'render_meta.json')))
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
def show(ax, key, title, flip_u=False, xl='$x/D$', yl='$y/D$', cyl=True):
    m = meta[key]; img = mpimg.imread(os.path.join(R, key + '.png'))
    u0, u1, v0, v1 = m['extent']
    if flip_u: img = img[:, ::-1]
    ax.imshow(img, extent=[u0, u1, v0, v1], origin='upper', interpolation='lanczos')
    if cyl and m['normal'] == 'z': ax.add_patch(Rectangle((-0.5, -0.5), 1, 1, fc='0.35', ec='k', lw=0.8, zorder=3))
    ax.set_xlim(u0, u1); ax.set_ylim(v0, v1); ax.set_aspect('equal'); ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(title, fontsize=10)
out = lambda n: os.path.join(here, n)
# b: medium full + near
fig, axs = plt.subplots(1, 2, figsize=(14, 5.2), dpi=220, gridspec_kw={'width_ratios': [1.4, 1]})
show(axs[0], 'medium_xy_full', 'Original medium mesh (1.97 M cells): $x$–$y$ section, full domain')
show(axs[1], 'medium_xy_near', 'Original medium mesh: near the cylinder')
fig.suptitle('(b) Original medium mesh, $x$–$y$ section at $z = 2.03D$', fontsize=11); fig.tight_layout(); fig.savefig(out('fig_b_medium_xy.png'), facecolor='w'); plt.close(fig)
# c: medium corner + wake
fig, axs = plt.subplots(1, 2, figsize=(14, 6), dpi=220, gridspec_kw={'width_ratios': [1, 1.4]})
show(axs[0], 'medium_xy_corner', 'Front-top corner: first cell 0.0046$D$, corner clustering along the faces')
show(axs[1], 'medium_xy_wake', 'Separated shear layer and near wake')
fig.suptitle('(c) Original medium mesh: corner and shear-layer region (no dedicated near-wall refinement)', fontsize=11); fig.tight_layout(); fig.savefig(out('fig_c_medium_corner.png'), facecolor='w'); plt.close(fig)
# d: spanwise layers (y-z at x = 1.003D), medium vs fine
fig, axs = plt.subplots(1, 2, figsize=(10, 8), dpi=220)
show(axs[0], 'medium_yz_span', 'Original medium: 40 layers, $\\Delta z = 0.10D$', flip_u=True, xl='$y/D$', yl='$z/D$', cyl=False)
show(axs[1], 'fine_yz_span', 'New fine: 80 layers, $\\Delta z = 0.05D$', flip_u=True, xl='$y/D$', yl='$z/D$', cyl=False)
fig.suptitle('(d) Spanwise resolution: $y$–$z$ section at $x = 1.0D$ (behind the cylinder), $L_z = 4D$', fontsize=11); fig.tight_layout(); fig.savefig(out('fig_d_spanwise.png'), facecolor='w'); plt.close(fig)
# e: medium vs fine, same views
fig, axs = plt.subplots(2, 2, figsize=(13, 10.5), dpi=220)
show(axs[0, 0], 'medium_xy_near', 'Original medium (1.97 M): near the cylinder')
show(axs[0, 1], 'fine_xy_near', 'New fine (9.48 M): near the cylinder')
show(axs[1, 0], 'medium_xy_corner', 'Original medium: front-top corner (first cell 0.0046$D$)')
show(axs[1, 1], 'fine_xy_corner', 'New fine: front-top corner (first cell 0.001$D$)')
fig.suptitle('(e) Original vs new mesh, same views ($x$–$y$ section at $z = 2.03D$)', fontsize=11); fig.tight_layout(); fig.savefig(out('fig_e_medium_vs_fine.png'), facecolor='w'); plt.close(fig)
print('composed')
