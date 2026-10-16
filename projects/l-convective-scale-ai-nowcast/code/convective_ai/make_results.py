"""Aggregate measured 7x4 results, fixed verification windows, no invented rows."""
import csv,json,statistics,math,html
from pathlib import Path
ROOT=Path(__file__).parent
rows=[json.loads(s) for s in (ROOT/'metrics.jsonl').read_text().splitlines()]
events=list(csv.DictReader((ROOT/'events.csv').open())); meta={e['event_id']:e for e in events}
ids={(r['id'],r['lead_h']) for r in rows if r['status']=='ok'}
expected={(e['event_id'],lead) for e in events for lead in (1,2,3,6)}
if ids!=expected:raise ValueError(f'incomplete: {len(ids)}/{len(expected)}, missing={sorted(expected-ids)}, errors={[r for r in rows if r["status"]!="ok"]}')
assert len(rows)==len(ids), 'duplicate or failed rows require manual adjudication'
rows.sort(key=lambda r:(r['peak_utc'],r['station'],r['lead_h']))

def ratio(r,model):return model['wide']['value_ms']/(r['obs_kt']*.514444)

def fmt(r,key,kind='wide'):
    a=r[key][kind];return '—' if not a else f"{a['value_ms']:.1f}/{a['value_ms']/(r['obs_kt']*.514444):.2f}"

out=['# 对流尺度 AI 地面强风：冻结试验结果','',f'样本：{len(events)} 个 NCEI 雷暴大风 ASOS 事件、{len(rows)} 组（每事件 1/2/3/6h）。原始逐组结果 `metrics.jsonl`；原始 Colab 日志 `batch_full.log`；输入事件 `events.csv`。','',
'## 判据与限制','',
'ASOS 峰值来自 NOAA Storm Events 的 MG/ASOS，IEM 同站 METAR 的 gust/PK WND 交叉核对；1kt=0.514444m/s。峰值时刻以 NCEI 事件时间为准（IEM PK WND 同分钟或数分钟内，events.csv 的 IEM「报告有效时刻」并不总是物理峰值分钟）。时间为 UTC，回复中的操作时间为美东。',
'以 ASOS 站点为中心，预测格点最大合成 10m 风：宽窗半径25km、峰值±1h；窄窗半径10km、峰值±0.5h。按最近 UTC 整点选择验证中心，起报为中心减1/2/3/6h；宽窗和窄窗均对模型及基线同样应用。位置偏差为最大风格点距站点，时间偏差为该时次与 NCEI 峰值之差。持久性取同起报 HRRR 分析的10m风25km最大值。',
'注意：ASOS 是短时阵风，StormCast 输出是 10m 水平风，不是阵风；不能将无阵风的模型结果宣称为阵风技巧。HRRR GUST 单列，HRRR 10m水平风作为同量比较。模型以 HRRR 99场初始化、但用事后 ERA5 条件（模型训练匹配、非纯业务可用输入）；因此这里是回报，不是业务预报。随机扩散单成员未固定噪声种子，复跑峰值可能变化。',
'','## 每事件、每起报结果','',
'表内「AI/HRRR10/GUST」为宽窗最大风速 m/s 与其对 ASOS 峰值的比（`风速/峰值比`）；窄窗一列为 AI/HRRR10/GUST 最大值 m/s；25.7m/s 命中按宽窗判。','',
'| NCEI ID/站/观测峰值 | 提前量/起报 UTC | AI 宽窗 | HRRR10 宽窗 | HRRR GUST 宽窗 | AI/HRRR10/GUST 窄窗 m/s | AI时差min/距km | AI/HRRR10/GUST ≥25.7 | 分析持续性m/s | 单组墙钟s/峰显存GB |','|---|---|---:|---:|---:|---|---|---|---:|---:|']
for r in rows:
    a=r['ai']['wide'];hs=r['hrrr_speed']['wide'];hg=r['hrrr_gust']['wide'];p=r['persistence']['value_ms']
    s=meta[r['id']]
    narrow='/'.join(f"{r[k]['narrow']['value_ms']:.1f}" if r[k]['narrow'] else '—' for k in ('ai','hrrr_speed','hrrr_gust'))
    hits='/'.join('是' if r[k]['wide']['value_ms']>=25.7 else '否' for k in ('ai','hrrr_speed','hrrr_gust'))
    out.append(f"| {r['id']} {r['station']} {r['obs_kt']:.0f}kt | {r['lead_h']}h {r['init_utc'][:16]} | {fmt(r,'ai')} | {fmt(r,'hrrr_speed')} | {fmt(r,'hrrr_gust')} | {narrow} | {a['time_bias_min']:+.0f}/{a['distance_km']:.1f} | {hits} | {p:.1f} | {r['runtime_sec']:.0f}/{r['gpu_peak_gb']:.1f} |")

