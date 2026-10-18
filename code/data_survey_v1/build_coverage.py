"""Build A1 dataset coverage report from archived computed summaries."""
import json,collections,datetime,zipfile,re
from pathlib import Path
from check_prague import Remote,URL
P=Path(__file__).parent
pa=[]
for f in ('paris_coverage_2022-06_2023-03.json','paris_coverage_2023-04_2024-03.json'):
    pa.extend(json.loads((P/f).read_text())['monthly'])
pr=json.loads((P/'prague_coverage.json').read_text())['monthly']
with zipfile.ZipFile(Remote(URL)) as z:
    zipcounts=collections.Counter(x.filename[:4]+'-'+x.filename[4:6] for x in z.infolist() if '/Processed_Wind_Profile_' in x.filename and re.match(r'\d{6}',x.filename))
par=lambda m,s,z: next(x for x in pa if x['month']==m and x['station']==s and x['target_agl']==z)
prag=lambda m,z: next(x for x in pr if x['month']==m and x['gate_target_agl']==z)
rows=['| UTC 月 | PALUPD 111m | PAARBO 52m | PAARBO 102m | PAARBO 152m* | PACHEM 104m† | PACHEM 154m* | PASIRT 146m |','|---|---:|---:|---:|---:|---:|---:|---:|']
for m in sorted({x['month'] for x in pa}):
    rows.append('| '+m+' | '+' | '.join(str(par(m,s,z)['valid_hours']) for s,z in [('PALUPD',100),('PAARBO',50),('PAARBO',100),('PAARBO',150),('PACHEM',100),('PACHEM',150),('PASIRT',150)])+' |')
prrows=['| 月（HPL 文件时标；时区未证实） | 处理廓线文件数 | 49.3m 小时 | 101.4m 小时 | 147.8m* 小时 |','|---|---:|---:|---:|---:|']
for m in sorted(zipcounts):
    prrows.append(f"| {m} | {zipcounts[m]} | {prag(m,50)['hours_ge4'] if m in ('2022-04','2022-05','2022-06','2022-07','2022-08','2022-09','2022-10') else 0} | {prag(m,100)['hours_ge4'] if m in ('2022-04','2022-05','2022-06','2022-07','2022-08','2022-09','2022-10') else 0} | {prag(m,150)['hours_ge4'] if m in ('2022-04','2022-05','2022-06','2022-07','2022-08','2022-09','2022-10') else 0} |")
