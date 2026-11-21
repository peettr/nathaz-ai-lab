"""Verify five addendum files, merge reproducibly, and summarize without scientific verdict."""
import json
import hashlib
from pathlib import Path
import numpy as np

BASE=Path('./26_Quick_Trials/06_Logs/L26.22/armA')
RUN=BASE/'run_01o'
OLD=BASE/'run_01m/stage2/stage2_results.jsonl'

def load(p): return [json.loads(x) for x in p.read_text().splitlines()]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    prior=load(OLD)
    old={}
    for r in prior:
        if r.get('type')=='result' and r.get('dtype')=='float64':
            old[(r['point'],r['metric'],r['T'],r['fd_step_fraction'])]=r
    rows=[]
    for idx in range(5):
        part=load(RUN/'v2'/f'point_{idx}.jsonl')
        assert part[0]['type']=='start' and part[-1]['type']=='complete'
        assert part[0]['point']==idx and part[-1]['point']==idx
        rows.extend(part)
    keys=set()
    for r in rows:
        if r['type'] in ('fd_result','segment','segment_average','fd_batch'):
            key=(r['point'],r['type'],r.get('metric'),r.get('T'),r.get('fd_step_fraction'),r.get('segment_index'),r.get('step'))
            if key in keys: raise ValueError(('duplicate',key))
            keys.add(key)
    step_rows=[r for r in rows if r['type']=='fd_result']
    seg=[r for r in rows if r['type']=='segment_average']
    assert len(step_rows)==3*8+5*2*2,len(step_rows)  # 0.5% for 3*8; fine steps for 5*2*2
    assert len(seg)==10,len(seg)
    for idx in range(5):
        assert len([r for r in seg if r['point']==idx])==2
        for kind,Ts in (('mean',(4480,8960,17920,35840)),('var',(9280,18560,37120,74240))):
            for t in Ts:
                assert (idx,kind,t,.01) in old
                if idx>=2: assert any(r['point']==idx and r['metric']==kind and r['T']==t and r['fd_step_fraction']==.005 for r in step_rows)
            for frac in (.0025,.001):
                assert any(r['point']==idx and r['metric']==kind and r['T']==Ts[-1] and r['fd_step_fraction']==frac for r in step_rows)
    output=RUN/'addendum_results.jsonl'
    if output.exists(): raise FileExistsError(output)
    output.write_text(''.join(json.dumps(r,sort_keys=True,allow_nan=False)+'\n' for r in rows))
    lines=['# L26.22-01o 臂A BGK 差分与分段梯度补测','',
           '数据源：CRC A10 BGK/Re_H=1000，起转终态来自 1755011；原比较来自 run_01m/stage2/stage2_results.jsonl。',
           'FD 相对差定义为 ‖FD(h)−FD(1%)‖/‖FD(1%)‖；超过 0.05 标差分不可靠。',
           '段目标：各自段内 12 测点均值相对 .023 的平方和（J_mean），或段内标准差相对 .001 的平方和（J_var）。',
           '段从同一全窗轨迹相邻起点出发，起点状态对指令停梯度；J_mean 两段各 17920 步、J_var 八段各 9280 步，段目标 AD 等权平均。这是描述量而非全窗 AD。','',
           '|点|目标|窗 T|FD(0.5%) vs FD(1%) 相对差|差分不可靠|AD vs FD(0.5%) cos|相对差|',
           '|---:|---|---:|---:|---|---:|---:|']
    for r in step_rows:
        if r['fd_step_fraction']!=.005:continue
        m=r['vs_ad']
        lines.append(f"|{r['point']}|{r['metric']}|{r['T']}|{r['vs_1pct_relative']:.8g}|{r['fd_unreliable']}|{m['cos']:.8g}|{m['relative_difference']:.8g}|")
    lines.extend(['','全窗细步长扫描：','|点|目标|档位|AD–FD cos|相对差|相对 1% FD 差|','|---:|---|---:|---:|---:|---:|'])
    for r in step_rows:
        if r['fd_step_fraction']==.005:continue
        m=r['vs_ad']
        lines.append(f"|{r['point']}|{r['metric']}|{r['fd_step_fraction']:.4g}|{m['cos']:.8g}|{m['relative_difference']:.8g}|{r['vs_1pct_relative']:.8g}|")
    lines.extend(['','分段平均梯度与全窗 FD 比较：','|点|目标|段长|段数|FD 档位|cos|相对差|','|---:|---|---:|---:|---:|---:|---:|'])
    for r in seg:
        idx,kind,T=r['point'],r['metric'],r['T']
        avg=np.asarray(r['gradient'],float)
        available={.01:np.asarray(old[(idx,kind,T,.01)]['fd'],float)}
        if (idx,kind,T,.005) in old:
            available[.005]=np.asarray(old[(idx,kind,T,.005)]['fd'],float)
        for q in step_rows:
            if q['point']==idx and q['metric']==kind and q['T']==T:
                available[q['fd_step_fraction']]=np.asarray(q['fd'],float)
        # Smallest reliable step = finest in a consecutive stable FD plateau;
        # a finer step with >5% change from its next coarser step is not certified.
        reliable=.01
        for fine,coarse in ((.005,.01),(.0025,.005),(.001,.0025)):
            if fine not in available or coarse not in available: break
            if np.linalg.norm(available[fine]-available[coarse])/np.linalg.norm(available[coarse])>.05: break
            reliable=fine
        for frac in sorted({.01,reliable}):
            f=available[frac]
            cos=float(np.dot(avg,f)/(np.linalg.norm(avg)*np.linalg.norm(f)))
            rel=float(np.linalg.norm(avg-f)/np.linalg.norm(f))
            lines.append(f"|{idx}|{kind}|{r['segment_T']}|{r['segment_count']}|{frac:.4g}|{cos:.8g}|{rel:.8g}|")
    lines+=['','本表只提供判据所需数字，不替 Lead 作值得用/放弃裁决。']
    summary=RUN/'ADDENDUM_SUMMARY.md'
    if summary.exists(): raise FileExistsError(summary)
    summary.write_text('\n'.join(lines)+'\n')
    print(json.dumps({'rows':len(rows),'fd_result':len(step_rows),'segment_average':len(seg),'output':str(output),'output_sha256':digest(output),'summary':str(summary),'summary_sha256':digest(summary)}))
if __name__=='__main__':main()