out+=['','## 预定闸门核对','']
for lead in (1,2,3,6):
    subset=[r for r in rows if r['lead_h']==lead]
    ar=[ratio(r,r['ai']) for r in subset];hr=[ratio(r,r['hrrr_speed']) for r in subset];gr=[ratio(r,r['hrrr_gust']) for r in subset]
    out.append(f"{lead}h：AI 峰值比中位 {statistics.median(ar):.2f}，HRRR10 {statistics.median(hr):.2f}，HRRR GUST {statistics.median(gr):.2f}；AI/HRRR10 比的中位 {statistics.median(a/h for a,h in zip(ar,hr)):.2f}；AI ≥25.7 有 {sum(r['ai']['wide']['value_ms']>=25.7 for r in subset)}/{len(subset)}，HRRR GUST 有 {sum(r['hrrr_gust']['wide']['value_ms']>=25.7 for r in subset)}/{len(subset)}。")
better=set()
for eid in meta:
    subset=[r for r in rows if r['id']==eid]
    n=sum(abs(ratio(r,r['ai'])-1)<abs(r['persistence']['value_ms']/(r['obs_kt']*.514444)-1) for r in subset)
    if n>=3:better.add(eid)
    out.append(f"事件 {eid}：AI 对观测的绝对峰值比误差优于同起报持久性 {n}/4 组；≥3/4 才计为该事件优于持续性。")
worst=max(r['runtime_sec'] for r in rows)
out.append(f"本样本优于持续性事件数 {len(better)}/{len(events)}（门槛 ≥2/3）；单次最长端到端墙钟 {worst:.0f}s，包含数据下载、推理与基线，不等同纯 GPU 前向，但低于10 GPU分钟上界。假定独立起报、同速率，100事件×4起报约 {sum(r['runtime_sec'] for r in rows)/len(events)*100/3600:.1f} GPU墙钟小时（还不含探空处理、失败重试、排队；共享缓存/批量可减少）。")
out.append('')
out.append('数据：NOAA NCEI Storm Events 年度 CSV，Iowa Environmental Mesonet ASOS，NOAA AWS HRRR 分析/预报，Copernicus ERA5 经 ARCO，NVIDIA StormCast V1/Earth2Studio；具体 URL/版本与许可见 `models.md`、`events.csv`、`PUBLIC_CITATIONS.md`。')
(ROOT/'results.md').write_text('\n'.join(out)+'\n')
# Lightweight vector chart, with truthful source caption; one point per model/event/lead.
W,H=1100,700; parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<rect width="100%" height="100%" fill="white"/>','<text x="40" y="35" font-size="20">ASOS thunderstorm gust vs 10m wind (7 events; 1/2/3/6h)</text>']
for lead in (1,2,3,6):
    subset=[r for r in rows if r['lead_h']==lead]; x0=55+(lead==2)*255+(lead==3)*510+(lead==6)*765
    parts+= [f'<text x="{x0}" y="70" font-size="16">Lead {lead}h</text>',f'<line x1="{x0}" y1="360" x2="{x0+190}" y2="360" stroke="#555"/>']
    for i,r in enumerate(subset):
        y=95+i*37;obs=r['obs_kt']*.514444
        parts.append(f'<text x="{x0}" y="{y+5}" font-size="11">{html.escape(r["station"])} {r["id"][-4:]}</text>')
        for j,k,color in ((0,'ai','#2368a2'),(1,'hrrr_speed','#dc8027'),(2,'hrrr_gust','#4b9b66')):
            val=r[k]['wide']['value_ms']/obs
            xx=x0+78+min(val,1.8)*60
            parts.append(f'<circle cx="{xx:.1f}" cy="{y+j*6-5}" r="2.8" fill="{color}"/>')
    parts.append(f'<line x1="{x0+78+60}" y1="80" x2="{x0+78+60}" y2="365" stroke="#999" stroke-dasharray="3 3"/>')
parts.append('<text x="55" y="405" font-size="14" fill="#2368a2">● StormCast 10m</text><text x="250" y="405" font-size="14" fill="#dc8027">● HRRR 10m</text><text x="410" y="405" font-size="14" fill="#4b9b66">● HRRR GUST</text>')
parts.append('<text x="45" y="665" font-size="12">Sources: NOAA Storm Events; IEM ASOS; NOAA AWS HRRR; Copernicus ERA5/ARCO; NVIDIA StormCast V1. Dashed line = forecast/observed 1.0.</text></svg>')
(ROOT/'peak_ratio.svg').write_text('\n'.join(parts))
print('verified',len(ids),'rows',len(events),'events','results.md','peak_ratio.svg')
