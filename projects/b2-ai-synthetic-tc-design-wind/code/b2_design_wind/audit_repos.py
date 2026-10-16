#!/usr/bin/env python3
"""Audit identifiable GitHub repositories, keep API response snapshot."""
import requests,json,pathlib,datetime,zoneinfo
root=pathlib.Path(__file__).resolve().parent
repos=['wenweixu/RAFT-dataset-processing','pnnl/raft-model.github.io','NBloemendaal/STORM','MRibberink/STORM2.0','neuralgcm/neuralgcm','CLIMADA-project/climada_python']
records=[]
for name in repos:
 r=requests.get('https://api.github.com/repos/'+name,timeout=30);r.raise_for_status();j=r.json();c=requests.get('https://api.github.com/repos/'+name+'/commits',params={'per_page':1},timeout=30);c.raise_for_status();head=c.json()[0]
 records.append({'full_name':j['full_name'],'url':j['html_url'],'stars':j['stargazers_count'],'license':j['license']['spdx_id'] if j['license'] else '未声明','latest_commit_date':head['commit']['committer']['date'],'latest_commit_sha':head['sha'],'description':j.get('description'),'archived':j.get('archived')})
 print(name,records[-1]['stars'],records[-1]['latest_commit_date'],records[-1]['license'],flush=True)
(root/'github_repos.json').open('x').write(json.dumps(records,ensure_ascii=False,indent=2))
links={'wenweixu/RAFT-dataset-processing':'Xu et al. 2024 / RAFT 轨迹处理；读取公开数据可本地运行，不能据此断言完整 RAFT 生成器公开','pnnl/raft-model.github.io':'RAFT 项目网页；不是模拟引擎','NBloemendaal/STORM':'Bloemendaal et al. 2020；生成器可运行但本实验直接用已发布目录','MRibberink/STORM2.0':'后续 STORM 2.0，非本轮 2020 v4 输入','neuralgcm/neuralgcm':'Kochkov et al. 2024 / SPIN 的气候组件；需 GPU、权重和气候强迫，不是 SPIN 全套','CLIMADA-project/climada_python':'H08 风场 CLIMADA 6.1.0；本轮 Colab CPU 实测可运行'}
text=['# GitHub 仓库实查（GitHub Search API + repositories/commits API）','时间：'+datetime.datetime.now(zoneinfo.ZoneInfo('America/New_York')).strftime('%m-%d %H:%M EDT'),'', '| 仓库 | 星数 | 最后提交 UTC | 许可证(API) | 对应论文及本地可运行性 |','|---|---:|---|---|---|']
for r in records:text.append(f"| {r['url']} | {r['stars']} | {r['latest_commit_date']} ({r['latest_commit_sha'][:10]}) | {r['license']} | {links[r['full_name']]} |")
text+=['','GitHub 搜索 `SPIN NeuralGCM`、`spin tropical cyclone in:name` 均无可确认的 SPIN 项目仓库；作者正式归档代码为 Zenodo https://doi.org/10.5281/zenodo.20796397 (5.7 GB)，不满足本轮 <5 GB 的下载条件。不能把 neuralgcm/neuralgcm 冒称 SPIN 官方仓库。RAFT 目录生成器源代码是否完整开放未核实，仅确认处理器仓库。','数据来源：GitHub REST `https://api.github.com/search/repositories`, `/repos/{owner}/{repo}`, `/commits?per_page=1`，原始结果见 `github_repos.json`。']
(root/'github_repos.md').open('x').write('\n'.join(text)+'\n')
