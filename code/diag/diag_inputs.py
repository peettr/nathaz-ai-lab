#!/usr/bin/env python3
"""R23.3a-02 retrospective H08 48h input-swap diagnostic (Colab CPU only).

Bundle original s2b source and frozen small reference files under /content/b_tc.
Output is exclusively under --out. Does not modify the frozen baseline.
"""
import argparse, csv, gzip, hashlib, json, math, statistics, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path('/content/b_tc')
sys.path[:0] = [str(BASE/'s2'), str(BASE/'v1')]
import chain_b_s2a as b
import chain_a_v1 as v
old = v.old

EVENTS = ('BERYL','DEBBY','DELTA','FRANCINE','HELENE','IAN','MILTON','NICOLE','ZETA')
VARIANTS = ('V0','V_dp','V_rmw','V_int','V_all')
NE_URL = 'https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip'

def rows(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))

def load_best(sid):
    url=old.ATCF.format(year=sid[-4:],sid=sid)
    raw=old.fetch(url)
    out={}
    for line in gzip.decompress(raw).decode(errors='replace').splitlines():
        a=[s.strip() for s in line.split(',')]
        if len(a)<20 or a[4]!='BEST' or a[11]!='34':continue
        try:
            t=old.dt(a[2]+'00')
            # ATCF BEST: Vmax[8] kt, Pc[9] hPa, POCI[17] hPa, RMW[19] nmi.
            out[t]=dict(t=t,v=float(a[8]),pc=float(a[9]),poci=float(a[17]),rmw=float(a[19]))
        except (ValueError,IndexError):continue
    return sorted(out.values(),key=lambda r:r['t']),dict(url=url,sha256=hashlib.sha256(raw).hexdigest(),records=len(out))

def interp_field(source,t,key,valid):
    # Field-specific: invalid values are missing, never interpolate through them.
    a=[(r['t'],(r[key],)) for r in source if valid(r[key])]
    z=old.interp(a,t,None)  # <= 7 h for bracketed nodes, s2b interpolation.
    if z is not None:return z[0]
    # Post-hoc endpoint-only sensitivity: sparse BEST 34-kt lines may have a
    # remote later record from the remnant storm. For a >12 h gap, carry the
    # near-side record <=6 h, not a linear interpolation through that gap.
    lo=max((r for r in a if r[0]<=t),default=None,key=lambda r:r[0])
    hi=min((r for r in a if r[0]>=t),default=None,key=lambda r:r[0])
    if lo and (t-lo[0]).total_seconds()<=6*3600 and (hi is None or (hi[0]-lo[0]).total_seconds()>12*3600):return lo[1][0]
    if hi and (hi[0]-t).total_seconds()<=6*3600 and (lo is None or (hi[0]-lo[0]).total_seconds()>12*3600):return hi[1][0]
    return None

def nearest_stations(event,obs,ev):
    ss={}
    for state in old.CANDIDATES[event][2].split(','):
        ss.update(old.stations(state,float(ev['lat']),float(ev['lon']),datetime.fromisoformat(ev['landfall_utc'])))
    stations=[ss[r['station']] for r in obs if r['event']==event and r['station'] in ss]
    assert len(stations)==sum(r['event']==event for r in obs),event
    return stations

def metrics(rr):
    e=[x['err_s'] for x in rr]
    return dict(n=len(e),B=statistics.median(e),median_abs=statistics.median(map(abs,e))) if e else dict(n=0,B=None,median_abs=None)

