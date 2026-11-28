"""L22.6 Claude 反馈轮：把 R{k}.json 的 messages 写成 H{k+1}.jsonl，再用 fb_R{k}.txt 原文作下一轮 user。
用法：python3 tools/claude_next_round.py <k> <id> [<id>...]（串行）"""
import json,subprocess,sys,os,datetime
k=int(sys.argv[1])
for i in sys.argv[2:]:
    d=f'claude/{i}'; out=f'{d}/R{k+1}.json'
    if os.path.exists(out) and os.path.getsize(out): continue
    msgs=[m for m in json.load(open(f'{d}/R{k}.json'))['messages'] if m['role'] in('user','assistant')]
    assert msgs[0]['role']=='user' and msgs[-1]['role']=='assistant'
    with open(f'{d}/H{k+1}.jsonl','w',encoding='utf-8') as f:
        for m in msgs: f.write(json.dumps({'role':m['role'],'content':m['content']},ensure_ascii=False)+'\n')
    with open(f'{d}/R{k+1}.log','w') as lg:
        rc=subprocess.run([os.path.expanduser('~/bin/rc-claude-qa'),'--caller','ideas-claude','--label','L22.6','--model','opus','--system','system.txt','--prompt',f'{d}/fb_R{k}.txt','--history',f'{d}/H{k+1}.jsonl','--out',out],stdout=lg,stderr=lg).returncode
    open('run_claude_rounds.log','a').write(f"{datetime.datetime.now():%m-%d %H:%M} {i} R{k+1} exit={rc}\n")
