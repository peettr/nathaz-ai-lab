"""Validate and aggregate the frozen 01m stage2 point outputs (no solver runs)."""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'run_01m' / 'stage2'
WINDOWS = {'mean': (4480, 8960, 17920, 35840), 'var': (9280, 18560, 37120, 74240)}


def norm(v):
    if not isinstance(v, list) or len(v) != 18 or not all(isinstance(x, (float, int)) and math.isfinite(x) for x in v):
        return float('nan')
    return math.sqrt(sum(x*x for x in v))


def lin_r2(xs, ys):
    if not all(math.isfinite(x) for x in ys):
        return float('nan')
    xm = sum(xs)/len(xs); ym = sum(ys)/len(ys)
    vx = sum((x-xm)**2 for x in xs)
    if not vx: return float('nan')
    b = sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/vx
    a = ym-b*xm
    tot = sum((y-ym)**2 for y in ys)
    return 1-sum((y-a-b*x)**2 for x,y in zip(xs,ys))/tot if tot else float('nan')


def main():
    rows=[]; proxies=[]; fd_batches=[]
    for point in range(5):
        path=ROOT/f'point_{point}.jsonl'
        if not path.is_file(): raise RuntimeError(f'缺文件 {path}')
        entries=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        starts=[r for r in entries if r.get('type')=='start']
        ends=[r for r in entries if r.get('type')=='complete']
        if len(starts)!=1 or len(ends)!=1 or ends[-1]!=entries[-1]: raise RuntimeError(f'未完成或标记重复: {path}')
        if starts[0]['point'] != point: raise RuntimeError(f'点编号不符: {path}')
        rows += [r for r in entries if r.get('type')=='result']
        proxies += [r for r in entries if r.get('type')=='truncation_proxy']
        fd_batches += [r for r in entries if r.get('type')=='fd_batch']
    expected={(i,d,k,t,s) for i in range(5) for d in ('float32','float64')
              for k,ts in WINDOWS.items() for t in ts for s in ((.01,.005) if i<2 else (.01,))}
    keys=[(r['point'],r['dtype'],r['metric'],r['T'],r['fd_step_fraction']) for r in rows]
    if len(keys)!=len(expected) or set(keys)!=expected: raise RuntimeError(f'结果缺失/重复: {len(keys)}/{len(expected)}')
    if len(proxies)!=10 or len(fd_batches)!=7: raise RuntimeError('描述量或FD批次数量不符')
    bykey=dict(zip(keys,rows))
    out=['# L26.22-01m 五点 BGK 阶段2汇总','',
         '数据源：CRC A10 run_01m/stage2/point_0..4.jsonl；BGK/Re_H=1000，起转终态来自 1755011。',
         '同一终态与固定噪声；FP64 中心差分量程 1% 五点、0.5% 前两点。',
         '', '|目标|窗口|FP64 AD/FD 1% 合格|FP32 AD/FD 1% 合格|FP64 AD 有限|FD 不可靠（前两点）|',
         '|---|---:|---:|---:|---:|---:|']
    unreliable={}
    for kind, ts in WINDOWS.items():
        for t in ts:
            flags=[]
            for i in range(2):
                f=bykey[i,'float64',kind,t,.01]['fd']; h=bykey[i,'float64',kind,t,.005]['fd']
                nf=norm(f)
                diff=norm([x-y for x,y in zip(f,h)]) if math.isfinite(nf) else float('nan')
                rel=diff/nf if nf>0 else float('nan')
                unreliable[i,kind,t]=not (math.isfinite(rel) and rel<=.05)
                flags.append(f'{i}:{rel:.6g}' if math.isfinite(rel) else f'{i}:非有限')
            def good(i,d):
                r=bykey[i,d,kind,t,.01]
                return r['finite'] and isinstance(r['cos'],(int,float)) and r['cos']>=.95 and isinstance(r['relative_difference'],(int,float)) and r['relative_difference']<=.10
            out.append(f'|{kind}|{t}|{sum(good(i,"float64") for i in range(5))}/5|{sum(good(i,"float32") for i in range(5))}/5|{sum(bool(bykey[i,"float64",kind,t,.01]["finite"]) for i in range(5))}/5|{", ".join(flags)}|')
    out += ['', '逐点逐窗数值（cos、相对差、范数、梯度向量）见附带 stage2_results.jsonl。',
            '差分可靠性只有前两点有 0.5% 复核；其余三点未复核，不可默认可靠。',
            '', '范数对窗长 log-linear R²（逐点逐目标、FP64 AD）：']
    for kind,ts in WINDOWS.items():
        for i in range(5):
            ns=[bykey[i,'float64',kind,t,.01]['ad_norm'] for t in ts]
            vals=[math.log(n) if isinstance(n,(int,float)) and n>0 and math.isfinite(n) else float('nan') for n in ns]
            out.append(f'- {kind} 点{i}: R²={lin_r2([math.log(t) for t in ts],vals):.8g}; 范数='+', '.join(str(n) for n in ns))
    out += ['', '描述量：以下短前缀对全窗 FD 是截断代理，不是分段平均梯度。']
    for r in proxies:
        out.append(f'- {r["metric"]} 点{r["point"]}: T_short={r["short_window"]}, T_full={r["full_window"]}, cos={r["cos"]}, 相对差={r["relative_difference"]}')
    out += ['', '分段平均梯度：当前冻结作业只计算从相同起转终态出发的前缀梯度，未计算各相邻段的梯度；不能由这些前缀向量冒充段平均。需在判据触发时另行测算。',
            '注：本表不替 Lead 作「值得用/放弃」裁决。']
    merged=ROOT/'stage2_results.jsonl'; summary=ROOT/'STAGE2_SUMMARY.md'
    for path in (merged,summary):
        if path.exists(): raise FileExistsError(f'不覆盖已有结果: {path}')
    merged.write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False,sort_keys=True)+'\n' for r in rows))
    summary.write_text('\n'.join(out)+'\n')
    print(f'验证 {len(rows)} 唯一结果、{len(fd_batches)} FD批、{len(proxies)} 截断描述；生成 {merged} 与 {summary}')

if __name__=='__main__':
    try: main()
    except Exception as e:
        print(f'汇总失败: {e}',file=sys.stderr); sys.exit(1)
