# L22.7 综述分类表（Lead 复核版）。标签由 Lead 判定；Gemini #dd0a0d49 只提供文献线索与元数据。
# 字段: id, 文献, 场景, 耦合, 闭环, 尺度, 流场, 旋翼, 验证, 核实, 备注
# 场景: 建筑/城市 | 地面障碍物 | 舰船 | 风电场尾流 | 近壁(无来流) | 范围外
R=[
("01","Sutherland & Etele 2014, ICAS 2014_0370","建筑/城市","单向","有(PID)","小型多旋翼","RANS/LES","点质量","风场对风洞","Lead读全文(p1摘要,Table3)",""),
("02","Sutherland 2015, Carleton MASc, 10.22215/etd/2015-10946","建筑/城市","单向","有(PD-PID)","小型多旋翼","RANS/LES","点质量","风场对风洞","Lead读全文(p2,p107,p116,p117)","风力加在质心"),
("03","Sutherland, Etele, Fusina 2016, J Aircraft 10.2514/1.C033624","建筑/城市","单向","有(PD-PID)","小型多旋翼","RANS/LES","点质量","风场对风洞","Crossref","02 的期刊版"),
("04","Galway, Etele, Fusina 2011, J Aircraft 10.2514/1.C031325","建筑/城市","单向","有","小型无人直升机","DES/LES","叶素","风场对风洞","Crossref;标签据 Gemini 摘要","待核"),
("05","Raza 2015, Carleton PhD thesis","建筑/城市","单向","有(PID/模糊等)","小型多旋翼","LES","叶素/点质量","飞行试验(阵风)","Gemini 称读全文","待核"),
("06","Raza & Etele 2018, J Aircraft 10.2514/1.C034573","建筑/城市","单向","有(混合)","小型多旋翼","LES","叶素/点质量","飞行试验","仅摘要","待核"),
("07","Kakavitsas et al. 2024, IEEE Aerospace / TechRxiv","建筑/城市","单向","有(PX4 SITL)","小型多旋翼","RANS","Gazebo 刚体推力","无","Lead 检索摘要",""),
("08","Krawczyk et al. 2024, Aerospace 10.3390/aerospace11100830","建筑/城市","单向","有","多旋翼/eVTOL","LES 降阶(POD)","点质量","无","仅摘要",""),
("09","Zhang, Jia, Kikumoto 2026, JWEIA 10.1016/j.jweia.2026.106428","建筑/城市","单向","有?(待核)","小型多旋翼","LES","点质量/多点","风场对风洞?","Crossref 存在;内容未读","与本题最近的风工程期刊先例,须取全文"),
("10","Carreno Ruiz et al. 2022, IEEE CDC 10.1109/CDC51059.2022.9992477","近壁(无来流)","双向","有(PID)","小型多旋翼","URANS","解析叶片/虚拟盘","无","Gemini 读全文","无建筑尾流"),
("11","Carreno Ruiz 2023, PoliTo PhD thesis","近壁(无来流)","双向","有(PID)","小型多旋翼","URANS","解析叶片/虚拟盘","旋翼性能风洞","Gemini 读全文",""),
("12","Carreno Ruiz et al. 2023, AIAA 2023-2272","近壁(无来流)","双向","有(PID)","小型多旋翼","URANS","解析叶片/虚拟盘","无","Crossref",""),
("13","Yang et al. 2025, arXiv 2509.21496","范围外","—","有(MPC)","小型多旋翼","解析吸力模型(非 CFD)","—","飞行试验","Gemini 读全文","不计入数值模拟"),
("14","Zagaglia, Zanotti, Gibertini 2018, AST 10.1016/j.ast.2018.05.019","范围外","—","无","直升机模型","风洞试验","—","—","Crossref","试验基准,不计入数值模拟"),
("15","Visingardi et al. 2017, GARTEUR AG22 综述(ERF)","地面障碍物","双向","无","直升机","URANS/DES/势流 多求解器","致动盘/叶素/解析叶片","风洞(AG22)","仅摘要",""),
("16","Chirico et al. 2017, CEAS AJ 10.1007/s13272-017-0259-y","地面障碍物","双向","无","直升机","URANS(HMB)","致动盘/解析叶片","风洞(PoliMi)","Lead 检索摘要",""),
("17","Gallas et al. 2017, ERF","地面障碍物","双向","无","直升机","URANS/自由尾迹","解析叶片/升力线","风洞","仅摘要",""),
("18","Tan et al. 2019, CEAS AJ 10.1007/s13272-018-0346-8","地面障碍物","双向","无","直升机","涡粒子","叶素/面元","风洞(AG22)","仅摘要",""),
("19","Tan et al. 2020, J Aircraft 10.2514/1.C035629","地面障碍物","双向","无","纵列双旋翼","涡粒子","面元/叶素","风洞","仅摘要",""),
("20","Ventura Diaz & Yoon 2018, AIAA 2018-1266","范围外","—","无","多旋翼","DES","解析叶片","风洞","Gemini 读全文","旋翼-机身干扰,无外部障碍物尾流"),
("21","Caprace, Ventura Diaz, Yoon 2023, AIAA 2023-4281","建筑/城市","双向","无","eVTOL 四旋翼","DDES/涡粒子","解析叶片/致动线","风洞?","Crossref","屋顶边缘悬停(无来流?待核)"),
("22","Alvarez & Ning 2022, FLOWUnsteady AIAA 2022-3218","范围外","—","无","多旋翼/eVTOL","rVPM-LES","致动线/面","风洞","仅摘要","方法参考"),
("23","Alvarez & Ning 2024, J Aircraft 10.2514/1.C037279","范围外","—","无","螺旋桨-机翼","rVPM-LES","致动线","风洞","Lead 读摘要","方法参考"),
("24","Cadieux et al. 2020, NASA LAVA LBM","范围外","—","无","四旋翼","LBM","解析叶片","风洞(声学)","Gemini 读全文","噪声,无障碍物尾流;LBM 方法参考"),
("25","Horvat et al. 2020, AIAA 2020-0539","范围外","单向/双向对比","有","直升机","GPU LBM","叶素/源项","无","仅摘要","飞机尾涡遭遇,非建筑"),
("26","Horvat et al. 2021, AIAA 2021-1827","风电场尾流","双向","有","直升机","GPU LBM","叶素/源项","无","仅摘要",""),
("27","Bludau, Rauleder, Hajek 2021, VFS 77","舰船","双向","有","直升机","GPU LBM","叶素","风场对PIV","Lead 读摘要",""),
("28","Kurban et al. 2022/2025, ERF/VFS","舰船","单向","无","直升机","GPU LBM","—(只流场)","风洞","仅摘要",""),
("29","Ashok et al. 2023, VFS 79","舰船","双向","无","直升机","GPU LBM(IB)","致动盘","风洞","仅摘要",""),
("30","Bludau 2024, TUM PhD thesis","舰船","双向","有(驾驶员/控制器)","直升机","多 GPU LBM","叶素/源项","风洞+飞行","Gemini 读全文","LBM 双向闭环最接近先例,但对象是舰船+直升机"),
("31","Waanders & Rauleder 2026, AIAA 2026-0028","舰船","双向","无","直升机(缩比)","GPU LBM","致动线/致动盘","风洞","Crossref",""),
("32","Waanders 2026, 多旋翼 LBM(GT 页面)","范围外","—","无","多旋翼","GPU LBM","致动盘/线","风洞?","仅个人页","旋翼间干扰"),
("33","Forrest & Owen 2010, Comput Fluids 10.1016/j.compfluid.2009.11.002","舰船","单向(只尾流)","无","直升机","DES","无","风洞/海试","仅摘要",""),
("34","Forrest et al. 2012, J Aircraft 10.2514/1.C031525","舰船","单向","有(驾驶员在环)","直升机","DES","叶素","海试 SHOL","仅摘要",""),
("35","Kääriä 等(Liverpool 舰船尾流,条目被截断)","舰船","未读到","未读到","直升机","DES?","叶素?","?","Gemini 输出截断","待补"),
("36","Liverpool Heliflight-R 舰载仿真综述(Aero J,作者未读到)","舰船","单向","有(驾驶员在环)","直升机","DES","叶素","飞行模拟","仅摘要","待补"),
("37","Bridges, Horn, Alpman, Long 2007, AIAA 2007-6485","舰船","双向(含单/双向对比)","有(驾驶员模型)","直升机","CFD(源项)","致动盘/叶素","无?","仅摘要",""),
("38","Crozon, Steijl, Barakos 2014, J Aircraft 10.2514/1.C032535","舰船","双向","无","直升机","URANS(HMB)","致动盘/解析叶片","?","仅摘要",""),
("39","Oruc, Horn, Shipman, Polsky 2017, IJ Mod Phys/JMM 10.1142/s179396231743005x","舰船","双向","有(驾驶员在环)","直升机","CFD","致动盘","?","仅摘要",""),
("40","Crozon, Steijl, Barakos 2018, Aero J 10.1017/aer.2017.112","舰船","双向","有(飞行动力学配平/控制)","直升机","URANS(HMB)","致动盘","?","仅摘要",""),
("41","Shi, Li, Su, Xu 2020, AST 10.1016/j.ast.2020.106175","舰船","双向","无","多架直升机","URANS","动量源","?","仅摘要",""),
("42","Frassoldati et al. 2022, ERF 48","舰船","单向与双向对比","无","直升机","DDES/SBES","叶素/源项","?","Gemini 读全文",""),
("43","Zong et al. 2025, JMSE 10.3390/jmse13091608","舰船","双向","无","直升机","CFD+VOF","动量源","?","仅摘要",""),
]
import collections,sys
out=sys.argv[1]
L=["# L22.7 综述分类表 v1（Lead 复核，10-19）","",
"来源：Deep Research ec4601（核对见 DR_核对_20261019.md）＋ Gemini 联网扩充 #dd0a0d49（原文 gemini_expansion_raw_20261019.md，表 35–36 条被截断）。标签由 Lead 判定，按工单0204 Gemini 只作文献线索。'?'/'待核' = 未读到原文。",
"范围：外部障碍物（建筑/城市、地面障碍物、舰船上层建筑、风电场尾流）尾流与旋翼飞行器相互作用的**数值**研究；近壁无来流单列；纯试验、旋翼-机身/机翼干扰、解析模型标'范围外'不计入数值统计。","",
"| # | 文献 | 场景 | 耦合 | 闭环 | 尺度 | 流场 | 旋翼 | 验证 | 核实 | 备注 |","|---|---|---|---|---|---|---|---|---|---|---|"]
for r in R: L.append("| "+" | ".join(r)+" |")
inn=[r for r in R if r[2]!="范围外"]
L+=["",f"## 计数（脚本生成，共 {len(R)} 条；计入数值统计 {len(inn)} 条）",""]
def cnt(name,f):
    c=collections.Counter(f(r) for r in inn); L.append(f"- {name}："+"；".join(f"{k} {v}" for k,v in c.most_common()))
