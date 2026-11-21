"""Validate 01p completed records; no solver runs, no overwrite."""
import json,math,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent/'run_01p'/'stage2'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def finite(x):return isinstance(x,(float,int)) and math.isfinite(x)
def regression(rows):
    x=np.array([r['T'] for r in rows if finite(r['ad_norm']) and r['ad_norm']>0],float)
    y=np.log(np.array([r['ad_norm'] for r in rows if finite(r['ad_norm']) and r['ad_norm']>0],float))
    if len(x)<3 or np.var(y)==0:return 'not_estimable','not_estimable'
    slope=float(np.polyfit(x,y,1)[0]);inter=float(y.mean()-slope*x.mean())
    r2=float(1-np.sum((y-(inter+slope*x))**2)/np.sum((y-y.mean())**2))
    return slope,r2

def main():
    points=[];results=[];segments=[];reliability=[];trunc=[]
    for i in range(5):
        p=ROOT/f'point_{i}.jsonl'
        rows=[json.loads(s) for s in p.read_text().splitlines() if s.strip()]
        assert rows[0]['type']=='start' and rows[-1]['type']=='complete' and rows[0]['point']==rows[-1]['point']==i
        points.append((i,sha(p),rows[0]['command']))
        results.extend(r for r in rows if r['type']=='result')
        segments.extend(r for r in rows if r['type']=='segment_average')
        reliability.extend(r for r in rows if r['type']=='fd_reliability')
        trunc.extend(r for r in rows if r['type']=='truncation')
    tm=rows[0]['T_m'];tv=rows[0]['T_v']
    keys=[(r['point'],r['dtype'],r['metric'],r['T'],r['fd_step_fraction']) for r in results]
    expected={(i,d,k,t,h) for i in range(5) for d in ('float32','float64') for k,T in (('mean',tm),('var',tv))
              for t in (T//8,T//4,T//2,T) for h in ((.01,.005,.0025,.001) if t==T else (.01,.005))}
    assert len(keys)==len(expected) and set(keys)==expected,(len(keys),len(expected))
    assert len(reliability)==40 and len(segments)==40 and len(trunc)==10
    assert len({(r['point'],r['metric'],r['T']) for r in reliability})==40
    assert len({(r['point'],r['metric'],r['fd_step_fraction']) for r in segments})==40
    merged=ROOT/'stage2p_results.jsonl';summary=ROOT/'STAGE2P_SUMMARY.md'
    if merged.exists() or summary.exists():raise FileExistsError('never overwrite results')
    merged.write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n' for r in results+reliability+segments+trunc))
    by={(r['point'],r['metric'],r['T']):r for r in reliability}
    text=['# 01p 五个随机指令点阶段2','',
          '数据源：CRC A10 BGK/Re_H=1000 合格终态，噪声种子 26031；控制向量 seed 26220，见 01p_commands.json。',
          f'T_m={tm}, T_v={tv}；FD 可靠性定义 ‖FD1%−FD0.5%‖/‖FD1%‖≤0.05。',
          '差分不可靠点剔除分母，不以细步长接近 AD 代替可靠性认证。','',
          '原始文件哈希：']
    text += [f'- 点{i}: {h}' for i,h,_ in points]
    text += ['', '|点|目标|T|FD 可靠|FP64 AD/FD1% cos|相对差|FP32 AD/FD1% cos|相对差|', '|---:|---|---:|---|---:|---:|---:|---:|']
    for i in range(5):
        for kind,T in (('mean',tm),('var',tv)):
            for t in (T//8,T//4,T//2,T):
                a=next(r for r in results if (r['point'],r['dtype'],r['metric'],r['T'],r['fd_step_fraction'])==(i,'float64',kind,t,.01))
                b=next(r for r in results if (r['point'],r['dtype'],r['metric'],r['T'],r['fd_step_fraction'])==(i,'float32',kind,t,.01))
                rel=by[i,kind,t]
                text.append(f'|{i}|{kind}|{t}|{not rel["unreliable"]} ({rel["relative_difference"]})|{a["cos"]}|{a["relative_difference"]}|{b["cos"]}|{b["relative_difference"]}|')
    text += ['', '全窗细步长 (FP64 AD 对 FP64 FD)：','|点|目标|步长|cos|相对差|','|---:|---|---:|---:|---:|']
    for r in results:
        if r['dtype']=='float64' and r['fd_step_fraction'] in (.0025,.001):
            text.append(f'|{r["point"]}|{r["metric"]}|{r["fd_step_fraction"]}|{r["cos"]}|{r["relative_difference"]}|')
    text += ['', '指数增长描述：对 log‖g_AD‖ 与线性 T 回归，零/非有限范数不能拟合。','|点|目标|精度|斜率每步|R²|','|---:|---|---|---:|---:|']
    for i in range(5):
        for k in ('mean','var'):
            for d in ('float32','float64'):
                rr=sorted((r for r in results if r['point']==i and r['metric']==k and r['dtype']==d and r['fd_step_fraction']==.01),key=lambda r:r['T'])
                slope,r2=regression(rr);text.append(f'|{i}|{k}|{d}|{slope}|{r2}|')
    text += ['', '分段平均梯度（固定段起点状态、段目标平方和、各段等权平均；仅描述）：','|点|目标|段数|步长|cos|相对差|','|---:|---|---:|---:|---:|']
    for r in segments:text.append(f'|{r["point"]}|{r["metric"]}|{r["segment_count"]}|{r["fd_step_fraction"]}|{r["cos"]}|{r["relative_difference"]}|')
    text += ['', '截断偏差代理为 T/8 前缀 AD 对全窗 FD1%，逐点向量见 JSONL；只描述，不作为判据。']
    summary.write_text('\n'.join(text)+'\n')
    print('validated',len(results),'results',len(reliability),'reliability',len(segments),'segments',sha(merged),sha(summary))
if __name__=='__main__':main()
