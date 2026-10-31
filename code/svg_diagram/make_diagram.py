"""Bounded text-only authoring of the svg-diagram quick-trial figure."""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).with_name('research_platform_architecture_v3.svg')
styles = {
    'blue': ('#dbeafe', '#3b82f6', '#1e40af'),
    'amber': ('#fef3c7', '#f59e0b', '#b45309'),
    'green': ('#d1fae5', '#22c55e', '#166534'),
    'purple': ('#f3e8ff', '#a855f7', '#6b21a8'),
    'pink': ('#fce7f3', '#ec4899', '#9d174d'),
}
lines = ['<svg viewBox="0 0 1080 468" width="1080" xmlns="http://www.w3.org/2000/svg">',
         '  <title>研究平台总架构图</title>',
         '  <desc>Research Chat、Claude Lead、Hermes 研究和工具 bot、Router 模型通道、守卫、知识与计算资源的关系。数据来源：平台手册、变更日志与快试规则。</desc>',
         '  <style>text { font-family: \'PingFang SC\', \'Microsoft YaHei\', \'Noto Sans CJK SC\', system-ui, sans-serif; }</style>',
         '  <defs>']
for k, (_, stroke, _) in styles.items():
    lines.append(f'    <marker id="arrow-{k}" markerWidth="8" markerHeight="8" refX="2" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 L2,4 z" fill="{stroke}"/></marker>')
lines += ['  </defs>', '  <rect x="0" y="0" width="1080" height="468" fill="#ffffff"/>',
          '  <text x="540" y="36" font-size="16" text-anchor="middle" fill="#1e293b">研究平台 · 总架构</text>',
          '  <text x="540" y="59" font-size="10" text-anchor="middle" fill="#64748b">交互与委托 / 模型路由 / 安全边界 / 知识与算力</text>']

def path(d, color):
    lines.append(f'  <path d="{d}" fill="none" stroke="{styles[color][1]}" stroke-width="1.5" marker-end="url(#arrow-{color})"/>')

def box(x, y, w, h, color, labels):
    fill, stroke, ink = styles[color]
    lines.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}"/>')
    center = x + w / 2
    # Two 12px lines, separated by 18px, optically centred in a 54px box.
    bases = [y + h / 2 + 4] if len(labels) == 1 else [y + h / 2 - 5, y + h / 2 + 13]
    for text, baseline in zip(labels, bases):
        lines.append(f'  <text x="{center:g}" y="{baseline:g}" font-size="12" text-anchor="middle" fill="{ink}">{escape(text)}</text>')

# All straight lines start 5px after a source, end 11px before a target.
path('M540,113 L540,124', 'blue')
path('M370,153 C 270,153 185,168 185,187', 'purple')
path('M540,176 L540,187', 'purple')
path('M710,153 L719,153', 'amber')
path('M895,176 L895,187', 'amber')
path('M185,257 L185,268', 'pink')
path('M540,257 L540,268', 'green')
path('M680,257 C 715,257 707,306 719,306', 'green')
path('M185,338 L185,349', 'pink')

box(375, 72, 330, 36, 'blue', ['Research Chat 界面'])
box(375, 135, 330, 36, 'purple', ['各项目 Lead（Claude）'])
box(20, 198, 330, 54, 'purple', ['Hermes 研究 bot', '项目执行与试验'])
box(375, 198, 330, 54, 'purple', ['Hermes 工具 bot', 'ComputeOps / LitWiki 等'])
box(730, 135, 330, 36, 'amber', ['Router · 模型请求路由'])
box(730, 198, 330, 54, 'amber', ['Claude / Gemini / Codex', 'Grok 等模型通道'])
box(20, 279, 330, 54, 'pink', ['guard · 硬安全守卫', 'SSH / 提交 / 删改'])
box(375, 279, 330, 54, 'green', ['知识库 / 文献库', 'rc-kb / LitWiki / Zotero'])
box(730, 279, 330, 54, 'green', ['Colab', 'GPU 计算'])
box(20, 360, 330, 54, 'green', ['超算 CRC / TACC', '计算与作业登记 rc-job'])
lines += ['  <text x="540" y="444" font-size="10" text-anchor="middle" fill="#64748b">数据来源：平台手册 CLAUDE.md、平台 CHANGELOG.md、快试 CLAUDE.md（只读）；绘制：svg-diagram · MIT</text>', '</svg>']
OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(OUT)
