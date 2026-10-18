"""Write complete soundings comparison from verified profile and RAOB JSONL."""
import csv,json
from pathlib import Path
root=Path(__file__).parent
models=[json.loads(x) for x in (root/'soundings_raw.jsonl').read_text().splitlines()];obs={x['event_id']:x for x in map(json.loads,(root/'raob_full.jsonl').read_text().splitlines())}
events={x['event_id']:x for x in csv.DictReader((root/'events.csv').open())}
assert len(models)==len(obs)==len(events)==7 and all(x['status']=='ok' for x in models)

def triplet(r,key):
    o=obs[r['event_id']]
    if key=='shear06' and o['n_wind']<5:return f"{r['ai'].get(key,'—')}/{r['hrrr'].get(key,'—')}/—(观测风层{ o['n_wind'] }个)"
    return '/'.join(str(z.get(key,'—')) for z in (r['ai'],r['hrrr'],o))
lines=['# 同批事件探空核对','','数据源：IEM 公开 RAOB JSON（逐例 URL 见 `raob_full.jsonl`）；AI 用 StormCast V1 的 HRRR 混合层，HRRR 业务同起报+3h 的混合层；初值 HRRR 99 场，AI 外条件为事后 ARCO ERA5。原始探空 `raob_raw.json`，计算程序 `soundings.py`、`raob_full.py`，日志 `soundings_full.log`、`raob_full.log`。','',
'站点取 2024 年后仍报告且最近的 IGRA 站（`events.csv` 含站点坐标和与 ASOS 距离）；探空取距 ASOS 峰值最近的 00/12Z，可能在峰值之后，绝不冒称同分钟实测。AI/HRRR 起报同为探空时刻前3h，模式在探空站最近格点取廓线。','',
'计算定义：MetPy most_unstable_cape_cin（最不稳定气块，MUCAPE），downdraft_cape（DCAPE），bulk_shear（观测站首个有风层起 0–6km 的矢量差模）；温湿以 p/t/q 换算露点，风速风向对 RAOB 换算 u/v；压力/高度 QC、去重。模式层有14个可用完整层，仅到约 440hPa；观测 MUCAPE/DCAPE 用完整可用温湿层到 100hPa，纵深不同，不可直接做无偏误差归因。RAOB 温湿和风分别利用有效层，不强行只取同时有五要素的少数层。','',
'|事件/探空站/探空 UTC|距 ASOS km|层数 AI/HRRR/RAOB温湿/RAOB风|MUCAPE AI/HRRR/RAOB J/kg|DCAPE AI/HRRR/RAOB J/kg|0–6km 切变 AI/HRRR/RAOB m/s|','|---|---:|---|---|---|---|']
for r in models:
    eid=r['event_id'];e=events[eid];o=obs[eid]
    lines.append(f"| {eid} {r['raob_station']} {r['raob_utc'][:16]} | {e['raob_distance_km']} | {r['ai']['n']}/{r['hrrr']['n']}/{o['n_thermo']}/{o['n_wind']} | {triplet(r,'mucape')} | {triplet(r,'dcape')} | {triplet(r,'shear06')} |")
lines+=['','质量与解释：KDVN 2024-05-21 12Z 探空只有3个可用风层，0–6km 观测风切标为缺失，不用 MetPy 少点插值结果作证据。KLMN 2023-06-18 00Z 只有9个温湿层，MUCAPE/DCAPE 不稳定；KOAX 2023-07-12 12Z 在峰值后，不能作为先验。混合层最高仅约440hPa 且地形决定低层取样，MUCAPE/DCAPE 与完整 RAOB 非同层厚；若要定量审查需统一截断、相同温度/比湿的垂向插值并测敏感性。','',
'本轮探空只作为伴随物理环境诊断，不进入已固定的地面强风通过门槛。来源：Iowa Environmental Mesonet RAOB API https://mesonet.agron.iastate.edu/json/raob.py?help= ，NOAA IGRA2 站表 https://www.ncei.noaa.gov/pub/data/igra/igra2-station-list.txt ，NOAA AWS HRRR，Copernicus ERA5/ARCO，NVIDIA StormCast V1。']
(root/'soundings.md').write_text('\n'.join(lines)+'\n')
print('soundings rows',len(models),'RAOB sources',len(obs))