cnt("场景",lambda r:r[2])
cnt("耦合",lambda r:"单向" if r[3].startswith("单向") and "双向" not in r[3] else ("双向" if r[3].startswith("双向") else ("单/双向对比" if "对比" in r[3] else r[3])))
cnt("闭环",lambda r:"有" if r[4].startswith("有") and "?" not in r[4] else ("待核" if "?" in r[4] or "未读到" in r[4] else "无"))
cnt("尺度",lambda r:"直升机" if "直升机" in r[5] or "旋翼" in r[5] and "多" not in r[5] else ("eVTOL" if "eVTOL" in r[5] else "小型多旋翼"))
cnt("流场含 LBM",lambda r:"LBM" if "LBM" in r[6] else "非 LBM")
cnt("旋翼含致动线",lambda r:"致动线/升力线" if ("致动线" in r[7] or "升力线" in r[7]) else "其他")
# cross: 场景 x 耦合 x 闭环
L+=["","## 交叉（场景 × 耦合 × 闭环）",""]
c=collections.Counter((r[2],"双向" if "双向" in r[3] else "单向",("有" if r[4].startswith("有") and "?" not in r[4] else ("待核" if ("?" in r[4] or "未读到" in r[4]) else "无"))) for r in inn)
L.append("| 场景 | 耦合 | 闭环 | 篇数 | 编号 |");L.append("|---|---|---|---|---|")
for k,v in sorted(c.items()):
    ids=",".join(r[0] for r in inn if (r[2],"双向" if "双向" in r[3] else "单向",("有" if r[4].startswith("有") and "?" not in r[4] else ("待核" if ("?" in r[4] or "未读到" in r[4]) else "无")))==k)
    L.append(f"| {k[0]} | {k[1]} | {k[2]} | {v} | {ids} |")
open(out,"w",encoding="utf-8").write("\n".join(L)+"\n")
print("\n".join(L[-40:]))
