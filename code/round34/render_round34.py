#!/usr/bin/env python3
"""Manual transcription and geometry for the Round 34 source PNG; isolated execution."""
from pathlib import Path
import sys
import matplotlib as mpl
# Academic Figure Skill typography baseline (references/typography.md).
mpl.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans"],
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 8,
    "figure.titlesize": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.6, "xtick.direction": "out", "ytick.direction": "out",
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "legend.frameon": False,
})
# Academic Figure Skill palette (references/color-palettes.md).
CATEGORICAL = ["#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666"]
# Academic Figure Skill export baseline (references/export-specs.md).
mpl.rcParams.update({"pdf.fonttype": 42, "svg.fonttype": "none",
                     "savefig.bbox": "tight", "savefig.dpi": 300})
mpl.rcParams["font.sans-serif"] = ["DejaVu Sans", "Noto Sans SC", "Arial"]
def save_cns_figure(fig, filename):
    """Standard Academic Figure Skill export: vector PDF + 300dpi PNG preview."""
    fig.savefig(f"{filename}.pdf", bbox_inches="tight", dpi=300)
    fig.savefig(f"{filename}.png", bbox_inches="tight", dpi=300)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent
assert not any((OUT / f"{name}.{fmt}").exists()
               for name in ("academic_round34_v2", "kdense_round34_v2")
               for fmt in ("svg", "pdf", "png", "export.json")), "Refuse overwrite"
# Each box is distinct (no overlapping rectangles). Coordinates are original-layout transcription,
# not architecture assertions beyond what the PNG depicts.
NODES = [
    ("Input", "3×64×64", .3, 1.2, "input"),
    ("E1", "64", 2.05, 1.2, "enc"),
    ("E2", "128", 3.8, 1.2, "enc"),
    ("E3", "256", 5.55, 1.2, "enc"),
    ("E4", "512\n(bottleneck)", 7.3, 1.2, "enc"),
    ("D3", "256", 9.05, 1.2, "dec"),
    ("D2", "128", 10.8, 1.2, "dec"),
    ("D1", "64", 12.55, 1.2, "dec"),
    ("Output", "1×64×64", 14.3, 1.2, "out"),
    ("Coarse Head", "1×16×16", 8.15, 4.05, "aux"),
    ("Coarse", "Supervision", 11.05, 4.05, "sup"),
]
WIDTH, HEIGHT = 1.35, .96