def as_table(headers,items):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for _ in headers)+' |\n'+'\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in items)+'\n'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    output=Path(args.out); output.mkdir(parents=True,exist_ok=True)
    if any((output/x).exists() for x in ('diag_results.csv','diag_inputs.md')):
        raise FileExistsError('Preserve existing diagnostic output; use fresh output root.')
    t0=time.monotonic()
    if not (BASE/'v1/ne_10m_land.zip').exists():
        urllib.request.urlretrieve(NE_URL,BASE/'v1/ne_10m_land.zip')
    geo=v.get_land()
    events={e['name']:e for e in rows(BASE/'events_verified.csv')}
    observations=rows(BASE/'v1/run2/station_rows_v1.csv')
    observed={(r['event'],r['station']):r for r in observations}
    baseline={(r['event'],r['station'],r['chain']):r for r in rows(BASE/'s2/s2b/final/station_comparison.csv') if r['reason']=='eligible' and int(r['nominal_lead_h'])==48 and r['event'] in EVENTS and r['chain'] in ('b','PANG')}
    assert len(baseline)==44,len(baseline)
    sources={}; records=[]; audits=[]
    for event in EVENTS:
        ev=events[event]; land=datetime.fromisoformat(ev['landfall_utc']);cycle=b.cycle_at(land,48);sid=ev['atcf_id'].lower()
        a,a_url=b.load_a(sid);init,error=b.get_initial(a,cycle)
        assert not error,(event,error)
        best,prov=load_best(sid);sources[event]=dict(best=prov,a_deck=a_url)
        stations=nearest_stations(event,observations,ev)
        ofcl=sorted((r for (c,aid,k),r in a.items() if c==cycle and aid=='OFCL' and k>=0 and r['v']>0),key=lambda r:r['t'])
        cobj=json.loads((BASE/f's2/s2b/track_{event.lower()}_pang_48.json').read_text())
        assert not cobj['failure'],event
        cpairs=[(datetime.fromisoformat(p['valid_utc']),(p['lat'],p['lon'])) for p in cobj['points']]
        fields={key:[interp_field(best,land-timedelta(hours=12)+timedelta(minutes=15*i),key,validator) for i in range(97)] for key,validator in (
            ('v',lambda x:x>0),('pc',lambda x:0<x<1100),('poci',lambda x:0<x<1100),('rmw',lambda x:0<x<=200))}
        end_hold={k:sum(x is not None and old.interp([(r['t'],(r[k],)) for r in best if validator(r[k])],land-timedelta(hours=12)+timedelta(minutes=15*i),None) is None for i,x in enumerate(vals)) for k,vals in fields.items() for validator in [dict(v=lambda x:x>0,pc=lambda x:0<x<1100,poci=lambda x:0<x<1100,rmw=lambda x:0<x<=200)[k]]}
        audits.append(dict(event=event,**{k+'_missing':sum(x is None for x in vals) for k,vals in fields.items()},**{k+'_endpoint_hold':n for k,n in end_hold.items()},best_records=prov['records']))
        for chain,variants in (('b',VARIANTS),('PANG',('V_all',))):
            for variant in variants:
                windrows=[]; missing=defaultdict(int)
                for i in range(97):
                    t=land-timedelta(hours=12)+timedelta(minutes=15*i)
                    forecast=b.forecast_interp([(r['t'],(r['lat'],r['lon'],r['v'])) for r in ofcl],t)
                    loc=forecast[:2] if forecast is not None else None
                    if chain=='PANG':loc=old.interp(cpairs,t,None)
                    if forecast is None or loc is None:missing['path_or_OFCL']+=1;continue
                    u=forecast[2];val={k:fields[k][i] for k in fields}
                    if variant in ('V_int','V_all'):
                        if val['v'] is None:missing['best_v']+=1;continue
                        intensity=val['v']
                    else:intensity=u
                    if variant in ('V_dp','V_all'):
                        if val['pc'] is None or val['poci'] is None:missing['best_pc_poci']+=1;continue
                        environmental=val['poci'];pressure=val['pc']
                    else:
                        environmental=init['poci'];pressure=environmental-(environmental-init['p'])*(intensity/init['v0'])**(1/.644)
                    if variant in ('V_rmw','V_all'):
                        if val['rmw'] is None:missing['best_rmw']+=1;continue
                        radius=val['rmw']
                    else:radius=init['rmw']
                    if not 0<pressure<environmental:missing['nonphysical_pressure']+=1;continue
                    windrows.append((t,loc[0],loc[1],intensity,pressure,radius,environmental))
                if len(windrows)!=97:
                    audits.append(dict(event=event,chain=chain,variant=variant,n_nodes=len(windrows),missing=dict(missing)))
                    print('INCOMPLETE',event,chain,variant,len(windrows),dict(missing),flush=True)
                    continue
                scored,_=b.score(event,48,windrows,stations,observed,land,geo)
                for r in scored:
                    if r['reason']!='eligible':continue
                    key=(event,r['station'],chain)
                    assert key in baseline,key
                    # Frozen observation must be same station and observed peak.
                    assert float(r['obs_s_kt'])==float(baseline[key]['obs_s_kt']),key
                    if variant=='V0':
                        olderr=float(baseline[key]['err_s'])
                        assert abs(r['err_s']-olderr)<1.e-8, (key,r['err_s'],olderr)
                    records.append(dict(event=event,station=r['station'],chain=chain,variant=variant,obs_s_kt=r['obs_s_kt'],pred_s_kt=r['pred_s_kt'],err_s=r['err_s'],model_peak_utc=r['model_peak_utc']))
                print('SCORED',event,chain,variant,len(windrows),sum(x['event']==event and x['chain']==chain and x['variant']==variant for x in records),'elapsed',round(time.monotonic()-t0,2),flush=True)
        # Pilot cost estimate after the first complete event, for the task's 5-CU hard gate.
        if event==EVENTS[0]:
            elapsed=time.monotonic()-t0
            print('PILOT_SECONDS',round(elapsed,2),'NINE_EVENT_PROJECTION_S',round(elapsed*9,2),flush=True)
            if elapsed*9>3600:raise RuntimeError('Pilot projects >1 hour; pause and check 5 CU budget')
    with (output/'diag_results.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,records[0].keys());writer.writeheader();writer.writerows(records)
    groups=defaultdict(list)
    for r in records:groups[(r['chain'],r['variant'])].append(r)
    complete=all(len(groups[key])==22 for key in [("b",v) for v in VARIANTS]+[("PANG","V_all")])
    if not complete:
        (output/'diag_inputs.md').write_text('# R23.3a-02 输入替换诊断：未完成\n\n个别变体 9 事件、22 站不齐，不能用不同样本比较中位数。\n\n'+as_table(['链','变体','合格站数'],[(c,v,len(groups[(c,v)])) for c,v in [("b",x) for x in VARIANTS]+[("PANG","V_all")]])+'\n缺值审计：\n\n```json\n'+json.dumps(audits,ensure_ascii=False,indent=2,default=str)+'\n```\n')
        return
    totals={k:metrics(v) for k,v in groups.items()}
    ref=totals[('b','V0')]['B']
    delta={v:totals[('b',v)]['B']-ref for v in ('V_dp','V_rmw','V_int')}
    interaction=totals[('b','V_all')]['B']-ref-sum(delta.values())
    ratio=totals[('PANG','V_all')]['median_abs']/totals[('b','V_all')]['median_abs']
    by_event=defaultdict(list)
    for r in records:by_event[(r['event'],r['chain'],r['variant'])].append(r)
    event_table=[];wins=[]
    for event in EVENTS:
        bb=metrics(by_event[(event,'b','V_all')]);cc=metrics(by_event[(event,'PANG','V_all')])
        if cc['median_abs']<=bb['median_abs']:wins.append(event)
        event_table.append((event,bb['n'],*[f"{metrics(by_event[(event,'b',vv)])['B']*100:.2f}" for vv in VARIANTS],f"{bb['median_abs']*100:.2f}",f"{cc['median_abs']*100:.2f}",'c' if cc['median_abs']<=bb['median_abs'] else 'b'))
    lines=['# R23.3a-02 事后输入替换诊断','',
      '范围：s2b 同一 48 h、9 事件 22 个 eligible 站，持续风主指标，H08 原风场与站点暴露规则。仅诊断，不判闸，不改 s2b。',
      '', '定义：站点 e = 模型峰值/冻结的观测峰值 − 1；B = median(e)；中位 |e| = median(|e|)。',
      'V0 原 (b)；V_dp 只将 Δp(t)=POCI(t)−Pc(t) 换成 BEST；V_rmw 只将 RMW(t) 换成 BEST；V_int 只将压力外推式的 OFCL V(t) 换成 BEST V(t)（并将该 V 传给 H08，避免强度在公式与风场不一致）；V_all 三项同时换，PANG V_all 只保留 Pangu 路径。',
      'Δ_x = B(V_x)−B(V0)；交互项 = B(V_all)−B(V0)−ΣΔ_x。B、|e|、Δ 以百分数/百分点表述。',
      '', '## 全站指标（程序由 CSV 生成）','',
      as_table(['链','变体','n','B (%)','median(|e|) (%)','Δ 对 b V0 (pp)'],[(chain,variant,totals[(chain,variant)]['n'],f"{totals[(chain,variant)]['B']*100:.2f}",f"{totals[(chain,variant)]['median_abs']*100:.2f}",f"{delta[variant]*100:+.2f}" if chain=='b' and variant in delta else '—') for chain,variant in [('b',v) for v in VARIANTS]+[('PANG','V_all')]]),
      f"三项交互项 {interaction*100:+.2f} pp；三项全换净变化 {(totals[('b','V_all')]['B']-ref)*100:+.2f} pp。",
      f"同三项全换 (c)/(b) 中位 |e| 比 = {totals[('PANG','V_all')]['median_abs']:.9f}/{totals[('b','V_all')]['median_abs']:.9f} = {ratio:.4f}；(c) 事件不差于 (b) {len(wins)}/9：{', '.join(wins)}。",
      '', '## 逐事件（B 各变体；最后两列事件内中位 |e|，单位 %）','',
      as_table(['事件','n','b V0 B','b V_dp B','b V_rmw B','b V_int B','b V_all B','b V_all |e|','c V_all |e|','较好'],event_table),
      '', '## 字段、插值和缺值','',
      '来源 ATCF b-deck BEST 34-kt 记录；0-based 字段 8=Vmax(knots)、9=Pc(hPa)、17=POCI(hPa)、19=RMW(nmi)。同有效时刻各字段独立挑有效节点，按时间线性插值到登陆 ±12 h 的 15 min 网格；内部相邻有效节点相隔 >7 h 不跨越，边界缺口见下一条。筛选 V>0，0<Pc,POCI<1100，0<RMW≤200，且组合 Pc<POCI。起报初值、路径 OFCL 插值沿用 chain_b_s2a.py。风场 CLIMADA 6.1.0 H08 与 chain_a_v1.py。',
      '事后补定（10-21，美东）：严格不外推首次试算发现 BERYL 窗末 11 个 15-min 节点、FRANCINE 窗末 16 个节点无 BEST 34-kt 行；严格读法是仅 7 事件可全窗比较，不能称 9/22 完整。为给定 9/22 诊断，末端最近有效 BEST 值限 6 h 持续（BERYL 最长 2 h 40 min，FRANCINE 最长 4 h），内部缺口仍不补；这是敏感性假设、不是 b-deck 原记录或预注册业务输入。审计表列持续节点数。',
      '注意：V_int 的替换同时作用于风场 max_sustained_wind 和压力外推式，故其单项效应不是纯压力公式效应；V_dp 将 Pc 与 POCI 一起换以保证 Δp 的物理参照，不能分解两者。中位数非线性，交互是残差，不能独立物理归因。',
      'b-deck 从结论时刻看属事后 BEST，不可用于业务起报；本诊断不可据此更改原业务评测。',
      '', '源数据 sha256：',*['- '+ev+' '+src['best']['url']+' '+src['best']['sha256'] for ev,src in sources.items()],
      '', '缺值审计：','', '```json',json.dumps(audits,ensure_ascii=False,indent=2,default=str),'```',
      '',f'Colab 计算耗时 {time.monotonic()-t0:.1f} s（不含 VM 配置）。']
    (output/'diag_inputs.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
