"""Audit 26 independent Colab replays against frozen B stop metrics."""
from pathlib import Path
from collections import defaultdict
import tarfile,json,statistics,hashlib,math
H=Path(__file__).resolve().parent
T=H/'a3_v4c_26_metrics_1015.tar.gz'
with tarfile.open(T) as t:
 files={m.name:json.load(t.extractfile(m)) for m in t.getmembers() if m.isfile()}
assert len(files)==29 and files['completion.json']=={'expected':26,'success':26,'failed':[],'missing':0}
old=json.loads((H/'metrics_B_stop.json').read_text());fields=old['fields'];prior=old['rows']
legacy={(r['case'],r['seed'],r['group']):r for r in prior if r['runroot'].startswith('./')}
assert len(legacy)==26
manifest=files['manifest.json'];assert len(manifest)==26
new={};details=[];hashes=files['wind_hashes.json']
for row in manifest:
 key=(row['case'],row['seed'],row['group']);assert key in legacy and key not in new
 fn=f'{key[0]}_s{key[1]}_{key[2]}.json';r=files[fn];assert r['returncode']==0
 assert r['wind_bts_sha256']==hashes[f'{key[0]}_s{key[1]}']['wind_bts_sha256']
 new[key]=r
 prev=legacy[key];delta={f:r['metrics'][f]-prev['metrics'][f] for f in fields}
 details.append(dict(case=key[0],seed=key[1],group=key[2],wind_bts_sha256=r['wind_bts_sha256'],old_metrics=prev['metrics'],recomputed_metrics=r['metrics'],delta_new_minus_old=delta,trigger_delta_s=r['trigger_abs_s']-prev['trigger_abs_s'],event_window_replay=r['event_window_abs_s'],event_window_old=prev['event_window_abs_s']))
assert set(new)==set(legacy)
changed=[r for r in details if any(not math.isclose(v,0.,abs_tol=1e-9) for v in r['delta_new_minus_old'].values()) or abs(r['trigger_delta_s'])>1e-9 or r['event_window_replay']!=r['event_window_old']]
raw=T.read_bytes();audit=dict(version='v4c',source_bundle='a3_b_colab_bundle_1014.tar.gz',replay_tar_sha256=hashlib.sha256(raw).hexdigest(),expected=26,recomputed=26,seven_fields=fields,changed_count=len(changed),wind_hashes=hashes,rows=details)
(H/'metrics_B_v4c_audit_20261015.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
lines=['# A3-B 旧 26 个停机工况 Colab 独立重算（v4c）','',f'同输入包重生四个种子风盒并补 14 帧/7 s，逐风盒 SHA-256 及全部 26×7 项旧/新值和差值见 metrics_B_v4c_audit_20261015.json；成功 {len(new)}/26，七指标或触发/窗口有差异 {len(changed)}/26。','', '|种子|补帧后 wind.bts SHA-256|字节|','|---:|---|---:|']
for key,z in hashes.items():lines.append(f"|{key}|`{z['wind_bts_sha256']}`|{z['bytes']}|")
lines+=['','每个控制组以同种子的独立风盒运行，风盒哈希按种子共享，不是 26 个不同风盒。旧原始风盒已不可读，哈希仅认证 Colab 新生成物；不能声称与旧原始文件逐字节一致。所有数值逐项比对来自保存的 metrics_B_stop.json。']
if changed:
 lines+=['','有不一致：以 v4c 重算 26 条替换旧值，仅在新文件重算 B 判据（不覆盖既有 RESULTS_B_stop/metrics_B_stop）。']
 merged={(r['case'],r['seed'],r['group']):r['metrics'] for r in prior}
 for key,r in new.items():merged[key]=r['metrics']
 gates={}
 for case in ('I_near','III_offset'):
  reduce={f:statistics.median([100*(merged[(case,s,'G1_instant')][f]-merged[(case,s,'G2_real_1D')][f])/merged[(case,s,'G1_instant')][f] for s in old['seeds']]) for f in ('tower_top_yaw_absmax_kNm','blade1_root_flapwise_negative_magnitude_kNm','tower_resultant_max_kNm')}
  gates[case]=dict(reductions_pct=reduce,passes=(reduce['tower_top_yaw_absmax_kNm']>=10 or reduce['blade1_root_flapwise_negative_magnitude_kNm']>=10) and reduce['tower_resultant_max_kNm']>=-5)
 (H/'metrics_B_v4c_corrected_gates_20261015.json').write_text(json.dumps(gates,indent=2)+'\n')
 lines+=['',json.dumps(gates,ensure_ascii=False,indent=2)]
else:
 lines+=['','七项指标、触发时刻与事件窗口全部一致。因此 96 个停机工况可逐项审计：其中旧 26 条以 Colab v4c 独立重算并逐项校验，另外 70 条为原 Colab 续跑记录。既有六种子判据数值不变，无需更正；仍限于合成场、离线停机重放，不等于在线验证。']
lines+=['','再现环境：OpenFAST 5.0.0、ROSCO 2.10.6 修改版（前馈增益 0），Colab CPU high-memory 单会话；输入 a3_b_colab_bundle_1014.tar.gz，执行脚本 colab_recompute_v4c_20261015.py。原始大输出不回传 工作站。','']
(H/'RESULTS_B_v4c_audit_20261015.md').write_text('\n'.join(lines))
print(json.dumps({'recomputed':len(new),'changed':len(changed),'max_abs_delta_by_field':{f:max(abs(r['delta_new_minus_old'][f]) for r in details) for f in fields},'tar_sha256':audit['replay_tar_sha256']},indent=2))
