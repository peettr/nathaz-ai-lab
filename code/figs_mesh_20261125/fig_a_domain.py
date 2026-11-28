import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
fig, ax = plt.subplots(figsize=(10, 6.2), dpi=200)
ax.add_patch(Rectangle((-4.5, -7), 19.5, 14, fill=False, lw=1.6, ec='k'))
ax.add_patch(Rectangle((-0.5, -0.5), 1, 1, fc='0.35', ec='k', lw=1.2))
for y in (-4.5, -1.5, 1.5, 4.5):
    ax.add_patch(FancyArrowPatch((-6.3, y), (-4.6, y), arrowstyle='-|>', mutation_scale=14, lw=1.4, color='tab:blue'))
ax.text(-7.0, 0, 'Inlet: uniform $U_\\infty=(1,0,0)$, no inflow turbulence, $\\tilde\\nu = 3\\nu$', color='tab:blue', ha='center', va='center', rotation=90, fontsize=9.5)
ax.text(15.3, 0, 'Outlet\n$p=0$, inletOutlet', ha='left', va='center', fontsize=9.5)
ax.text(5.25, 7.35, 'Top: slip', ha='center', fontsize=9.5); ax.text(5.25, -7.85, 'Bottom: slip', ha='center', fontsize=9.5)
ax.annotate('Square cylinder, $D=1$\nno-slip (Spalding wall function for $\\nu_t$)', xy=(0.5, 0.5), xytext=(2.6, 3.2), fontsize=9.5,
            arrowprops=dict(arrowstyle='->', lw=1))
def dim(x0, y0, x1, y1, txt, off=(0, 0)):
    ax.annotate('', xy=(x0, y0), xytext=(x1, y1), arrowprops=dict(arrowstyle='<->', lw=0.9))
    ax.text((x0 + x1) / 2 + off[0], (y0 + y1) / 2 + off[1], txt, ha='center', va='center', fontsize=9.5, backgroundcolor='w')
dim(-4.5, -2.2, -0.5, -2.2, '$4D$'); dim(0.5, -2.2, 15, -2.2, '$14.5D$'); dim(11.5, -7, 11.5, 7, '$14D$ (blockage 7.1%)', (0, 0))
ax.text(-4.3, -6.5, 'Spanwise: $L_z = 4D$, periodic (cyclic)\n$Re = U_\\infty D/\\nu = 22{,}000$', fontsize=9.5, ha='left', va='bottom')
ax.set_xlim(-7.6, 19.5); ax.set_ylim(-8.5, 8.2); ax.set_aspect('equal')
ax.set_xlabel('$x/D$'); ax.set_ylabel('$y/D$'); ax.set_title('(a) Computational domain and boundary conditions ($x$–$y$ plane)', fontsize=11)
ax.set_xticks(range(-4, 16, 2)); ax.set_yticks(range(-7, 8, 7))
fig.tight_layout(); fig.savefig(__file__.replace('fig_a_domain.py', 'fig_a_domain_bc.png'), facecolor='w')
print('ok')
