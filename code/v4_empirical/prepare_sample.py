#!/usr/bin/env python3
"""Freeze explicit s2b 48h paired station roster from scored rows and v1 QC."""
import csv
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
EVENTS=('BERYL','DEBBY','DELTA','FRANCINE','HELENE','IAN','MILTON','NICOLE','ZETA')
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def main():
 scored=read(BASE/'s2/s2b/final/station_comparison.csv')
 v1={(r['event'],r['station']):r for r in read(BASE/'v1/run2/station_rows_v1.csv')}
 b={(r['event'],r['station']):r for r in scored if r['chain']=='b' and r['nominal_lead_h']=='48' and r['reason']=='eligible' and r['event'] in EVENTS}
 c={(r['event'],r['station']):r for r in scored if r['chain']=='PANG' and r['nominal_lead_h']=='48' and r['reason']=='eligible' and r['event'] in EVENTS}
 assert len(b)==len(c)==22 and set(b)==set(c)
 rr=[]
 for k in sorted(v1):
  r=v1[k];ev,st=k
  if ev in EVENTS and k in b:
   assert r['reason']=='eligible' and float(r['obs_s_kt'])==float(b[k]['obs_s_kt'])==float(c[k]['obs_s_kt'])
   reason='保留：v1 eligible，OFCL/Pangu 48h 完整窗口，同一固定 sknt 观测峰';status='include'
  elif ev=='NICHOLAS':reason='剔除：48h 同起报无 OFCL，官方不可评';status='exclude'
  elif ev in EVENTS:reason='剔除：v1 '+r['reason']+'，不进入 s2b eligible 主样本';status='exclude'
  else:reason='剔除：48h 未进入 s2b 两链同质可评事件';status='exclude'
  rr.append(dict(event=ev,station=st,status=status,reason=reason,v1_reason=r['reason'],sknt_valid=r['sknt_valid'],obs_s_kt=r['obs_s_kt']))
 assert sum(x['status']=='include' for x in rr)==22
 with (OUT/'sample_list.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,rr[0]);w.writeheader();w.writerows(rr)
 (OUT/'sample_rules.md').write_text('''# v4 固定样本规则（先于风场计算）\n\n来源：s2/s2b/score_s2b.py 第19–27、46–59、85–109行；s2/chain_b_s2a.py 第91–114行；v1/chain_a_v1.py 第70–90、98–103行；s2/PREREG_s2b.md 第5–10行。\n\n1. 原候选站由事件涉及州的站点目录生成（chain_a_v1.py 第98–103行；chain_a.py 的 stations），v1 观测按模型峰时 ±6 h 查询一分钟 ASOS sknt、gust_sknt，缺测、负数、阵风小于持续风、峰阵风小于峰持续风均 QC；有效持续风少于648分钟、首末有效值不能包住峰时为 truncated；请求失败 request_error。只用 reason=eligible 的固定观测峰；s2b 的 scorer 没有重新筛站或查询观测。\n2. 48h 官方链须 97 个15分钟节点全窗，Pangu 路径同样97节点全窗。两链都有完整窗口且有 v1 eligible 站才进入同质主分析。Nicholas 同起报无 OFCL，48h 不可评；Ida/Idalia 无 eligible 主站（虽有候选/截尾），不得补入。\n3. sample_list.csv 逐行展示 v1 候选站的保留/剔除理由；仅 status=include 的9事件22站参与两链及所有变体。模型峰窗固定登陆±12h，观测峰固定 v1 obs_s_kt；绝不按变体峰时重查观测。v1 一分钟 ASOS sknt 是一分钟资料库的持续风记录，原 s2b RESULTS 注明其实际为约2分钟持续风代理，不能称传感器严格1分钟平均。\n''')
 print('sample',len(rr),'included',sum(x['status']=='include' for x in rr),sorted({x['event'] for x in rr if x['status']=='include'}))
if __name__=='__main__':main()
