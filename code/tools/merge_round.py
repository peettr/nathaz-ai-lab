"""L22.6 按 extract.py 多轮规则合成 cand_R{k}：用法 python3 tools/merge_round.py <model> <k> <id>..."""
import json,subprocess,shutil,os,sys
m=sys.argv[1]; k=int(sys.argv[2])
for s in sys.argv[3:]:
    d=f'{m}/{s}'; r=json.load(open(f'{d}/R{k}.json')); t=r['text']
    print(s,r.get('model'),r.get('rounds'),r.get('replay'),len(t))
    open(f'{d}/R{k}_text.md','w',encoding='utf-8').write(t)
    for x in (f'own_R{k}',f'cand_R{k}'): shutil.rmtree(f'{d}/{x}',ignore_errors=True)
    subprocess.run(['python3','tools/extract.py',m,s,str(k),f'{d}/R{k}_text.md',f'{d}/own_R{k}'])
    shutil.copytree(f'{d}/cand_R{k-1}',f'{d}/cand_R{k}'); os.remove(f'{d}/cand_R{k}/EXTRACT.json')
    own=json.load(open(f'{d}/own_R{k}/EXTRACT.json'))
    # 判据补充（Lead 11-05 10:42，发现片段含 #include 被当完整文件；此时该份尚未提交打分）：
    # 同名文件新版不足上一轮一半大小的，视为片段，不覆盖。
    for f in list(own['files']):
        p=f'{d}/cand_R{k-1}/{f}'
        if os.path.exists(p) and os.path.getsize(f'{d}/own_R{k}/{f}') < 0.5*os.path.getsize(p):
            own['files'].remove(f); own['log'].append(f'{f}: 不足上一轮一半，视为片段，不收')
    for f in own['files']:
        os.makedirs(os.path.dirname(f'{d}/cand_R{k}/{f}') or '.',exist_ok=True); shutil.copy(f'{d}/own_R{k}/{f}',f'{d}/cand_R{k}/{f}')
    base=sorted(os.path.relpath(os.path.join(a,f),f'{d}/cand_R{k-1}') for a,_,fs in os.walk(f'{d}/cand_R{k-1}') for f in fs if f!='EXTRACT.json')
    json.dump({'model':m,'session':s,'round':k,'from_prev':[f for f in base if f not in own['files']],'from_this':own['files'],'log':own['log']},open(f'{d}/cand_R{k}/EXTRACT.json','w'),ensure_ascii=False,indent=1)
    print('  ->',own['files'])
