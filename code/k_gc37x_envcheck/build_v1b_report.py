import json,pathlib,hashlib
base=pathlib.Path(__file__).parent
raw=json.loads((base/'VALIDITY_GATE_v1b_raw_20261127.json').read_text())
remote='/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x/envcheck_v1'
script=base/'envcheck_gc37x_v1b.py'
h=hashlib.sha256(script.read_bytes()).hexdigest()
lines=['# R23.4c envcheck v1b 有效性闸（2026-11-27 美东）','',
'总判：未通过。内容坏例可被检测，N1 对照未误报，但 may4 已知答案五项相对差全部 >1%；不能用于正式样本。方法卡和 v1 原件不动；无 IGRA2/RAP 下载或正式样本运行。','',
f'CRC 脚本：`{remote}/envcheck_gc37x_v1b.py`；工作站 副本：`{script}`；两处 SHA-256 `{h}`。',
'CRC 资源方式：复用 超算 既有 SSH ControlMaster，在前端做小规模只读诊断及夹具运行；没有提交作业、没有调度器输出或 rc-job 回执。MetPy 版本运行时原文：`MetPy version: 1.6.3`。',
'', '## 已知答案：真实地面层直接 MetPy vs profile 全路径',
'探空 `may4_sounding.txt` SHA-256 `b3a7c3ee4b1bdb1e1961492265c23f42947dc627156cfacb5fdebac0ad0b4350`；SOILHGT=345 m、真实地面气压 959 hPa。profile 严格筛选地上层（排除真实地面层），重新对 GHT–ln(p) 插值计算 ps，100 hPa 截顶；直接 MetPy 保留原始地面层。探空实测最高约 268.6 hPa，因此本例积分实际受观测顶限制，未达到100 hPa。','',
'指标 | profile | 直接 MetPy | 相对差（%）','---|---:|---:|---:|',
'MLCAPE (J/kg) | 2105.261783650429 | 2148.0641544092714 | 1.992602067819204',
'MUCAPE (J/kg) | 2324.218997568475 | 2410.148979183887 | 3.565339004251483',
'SHEAR06 (m/s) | 26.99736897416307 | 21.35709985311645 | 26.409340031360057',
'SRH01 (m²/s²) | 105.65448868578771 | 237.81653991783458 | 55.57311164215438',
'SRH03 (m²/s²) | 189.71594095870626 | 323.0173640167214 | 41.26757193496094','',
'判据五项分别 ≤1%，实际 `"pass": false`。原因包括删除真实地面层导致近地面热力缺口和线性外推的地面风与观测风不同；MetPy Bunkers 风层及 SRH 对底层差敏感。没有调参凑门槛。',
'31 标准层诊断（不判）：MLCAPE=2179.814427366905、MUCAPE=2437.1144830885487 J/kg；SHEAR06=20.592615627073943 m/s；SRH01=207.24739209439903、SRH03=294.17218105273935 m²/s²。严格说无法从仅至268.6 hPa的探空向100–1 hPa“插值”；超观测区温湿风边界保持、高度 log(p) 外推，结果不是独立真值。','',
'## 重签夹具：同一 CLI 的原始输出',
'每个 `_v1b.json` REPORT 包含对应文件真实 SHA，先通过 SHA 入样闸；命令使用 `--force-t0-gate-test --max-points 1`，坏场检测仍检查全网格/全评估框。下列 `SCRIPT_EXIT=0` 是脚本返回分类，不代表坏例有效。','']
for row in raw['fixtures']:
    case=row['case'];d=row['output']; lines+= [f'CASE={case}；REPORT=`{row["report"]}`（SHA-256 `{row["report_sha256"]}`）',
'MetPy version: 1.6.3',json.dumps(d,ensure_ascii=False), 'SCRIPT_EXIT=0','']
lines += ['对照副本为有效，五项 X99 见上方原始 JSON；三坏例分别为湿度常值、TT NaN、UU 600 hPa 反转，由内容触发 `删失（坏场）` 而非 sha 不符。','',
'## N1 全部 AI/GFS 中间文件的新场级 QC 清单',
'范围：3 个起报周期 × AI/GFS 全部现存 6 h 中间文件，共 60 个；包括 +6 h 后。每行 UU/VV 是评估框内全部相邻压力层格点 Pearson 相关的最小值，允许高空负值；内部 300–975 hPa 层与上下两层均负才触发。每个文件 1294 格、QC 均 PASS，误触发 0。',
'源 / cycle / valid | min UU | min VV | QC','---|---:|---:|---|']
for row in raw['fields']:
    p=pathlib.PurePosixPath(row['file']); parts=p.parts
    descriptor=f'{parts[-3]} / {parts[-2]} / {p.name}'
    c=row.get('min_adjacent_correlation',{})
    lines.append(f'{descriptor} | {c.get("UU",float("nan")):.6f} | {c.get("VV",float("nan")):.6f} | {row["qc"]}')
lines += ['',f'原始机器记录 CRC：`{remote}/VALIDITY_GATE_v1b_windfix_raw_20261127.json`；工作站：`{base}/VALIDITY_GATE_v1b_raw_20261127.json`；SHA-256 `8ec306f090cfb9530534eed188f311d5472e1cbf29544aeb0bc8fbd9a5d311a9`。',
'阈值、底层外推、越界告警 traceback 与未消除的风险见 `IMPLEMENTATION_NOTES.md`；CRC raw 执行日志 `VALIDITY_GATE_v1b_windfix_20261127.log`。']
out=base/'VALIDITY_GATE_v1b_20261127.md'
if out.exists():raise FileExistsError(out)
out.write_text('\n'.join(lines)+'\n')
print(out,len(raw['fields']),sum(r['qc']!='pass' for r in raw['fields']),hashlib.sha256(out.read_bytes()).hexdigest())
