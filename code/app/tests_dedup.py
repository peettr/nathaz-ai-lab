#!/usr/bin/env python3
"""L26.25 去重复测（测试副本，假对话，fake_post_delay=8s 模拟 rc_post 慢）。输出 JSON。"""
import json, os, threading, time, urllib.request, uuid
B = "http://127.0.0.1:8766"; WS = os.path.expanduser("~/l26_25_ws/wb_dedup"); FAKE = f"{WS}/fake_chat.jsonl"
def post(u, b, timeout=60):
    r = urllib.request.Request(B + u, data=json.dumps(b).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read())
def users(): return [json.loads(l) for l in open(FAKE)] if os.path.exists(FAKE) else []
def nuser(): return sum(1 for m in users() if m["role"] == "user")
R = {}
# A 连点：5 次并发、同一选区同一问题（模拟 Liang Hu 在 8 s 送达等待中连点）
body = {"question": "这段四个不同之处说清楚了吗", "selection": "In common usage, trustworthiness is a property", "page": 1}
n0 = nuser(); res = []
ts = [threading.Thread(target=lambda: res.append(post("/api/ask", body))) for _ in range(5)]
[t.start() or time.sleep(0.3) for t in ts]; [t.join() for t in ts]
R["A_连点5次"] = {"posted": nuser() - n0, "dup_replies": sum(1 for r in res if r.get("dup")), "pass": nuser() - n0 == 1}
# B 超时重试：客户端 2 s 超时后重发 3 次（慢网络），服务端仍在发第一条
body2 = dict(body, question="慢网络重试测试"); n0 = nuser(); errs = 0
for i in range(3):
    try: post("/api/ask", body2, timeout=2)
    except Exception: errs += 1
time.sleep(9)
R["B_超时重试3次"] = {"client_timeouts": errs, "posted": nuser() - n0, "pass": nuser() - n0 == 1}
# C 同一问题 60 s 内再发 → 不发；不同问题 → 照发
n0 = nuser(); r1 = post("/api/ask", body); r2 = post("/api/ask", dict(body, question="另一个问题"))
R["C_60s内同题不发_异题照发"] = {"same_dup": r1.get("dup", False), "diff_posted": nuser() - n0, "pass": r1.get("dup") and nuser() - n0 == 1}
# D 三条完全相同的 Lead 回复（各带同一 wb-edit）→ 待批只 1 条，可接受；其余标重复、接受被拒
e = {"file": "main.tex", "old": "This test paper are used", "new": "This test paper is used", "why": "主谓一致"}
for _ in range(3):
    with open(FAKE, "a") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(),
                            "content": "建议：\n```wb-edit\n" + json.dumps(e) + "\n```\n"}) + "\n")
st = json.loads(urllib.request.urlopen(B + "/api/state").read())
mine = [x for x in st["edits"] if x.get("old") == e["old"]]
pend = [x for x in mine if x["status"] == "待批"]; dups = [x for x in mine if x["status"] == "重复"]
rd = post("/api/accept", {"id": dups[0]["id"]}) if dups else {"ok": True}
R["D_三条重复待批合并"] = {"total": len(mine), "待批": len(pend), "重复": len(dups), "dup_count": pend[0].get("dup_count") if pend else None,
                       "accept_dup_refused": not rd["ok"], "msg": rd.get("msg"), "pass": len(pend) == 1 and len(dups) == 2 and not rd["ok"]}
# E 用户消息在对话里显示
R["E_对话显示用户提问"] = {"user_msgs_in_state": sum(1 for m in st["chat"] if m["role"] == "user"), "pass": any(m["role"] == "user" for m in st["chat"])}
log = open(f"{WS}/workbench.log").read()
R["日志去重记录条数"] = log.count("ask dedup")
print(json.dumps(R, ensure_ascii=False, indent=1))
