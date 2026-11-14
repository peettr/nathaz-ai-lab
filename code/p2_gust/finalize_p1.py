#!/usr/bin/env python3
"""Write final P1 manifest and report from retrieved blind data, without scoring."""
import csv,datetime as dt,hashlib,json,pathlib,subprocess,sys,collections
R=pathlib.Path(__file__).resolve().parent
s=json.loads(subprocess.check_output([sys.executable,str(R/'summarize_p1.py')],text=True))
f=json.loads((R/'freeze_manifest.json').read_text());p=json.loads((R/'pair_manifest_final.json').read_text())
a=dt.datetime.fromisoformat('2026-11-11T10:46:13-05:00');b=dt.datetime.fromisoformat('2026-11-11T18:37:49-05:00');hours=(b-a).total_seconds()/3600
# Prior observed CPU session rate ~0.08 CU/h; account usage contains another L4 assignment.
manifest={'raw_path_on_terminated_vm':'/content/p1/pairs_p2.csv','raw_bytes':p['pairs_bytes'],'raw_sha256':p['pairs_sha256'],'local_archive':str(R/'pairs_p2.csv.gz'),'archive_bytes':(R/'pairs_p2.csv.gz').stat().st_size,'archive_sha256':s['archive_sha256'],'rows':s['pairs_rows'],'station_sha256':f['station_sha256'],'restore_command':'gzip -dc pairs_p2.csv.gz > pairs_p2.csv (only after checking destination does not exist)','note':'CSV exceeded 200 MB; gzip small archive downloaded and verified by streaming decompression before Colab stop.'}
(R/'pairs_p2_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
missing=[]
for line in (R/'archive_availability.jsonl').open():
 x=json.loads(line)
 if x['status']!=200:missing.append(f"{x['source']} {x['init_utc']} HTTP {x['status']}")
status=s['status'];fields=s['field_counts'];sources=['FOUR_v200_GFS','GRAP_v100_GFS','PANG_v100_GFS','GFS'];seasons=['2022-10-01—2023-03-31','2023-10-01—2024-03-31','2024-10-01—2025-03-31']
def v(d,src,i,k):return d.get(str((src,i)),{}).get(k,0)
rows=[]
for i,season in enumerate(seasons,1):
 for src in sources:
  n=v(fields,src,i,'rows');ok=v(fields,src,i,'uv10');obs=v(fields,src,i,'obs_complete');pairs=v(fields,src,i,'paired_uv10_obs');gust=v(fields,src,i,'gust');m5=v(fields,src,i,'m5');avail=s['availability'].get(str((src,i)),{}) if src!='GFS' else {'200':'未作归档 HEAD；按成功取数计'}
  rows.append(f"| {season} | {src} | {avail.get('200',0)} / {sum(z for z in avail.values() if isinstance(z,int)) if src!='GFS' else '—'} | {obs}/{n} ({obs/n:.2%}) | {ok}/{n} ({ok/n:.2%}) | {pairs}/{n} | {gust}/{n} | {m5}/{n} |")
cat=[]
for src in sources:
 cat.append({'dataset':src,'source':'https://noaa-oar-mlwp-data.s3.amazonaws.com/' if src!='GFS' else 'https://noaa-gfs-bdp-pds.s3.amazonaws.com/','periods':seasons,'field_source_sha256':hashlib.sha256((R/('stage2_gfs.py' if src=='GFS' else 'stage2_aiwp.py')).read_bytes()).hexdigest(),'derived_pairs_archive_sha256':s['archive_sha256'],'license':'未从源端独立核验许可；本地仅作研究取数，后续分发需查证许可'})
cat += [{'dataset':'MeteoSwiss SwissMetNet 10-minute observations','source':'https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/','periods':seasons,'field_source_sha256':f['station_sha256'],'derived_pairs_archive_sha256':s['archive_sha256'],'license':'未独立核验许可；不据此授权再分发'}, {'dataset':'WMO OSCAR station metadata','source':'https://oscar.wmo.int/surface/rest/api/wmd/download/<station_wigos_id>','periods':seasons,'field_source_sha256':hashlib.sha256((R/'oscar_height_metadata.csv').read_bytes()).hexdigest(),'license':'未独立核验许可；不据此授权再分发'}]
(R/'dataset_catalog_p1.json').write_text(json.dumps(cat,indent=2,ensure_ascii=False)+'\n')
text=f'''# R23.2d P1 检验床取数报告（盲取数，不评分）

## 冻结与范围
站表冻结于 {f['freeze_time_eastern']}（US-Eastern）；{f['selected']} 站，山脊 {f['counts']['ridge']}、山口 {f['counts']['pass']}、谷底 {f['counts']['valley']}、高原 {f['counts']['plateau']}、平原 {f['counts']['plain']}。山口不足 8 站，全部保留 5 站；第一阶段 12 站保留。站表 SHA-256 `{f['station_sha256']}`，在取预报前冻结。候选 {f['candidates']}，符合观测资格 {f['eligible']}；其余筛选详见 inventory_all.json 和 stage1_inventory.py。三冷季均可取数，无 NOAA AIWP 冷季缺失超过 20% 的情况。OSCAR 逐站测风传感器高度及部署起始日存 oscar_height_metadata.csv：覆盖 {s['oscar'].get('verified_full_period',0)}/{f['selected']}（按完整检验期有效的解析标准），不填默认 10 m。

## 可得性与配对完整率
分母为该冷季站×起报×提前量且有效时刻仍在冷季的全部行；观测为六条十分钟值齐全，均风取平均、1 秒阵风取最大，3 秒阵风另存最大。每季起报计划数：第一季 364、第二季 366、第三季 364。FOUR 10/100 m、GRAP/PANG 10 m、GFS 10 m 与 surface GUST；M5 V1、模式地形、Δz 来自 GFS 层插值。以下只报告字段/联合可用数，不计算误差、命中或技巧。

| 冷季 | 来源 | AIWP HTTP 200 / 起报计划 | 六条观测齐 / 行 | u/v10 齐 / 行 | 观测+u/v10 齐 / 行 | GUST 齐 / 行 | M5 三字段齐 / 行 |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

来源状态日志：AI 成功/跳过/失败按来源和冷季见 forecast_progress_final.jsonl；GFS 见 gfs_progress_final.jsonl。跳过是第一批 pilot 已成片，不计失败。两处实际失败：{s['issues'][0][0]} {s['issues'][0][1]}（HTTP 503），{s['issues'][1][0]} {s['issues'][1][1]}（GRIB Ni/Nj 键缺失）。均不超过单源 5% 停线；没有为此重启整批进程。GFS 已成功时次的 GUST 全部齐全；不存在整季 GUST 不可得的情况。逐来源缺失整片：{p['missing_object_counts']}。AIWP 原始归档缺失（HTTP 404）清单：
{chr(10).join('- '+x for x in missing)}

## 配对保存和复核
按冻结站表及固定时次写 {s['pairs_rows']} 行；原始 CSV {p['pairs_bytes']} bytes（大于 200 MB），故仅在本机保留小于 200 MB 的 `pairs_p2.csv.gz` 和 `pairs_p2_manifest.json`；后者给出原 CSV SHA-256 `{p['pairs_sha256']}`、压缩文件 SHA-256 `{s['archive_sha256']}`。压缩档拉回后已在本机流式解压验原始哈希和长度，通过后才停止会话。`pair_manifest_final.json` 为远端构建记录；解压只在确认目标不存在时进行，避免覆盖既有结果。字段定义见 build_pairs.py；空值是未取到而非零。原始预报分片留在已停止的短暂 Colab VM，不能将该 VM 当永久归档；本地压缩表保全全部最终配对值。数据集目录及来源/许可核验状态见 dataset_catalog_p1.json；许可尚未独立核实，不将本报告视为再分发许可。

## 资源与会话
仅一个获批 CPU 会话 `r232d-p1-1111`，分配 US-Eastern {a.isoformat()}，`colab stop` 于 {b.isoformat()} 返回 Session terminated，分配时长 {hours:.3f} h（≤批准后的 16 h）。随后私有和全局 `sessions` 都只列出另一个不属于本任务的 L4 GPU，均不再列本 CPU 会话。停止前账户用量余额 1105.46 CU、账户速率 2.02 CU/h、2 个活跃分配，故该账户速率不能归到本任务；按早先 CPU 约 0.08 CU/h 和分配时长估算本会话约 {hours*0.08:.3f} CU（非独立账单，实际单会话账单未取得），低于 6 CU 先停/8 CU 上限。0 SU。未改只读源文件，未算任何预报评分。

## 脚本与局限
stage1_inventory.py、stage1_oscar.py、stage2_aiwp.py、stage2_gfs.py、build_pairs.py 为实际运行脚本；archive_p1_remote.py、cutoff_p1.py 为停线保全辅助脚本（未执行归档/停线），summarize_p1.py 和 finalize_p1.py 用于本地无评分校验与报告。每个 GFS 起报中 GUST 数据和 M5 特征的可用性以实际字段为准。少量缺失时次仍以空值保留，不补季节、不评分。许可资料未独立核验；OSCAR 的可用高度是 XML 中完整跨期部署的严格解析结果，非对实际仪器状态的外部复测。
'''
(R/'P1_report.md').write_text(text)
print(json.dumps({'report':str(R/'P1_report.md'),'manifest':str(R/'pairs_p2_manifest.json'),'catalog':str(R/'dataset_catalog_p1.json'),'rows':s['pairs_rows'],'missing_404':len(missing),'hours':hours},ensure_ascii=False))
