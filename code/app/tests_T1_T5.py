#!/usr/bin/env python3
"""L26.25 T1–T5 测试（只对测试副本：~/l26_25_ws/repo，假远端 remote.git，假对话 fake_chat.jsonl）。
输出 JSON 结果到 stdout。"""
import json, os, re, subprocess, time, urllib.request, uuid

B = "http://127.0.0.1:8766"
WS = os.path.expanduser("~/l26_25_ws")
FAKE = f"{WS}/wb_test/fake_chat.jsonl"
REPO = f"{WS}/repo"


def post(u, b=None):
    r = urllib.request.Request(B + u, data=json.dumps(b or {}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=300).read())


def state():
    return json.loads(urllib.request.urlopen(B + "/api/state", timeout=60).read())


def lead_says(text, edits):
    blocks = "".join("\n```wb-edit\n" + json.dumps(e, ensure_ascii=False) + "\n```\n" for e in edits)
    with open(FAKE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": "a-" + uuid.uuid4().hex[:8], "role": "assistant", "ts": time.time(), "content": text + blocks},
                           ensure_ascii=False) + "\n")


def sh(cmd, cwd=REPO):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)


def remote_log():
    return sh("git --git-dir=../remote.git log --format='%h|%s' main").stdout.strip().split("\n")


R = {}
# ---- T1 选取→提问 ----
sels = [("This test paper are used to evaluate an editing tool.", 1, 11),
        ("it’s effect on the lock-in range", 1, 16),
        ("mÿ + cẏ + ky = ρU 2 DCL", 1, 22),                     # 公式区域
        ("The peak amplitude is 0.78D at a reduced velocity", 1, 49),
        ("Amplitude response versus reduced velocity.", 1, 58)]
src = open(f"{REPO}/main.tex", encoding="utf-8").read().split("\n")
t1 = []
before = sum(1 for _ in open(FAKE)) if os.path.exists(FAKE) else 0
for s, p, expect in sels:
    r = post("/api/ask", {"question": "这里请看一下", "selection": s, "page": p})
    line = r.get("loc", {}).get("line") if r.get("loc") else None
    if expect is None:  # 期望行 = 源码里含该句关键词的行
        key = s.split()[1]
        expect = next((i for i, l in enumerate(src, 1) if s.split()[0] in l and key in l), None)
    t1.append({"sel": s, "ok": r["ok"], "line": line, "expect": expect, "line_ok": line == expect})
after = [json.loads(l) for l in open(FAKE)][before:]
R["T1"] = {"items": t1, "arrived": sum(1 for m in after if m["role"] == "user" and "【稿件工作台】" in m["content"] and "选中原文" in m["content"]),
           "pass": all(x["ok"] and x["line_ok"] for x in t1) and len(after) == 5}

# ---- T2 待批→写回 5 条 ----
edits = [
    {"file": "main.tex", "old": "This test paper are used", "new": "This test paper is used", "why": "主谓一致"},
    {"file": "main.tex", "old": "We considers a wake oscillator", "new": "We consider a wake oscillator", "why": "主谓一致"},
    {"file": "main.tex", "old": "coupled to a elastically mounted", "new": "coupled to an elastically mounted", "why": "冠词"},
    {"file": "main.tex", "old": "the coupling term and it's effect", "new": "the coupling term and its effect", "why": "its"},
    {"file": "main.tex", "old": "The model reproduce\nthe upper branch", "new": "The model reproduces the upper branch", "why": "跨行空白归一定位测试"},
]
lead_says("建议如下。", edits)
st = state()
ids = [e["id"] for e in st["edits"] if e["status"] == "待批"][-5:]
t2 = []
for eid, e in zip(ids, edits):
    h0 = sh("git rev-parse HEAD").stdout.strip()
    r = post("/api/accept", {"id": eid})
    diff = sh(f"git diff {h0} HEAD -U0").stdout if r["ok"] else ""
    minus = [l[1:] for l in diff.split("\n") if l.startswith("-") and not l.startswith("---")]
    plus = [l[1:] for l in diff.split("\n") if l.startswith("+") and not l.startswith("+++")]
    only = r["ok"] and len(sh(f"git diff --name-only {h0} HEAD").stdout.split()) == 1 and \
        " ".join(minus).replace(e["old"].replace("\n", " "), "") == " ".join(plus).replace(e["new"], "")
    msg = sh("git log -1 --format=%s").stdout.strip()
    t2.append({"edit": e["why"], "ok": r["ok"], "msg": r["msg"], "only_that_change": only,
               "commit_msg_ok": ("Lead 提" in msg and "Liang Hu" in msg and "接受" in msg)})