text=f'''# A1 多站数据最小覆盖核验

结论：按“每中心小时至少四个有值廓线”的计数口径，巴黎 PALUPD 与布拉格 PVK 屋顶各有至少连续六个月的 30–150 m 候选门；但两站合格月份不重叠，而且布拉格处理廓线没有可核的逐门 QC 标志、存在异常峰值及时区/屋顶高度歧义，故只可列为**有条件的双城市候选**，尚不可称“已经凑齐经 QC 验证的多城市检验样本”。[1][2][3]

巴黎 L3v1.42：每月 600 s tar 内每日 NetCDF、有限 u/v，实际 AGL = altitude−(station_altitude−station_height)。与前期脚本一致，记录时刻减五分钟后归到最近整点，按月跨日去重，同一中心小时≥4 个不同 10 min 才计有效；风速均值为先均 u/v 后求模。月表格的数字是该门**有值小时数**，不是预报共同配对数、也不是每月覆盖率。脚本读取了 2022-06 至 2024-03 所有月包，月末跨包时刻按小时所在 UTC 月统计。[2]

{chr(10).join(rows)}

* PAARBO 152 m、PACHEM 154 m 实际超出严格 150 m 上界，只作为邻近高度对照，不拿来充当“≤150 m 合格门”。† PACHEM 104 m 的逐月小时平均风仅 0.26–0.50 m/s，而该站 154 m 为 4.39–7.76 m/s；极可能存在低门检索问题，需原始 QC 核查，不能仅凭 finite 判为可信。PAARBO 102 m 在 2023-10 为零；2023-08—2024-02 **不是连续七个月有效**。PALUPD 111 m 在 2023-06—2024-02 有值，2024-02 仅 139 小时；PASIRT 146 m 2022-06—2024-02 长期可用，但为郊区站，不替代市中心站。PARIS L3 的有限值已经经过 L3 处理，本核验没有独立复查 SNR/逐日检索标志。[2]

布拉格 TURDATA：[Zenodo 10655033](https://zenodo.org/records/10655033) 为 CC BY 4.0。远程读取 ZIP 中 `LIDAR_wind_profile_TURDATA_readme.txt`、元数据工作簿及处理后 HPL 头，不下载整包。**廓线只有 PVK roof 一部 lidar**（LDR，50.072588°N、14.428428°E，地面 235 m ASL、仪器架设高度 4.5 m；元数据称 Urban），不是 Legerova 与 Karlov 各有一部激光雷达。Karlov 有地面站与微波辐射计，不可当第二个廓线站。[1][3]

README 称处理后 HPL 三列为高度/风向/风速，测量范围自 8.7 m、门距约 2.9 m；抽检文件有 49.3/101.4/147.8 m。README 将它们称为 AGL，但仪器在 4.5 m 屋顶，是否已加仪器安装高度未由文件头证明：若相对仪器，则对应地面 AGL 约 53.8/105.9/152.3 m；100 m 门不受资格影响，147.8 m 门不列严格≤150 m。处理后的文件未见逐门 SNR/QC 字段；RAW HPL 有 intensity/SNR，却没有做 SNR 重审。2022-04 至 10 按文件名时标（文件与 RAW header 同一时间；实际时区未证实）近整点以“时间−5 min”分配小时，每小时≥4 个数值有限、非负、方向在 0–360° 的处理廓线才计“格式有效”；这**不等于独立 QC 通过**。[1][3]

{chr(10).join(prrows)}

2022-03 是不完整月，未列入连续六个月；2022-04—09 连续六个月 101.4 m 每月 629–744 个“格式有效小时”，10 月另有 608。2022-11 起 HPL 间隔约 33 分钟（RAW header 与文件名样例核对），每小时至多约两个，因而在≥4 的**10 min** 口径下恒为零；0 并不表示整月无观测。2022-04/09 文件间隔可约 8–11 分钟，未严格等间隔 10 min。样例处理值有 49.3 m 超过 50 m/s、个别 147.8 m 超 70 m/s，显然不能把“格式有效”直接当科学 QC；完整逐门物理审查与原始 SNR 验证待做。[3]

## 判定与下步

按照宽松的“有有限处理值、≥4 记录/小时、连续六个月”门槛：PALUPD 111 m（建议 2023-07—2024-01 七个完整月）与布拉格 PVK 101.4 m（建议 2022-04—09 六个月）可组成两城两站**候选**。严格“可信 QC 且同一自然月时段”门槛下凑不齐：两地观测的这两段**没有共同时段**，不能做同期城市间配对；但都位于 GraphCast 2022-01 后，可做异时段的各城市独立预报验证，不把季节与城市效应混同。布拉格处理风的超常大值、标称 33 min 与实际前期 8–11 min 的时标差异、屋顶 AGL 定义、时区须先澄清；失败则优先核 CROCUS，不可据当前表宣布推广成立。[1][2][3]

数据与运行：只在 工作站 用 HTTP Range 获取 TURDATA ZIP 中央目录与所需处理廓线片段；Prague 累计范围请求 {json.loads((P/'prague_coverage.json').read_text())['bytes_fetched']/1e6:.1f} MB（含中央目录）；巴黎月包流式内存处理 {sum(x['bytes'] for f in ('paris_coverage_2022-06_2023-03.json','paris_coverage_2023-04_2024-03.json') for x in json.loads((P/f).read_text())['archives'])/1e6:.1f} MB，没在 工作站 保存月度原包。本次没有使用 Colab、HPC，0 CU。可复核原始汇总：`prague_coverage.json`、`paris_coverage_2022-06_2023-03.json`、`paris_coverage_2023-04_2024-03.json`；脚本 `check_prague.py`、`check_prague_metadata.py`、`count_prague.py`、`check_paris.py`、`build_coverage.py`。
'''
(P/'coverage_check.md').write_text(text)
print('written',P/'coverage_check.md','Paris rows',len(rows)-2,'Prague rows',len(prrows)-2)