def draw(name, colors):
    mpl.rcParams["font.sans-serif"] = ["DejaVu Sans", "Noto Sans SC", "Arial"]
    fig, ax = plt.subplots(figsize=(16.6, 8.3), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 16.0); ax.set_ylim(-2.0, 6.1); ax.axis("off")
    ax.set_aspect("equal", adjustable="box")
    ax.text(8, 5.85, "UNet Speed Distillation — Round 34 (Global Best)",
            ha="center", va="center", fontsize=16, weight="bold", color="#18283a")
    ax.text(8, 5.47, "4-level encoder-decoder  |  base=64  |  SE attention (r=1)  |  8.57M parameters  |  EMA RMSE = 0.0586",
            ha="center", va="center", fontsize=10, color="#42536a")
    for title, sub, x, y, kind in NODES:
        edge, face = colors[kind]
        ax.add_patch(FancyBboxPatch((x,y), WIDTH, HEIGHT,
                     boxstyle="round,pad=0.015,rounding_size=0.10", linewidth=1.35,
                     edgecolor=edge, facecolor=face, zorder=3))
        ax.text(x+WIDTH/2, y+HEIGHT/2, title+"\n"+sub, ha="center", va="center",
                fontsize=9.3, linespacing=1.55, color="#162333", zorder=4)
    def arrow(a,b,color="#556676",ls="solid",lw=1.5,ms=11):
        ax.add_patch(FancyArrowPatch(a,b, arrowstyle="-|>", mutation_scale=ms,
                     linewidth=lw, color=color, linestyle=ls, zorder=2,
                     shrinkA=1, shrinkB=1, connectionstyle="arc3,rad=0"))
    # Input -> E1 through D1 -> Output: exact depicted connection order.
    for i in range(8):
        x = NODES[i][2]
        arrow((x+WIDTH,1.68),(NODES[i+1][2],1.68))
        if i < 4:
            ax.text((x+WIDTH+NODES[i+1][2])/2, 2.58,"Pool 2×",
                    ha="center", va="center", fontsize=8, color="#475569")
        elif i == 4:
            ax.text((x+WIDTH+NODES[i+1][2])/2,2.58,"UpSample 2×",
                    ha="center", va="center", fontsize=8, color="#475569")
    # 3 separate unobstructed skip lanes below node baseline: E3→D3, E2→D2, E1→D1.
    skip_color = colors["skip"][0]
    for src, dst, lane, tag in [(3,5,.56,"Skip (x₃) + Cat"),
                                (2,6,-.22,"Skip (x₂) + Cat"),
                                (1,7,-1.0,"Skip (x₁) + Cat")]:
        sx=NODES[src][2]+WIDTH/2; dx=NODES[dst][2]+WIDTH/2
        ax.plot([sx,sx],[1.2,lane],color=skip_color,lw=1.5,ls=(0,(5,4)),zorder=1)
        ax.plot([sx,dx],[lane,lane],color=skip_color,lw=1.5,ls=(0,(5,4)),zorder=1)
        arrow((dx,lane),(dx,1.17),skip_color,ls=(0,(5,4)),lw=1.5)
        ax.text(8.05,lane+.15,tag,ha="center",va="center",fontsize=8.5,
                color=skip_color,bbox={"facecolor":"white","edgecolor":"none","pad":.7},zorder=2)
    # Bottleneck E4 branches into coarse head and supervision. Explicit original auxiliary link.
    arrow((7.3+WIDTH/2,2.16),(8.15+WIDTH/2,4.02),colors["aux"][0])
    arrow((8.15+WIDTH,4.53),(11.05,4.53),colors["aux"][0])
    # Preserve all four legend phrases from original image.
    for i,(label,kind) in enumerate([
        ("Encoder (ConvBlock + SE)","enc"),
        ("Decoder (ConvBlock + SE)","dec"),
        ("Coarse Auxiliary Head","aux"),
        ("Skip Connection","skip")]):
        y=-1.28-i*.18
        ax.scatter([.39],[y],s=45,c=[colors[kind][0]],marker="s",zorder=4)
        ax.text(.55,y,label,va="center",fontsize=8,color="#29384a")
    ax.text(15.7,-1.8,"Source: Round 34 architecture PNG (text and links transcribed; layout redrawn)",
            ha="right",va="bottom",fontsize=7,color="#637084")
    return fig

ACADEMIC={
    "input":("#A47210","#fff6dd"),"enc":(CATEGORICAL[0],"#eaf1f8"),
    "dec":(CATEGORICAL[1],"#faeeee"),"out":(CATEGORICAL[1],"#faeeee"),
    "aux":(CATEGORICAL[2],"#edf6ef"),"sup":(CATEGORICAL[3],"#fff2db"),
    "skip":(CATEGORICAL[4],"white")}
KDENSE={
    "input":("#B47600","#fff5d6"),"enc":("#0072B2","#eaf5fb"),
    "dec":("#D55E00","#fdf1e8"),"out":("#D55E00","#fdf1e8"),
    "aux":("#009E73","#e7f7f0"),"sup":("#B47600","#fff4d9"),
    "skip":("#CC79A7","white")}
if __name__ == "__main__":
    # All source data is only labels and connectivity; no remote imports or keys.
    fa=draw("academic",ACADEMIC)
    save_cns_figure(fa,str(OUT/"academic_round34_v2"))
    fa.savefig(OUT/"academic_round34_v2.svg",bbox_inches="tight",dpi=300)
    plt.close(fa)
    skill = Path.home()/"qt_sandbox/sci_fig/scientific-agent-skills/skills/scientific-visualization/scripts"
    sys.path.insert(0,str(skill))
    from style_presets import style_context
    from figure_export import export_figure
    with style_context("default",palette_name="okabe_ito_on_white"):
        fk=draw("kdense",KDENSE)
        report=export_figure(fk,str(OUT/"kdense_round34_v2"),formats=["svg","pdf","png"],
                dpi=300,bbox_inches="tight",font_mode="truetype",write_manifest=True,
                provenance={"source":"Round 34 architecture PNG", "method":"manual text/connectivity transcription; geometry redrawn"})
        print(report)
        plt.close(fk)
