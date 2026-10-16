"""Authoritative cohort-normalized addendum; never replace prior report."""
import csv,pathlib,datetime,zoneinfo
P=pathlib.Path(__file__).resolve().parent;a=list(csv.DictReader(open(P/'passage_station_near500_v2.csv')))
segs=['TX','LA_to_Panhandle','FL_peninsula','Carolinas'];zones=['RMW_le1','RMW_1to3','km_le50','km_le100'];cats=['TS_only','Cat1-2','Cat3+','Cat4-5']
sources=[('RAFT','all'),('STORM','all'),('HURDAT2','1979-2018'),('HURDAT2','1988-2018')]
lines=['# DIAG_passage_v1 补注：入样风暴分母与图例','时间：'+datetime.datetime.now(zoneinfo.ZoneInfo('America/New_York')).strftime('%m-%d %H:%M EDT')+'。本补注不覆盖 `DIAG_passage_v1.md`，其年率、事件计数及条件强度均保持有效；但 v1 主表把“每千条入样风暴”定义为全北大西洋原始合格风暴。委托要求的**距 19 站任一站 ≤500 km 的入样风暴**分母另见下表；下表为每千条近岸入样风暴的条件过境计数，而非全盆地发生率。年率一律仍用全盆地原始分母，绝不可把近岸条件分母代入年率。','', '入样分母：RAFT 15,063；STORM 32,016（同 `DIAG_inputs_v1.md` 原生节点严格 500 km 口径）；HURDAT2 1979–2018 为 196、1988–2018 为 163（`denominator_near500.py` 从原始 HURDAT2 和既定 24h 门槛重算）。v1 主表对应的全盆地分母分别为 40,000、107,063、483、408。以下四元组为 TS_only / Cat1-2 / Cat3+ / Cat4-5；末档包含于 Cat3+。','', '| 圈 | 海岸段 | RAFT/千条近岸入样 | STORM/千条近岸入样 | OBS 1979–2018 | OBS 1988–2018 |','|---|---|---:|---:|---:|---:|']
for zone in zones:
 for seg in segs:
  cells=[]
  for src,per in sources:
   v=[]
   for cat in cats:
    r=[x for x in a if (x['source'],x['period'],x['segment'],x['zone'],x['category'])==(src,per,seg,zone,cat)]
    v.append(sum(float(x['per_1000_near500']) for x in r)/len(r))
   cells.append(' / '.join(f'{x:.2f}' for x in v))
  lines.append('| '+zone+' | '+seg+' | '+' | '.join(cells)+' |')
lines+=['','逐站所有类别在 `passage_station_near500_v2.csv`；分母审计在 `passage_near500_denominators_v2.csv`。由于条件分母变化，RAFT 与 STORM 的“每千条”相对比值不同于年率比值；判断全盆地目录对沿海年过境频率贡献时仍以 v1 的场/站/年为准。OBS 1979–2018 的 RMW 圈因 1988 年前 EBTRK 缺测仍不可比；不能用本补注的重标度将其变得可比。','', 'v1 图 `passage_v1.png` 右侧散点缺独立图例；请改看 `passage_v1_legend.png`，图例显示 RAFT/STORM/HURDAT2，底部保留数据来源。','', '归因不变：与观测比，RAFT 在固定 100 km 的年 TS+ 和强度条件比例均偏低；与 STORM 比，RAFT TS+ 年率不低、强度尾部偏弱。']
(P/'DIAG_passage_v1_ADDENDUM.md').write_text('\n'.join(lines)+'\n');print('addendum lines',len(lines))