rl = remote_log()
R["T2"] = {"items": t2, "remote_commits": rl[:6], "pass": all(x["ok"] and x["only_that_change"] and x["commit_msg_ok"] for x in t2)}

# ---- T3 冲突 ----
# (a) 远端有人先改了同一句 → 已过时、不写回
tmp = f"{WS}/collab"
subprocess.run(f"rm -rf {tmp} && git clone -q {WS}/remote.git {tmp}", shell=True)
sh("sed -i 's/Wake oscillator models represent the fluctuating lift/Wake-oscillator models describe the fluctuating lift/' main.tex && "
   "git -c user.name=c -c user.email=c@c commit -qam collab-edit && git push -q origin main", cwd=tmp)
lead_says("再改一句。", [{"file": "main.tex", "old": "Wake oscillator models represent the fluctuating lift",
                          "new": "Wake oscillator models express the fluctuating lift", "why": "用词"}])
eid = [e["id"] for e in state()["edits"] if e["status"] == "待批"][-1]
n0 = len(remote_log())
ra = post("/api/accept", {"id": eid})
stale_ok = (not ra["ok"]) and "过时" in ra["msg"] and len(remote_log()) == n0 and "describe" in open(f"{REPO}/main.tex").read()
# (b) 拉取冲突：本地有人留了未提交改动 → 停下不覆盖
sh("echo '% local uncommitted' >> main.tex")
lead_says("又一条。", [{"file": "main.tex", "old": "The lock-in range", "new": "The lock-in range", "why": "占位"}])
eid2 = [e["id"] for e in state()["edits"] if e["status"] == "待批"][-1]
rb = post("/api/accept", {"id": eid2})
dirty_ok = (not rb["ok"]) and "未提交改动" in rb["msg"] and "% local uncommitted" in open(f"{REPO}/main.tex").read()
sh("git checkout -- main.tex")
# (c) 真正的 rebase 冲突：本地已提交未推的改动与远端同一行冲突 → doc-git-sync 退出 3，工作台停下
sh("sed -i 's/range extends from/range spans from/' main.tex && git -c user.name=l -c user.email=l@l commit -qam local-unpushed")
sh("sed -i 's/range extends from/range goes from/' main.tex && git -c user.name=c -c user.email=c@c commit -qam collab2 && git push -q origin main", cwd=tmp)
lead_says("第三条。", [{"file": "main.tex", "old": "Figure 1 shows the amplitude response.", "new": "Figure 1 shows the amplitude response curve.", "why": "测试"}])
eid3 = [e["id"] for e in state()["edits"] if e["status"] == "待批"][-1]
n1 = len(remote_log())
rc_ = post("/api/accept", {"id": eid3})
rebase_ok = (not rc_["ok"]) and ("冲突" in rc_["msg"] or "拉取" in rc_["msg"]) and len(remote_log()) == n1
# 收拾：中止 rebase，丢掉本地未推测试提交，回到远端
sh("git rebase --abort; git fetch -q origin && git reset -q --hard origin/main")
R["T3"] = {"stale": {"ok": stale_ok, "msg": ra["msg"]}, "dirty": {"ok": dirty_ok, "msg": rb["msg"]},
           "rebase_conflict": {"ok": rebase_ok, "msg": rc_["msg"][:200]}, "pass": stale_ok and dirty_ok and rebase_ok}

# ---- T4 撤销 ----
acc = [e for e in state()["edits"] if e["status"] == "已接受"]
target = acc[0]  # 第一条：are→is
txt0 = open(f"{REPO}/main.tex").read()
r4 = post("/api/revert", {"id": target["id"]})
txt1 = open(f"{REPO}/main.tex").read()
R["T4"] = {"ok": r4["ok"], "msg": r4["msg"], "restored": ("This test paper are used" in txt1) and ("This test paper is used" in txt0),
           "others_kept": "We consider a wake oscillator" in txt1, "remote_head": remote_log()[0]}
R["T4"]["pass"] = R["T4"]["ok"] and R["T4"]["restored"] and R["T4"]["others_kept"]

# ---- T5 令牌 ----
logs = open(f"{WS}/wb_test/workbench.log", encoding="utf-8").read() + open(f"{WS}/wb_test/stdout.txt", encoding="utf-8").read()
hits = len(re.findall(r"olp_[A-Za-z0-9]{6,}", logs))
R["T5"] = {"olp_plain_hits_in_logs": hits, "pass": hits == 0}
print(json.dumps(R, ensure_ascii=False, indent=1))
