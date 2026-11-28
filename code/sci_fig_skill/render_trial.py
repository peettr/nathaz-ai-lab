#!/usr/bin/env python3
"""Two source-grounded schematics; source is a dated textual record, not a model audit.
Run only in the isolated sandbox venv. This file never reads model data or keys.
"""
import argparse
import sys
from pathlib import Path

# Academic Figure Skill typography baseline, verbatim (typography.md)
import matplotlib as mpl
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans"],
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 8,
    "figure.titlesize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "legend.frameon": False,
})
# Academic Figure Skill color baseline, verbatim (color-palettes.md)
CATEGORICAL = ["#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666"]
CATEGORICAL_EXTENDED = [
    "#2166AC", "#B2182B", "#1B7837", "#F1A340", "#762A83", "#666666",
    "#4393C3", "#D6604D", "#5AAE61", "#B35806", "#9970AB", "#999999",
]
DIVERGING   = ["#2166AC", "#F7F7F7", "#B2182B"]
SEQUENTIAL  = ["#F7FBFF", "#6BAED6", "#08306B"]
ACCENT_RED  = "#B2182B"
GREY        = "#999999"
BLACK       = "#222222"
# Academic Figure Skill export baseline, verbatim (export-specs.md)
mpl.rcParams.update({
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})
def save_cns_figure(fig, filename):
    """Standard Academic Figure Skill export: vector PDF + 300dpi PNG preview."""
    fig.savefig(f"{filename}.pdf", bbox_inches="tight", dpi=300)
    fig.savefig(f"{filename}.png", bbox_inches="tight", dpi=300)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

SRC = "Source: project_graph_deeponet.md lines 19–44, 48–56 (dated 2026-04-02); schematic, not code-verified"


def box(ax, x, y, w, h, label, edge, fill, fontsize=7.3):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.005,rounding_size=0.012",lw=1.1,edgecolor=edge,facecolor=fill))
    ax.text(x+w/2,y+h/2,label,ha="center",va="center",fontsize=fontsize,color="#202a37",linespacing=1.4)

def arrow(ax, x1,y1,x2,y2,color="#536273",style="solid"):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle="-|>",mutation_scale=10,lw=1.15,color=color,linestyle=style,shrinkA=2,shrinkB=2))

def base_figure(title):
    fig,ax=plt.subplots(figsize=(11.5,5.3),dpi=130)
    ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis("off")
    ax.text(.04,.95,title,fontsize=13,fontweight="bold",color="#17243a",va="center")
    ax.text(.04,.90,"Recorded best: HybridGraphCNN + FineGraph48 + Fourier64 trunk",fontsize=9,color="#526176")
    return fig,ax

def academic(out):
    fig,ax=base_figure("Graph-DeepONet · recorded architecture / 记录结构")
    blue=CATEGORICAL[0]; green=CATEGORICAL[2]; purple=CATEGORICAL[4]
    ax.text(.045,.795,"BRANCH / 图分支",fontweight="bold",fontsize=9,color=blue)
    ax.text(.045,.455,"TRUNK / 查询主干",fontweight="bold",fontsize=9,color=green)
    upper=[(.045,"建筑几何\n输入"),(.265,"FineGraph48\n图表示"),(.49,"HybridGraphCNN\nGAT + CNN 双路径"),(.745,"branch code\np = 64")]
    widths=[.15,.16,.19,.16]
    for (x,t),w in zip(upper,widths):box(ax,x,.665,w,.105,t,blue,"#edf3fa")
    for i in range(3):arrow(ax,upper[i][0]+widths[i],.718,upper[i+1][0],.718)
    lower=[(.045,"查询坐标\n(x, y)"),(.265,"Fourier64\nm = 64; σ = 10.0"),(.49,"位置感知 trunk\n具体注入方式未记录"),(.745,"trunk code\np = 64")]
    for (x,t),w in zip(lower,widths):box(ax,x,.325,w,.105,t,green,"#eef7f1",7.0)
    for i in range(3):arrow(ax,lower[i][0]+widths[i],.378,lower[i+1][0],.378)
    box(ax,.777,.11,.19,.105,"逐点内积 + bias\n风速（单通道）",purple,"#f4eff9")
    arrow(ax,.825,.665,.825,.22,purple)
    arrow(ax,.865,.325,.865,.22,purple)
    ax.text(.047,.565,"GAT/CNN 的层数、通道、分辨率、融合细节：记录里没有；图不补猜测。",fontsize=8,color="#546176")
    ax.text(.045,.065,SRC,fontsize=7,color="#546176")
    save_cns_figure(fig,str(out))
    fig.savefig(str(out)+".svg",bbox_inches="tight",dpi=300)
    plt.close(fig)

def kdense(out, skill_dir):
    sys.path.insert(0,str(skill_dir/"scripts"))
    from style_presets import style_context
    from figure_export import export_figure
    with style_context("default",palette_name="okabe_ito_on_white"):
        fig,ax=base_figure("Graph-DeepONet · evidence-first schematic / 证据优先示意")
        ax.text(.04,.785,"A   Geometry → branch",fontsize=9,fontweight="bold",color="#0072B2")
        ax.text(.04,.515,"B   Query → trunk",fontsize=9,fontweight="bold",color="#009E73")
        top=[(.04,"建筑几何"),(.26,"FineGraph48"),(.49,"HybridGraphCNN\nGAT + CNN"),(.76,"branch: p=64")]
        bottom=[(.04,"查询坐标 (x,y)"),(.26,"Fourier64\nm=64; σ=10.0"),(.49,"位置感知 trunk\n接入细节未知"),(.76,"trunk: p=64")]
        ww=[.155,.17,.2,.18]
        for row,y,c,bg in [(top,.665,"#0072B2","#edf5fa"),(bottom,.395,"#009E73","#eaf7f1")]:
            for (x,s),w in zip(row,ww):box(ax,x,y,w,.095,s,c,bg,7.1)
            for j in range(3):arrow(ax,row[j][0]+ww[j],y+.048,row[j+1][0],y+.048)
        box(ax,.76,.16,.18,.095,"逐点内积 + bias\n单通道风速","#CC79A7","#f8eef4")
        arrow(ax,.845,.665,.845,.265,"#CC79A7")
        arrow(ax,.89,.395,.89,.265,"#CC79A7")
        ax.text(.04,.285,"Unspecified in record: layer count, channels, resolution, fusion details.",fontsize=8,color="#4d5765")
        ax.text(.04,.07,SRC,fontsize=7,color="#4d5765")
        report=export_figure(fig,str(out),formats=["svg","pdf","png"],dpi=300,bbox_inches=None,
                             font_mode="truetype",provenance={"source":"project_graph_deeponet.md:19-44,48-56","limitations":"schematic; unknown dimensions not invented"},write_manifest=True)
        print("K-Dense export:",report)
        plt.close(fig)

if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--kdense-skill",type=Path,required=True)
    a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    academic(a.out/"academic_figure")
    kdense(a.out/"kdense_visualization",a.kdense_skill)
