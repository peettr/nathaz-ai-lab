#!/usr/bin/env python3
"""Monitor V3 — lightweight submit + auto-monitor for CRC Condor GPU campaigns.

Design principles (learned from V2 failures on 2026-04-20):
- Single SSH call per poll cycle (no per-run tail commands)
- SSH ConnectTimeout=120s everywhere
- No Claude CLI dependency — failures are logged and notified, not auto-fixed
- Submit + monitor in one command
- Held permission errors auto-released (chmod 666 + condor_release)
- OOM auto-upgrade GPU tier (20→30→40→80GB) + batch halving
- Progress notification every 15 min
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Config ──────────────────────────────────────────────────────────────
HOST = "[邮箱]"
BASE = "/groups/kareem/[用户]/graph-deeponet-wind/auto_v3"
SSH_SOCKET = "~/.ssh/sockets/[邮箱]"
SSH_TIMEOUT = 120  # seconds
BOT_TOKEN = [已隐去]"TG_BOT_TOKEN", "8784162677:AAF-L_qNulpvcV_I6VcnHCPKOIoM4MVUAVE")
CHAT_ID = "6701874922"

POLL_INTERVAL = 180       # 3 min
PROGRESS_INTERVAL = 900   # 15 min
MAX_RELEASES = 3
MAX_OOM_RETRIES = 2
MIN_BATCH = 4

HELD_PERMANENT_PATTERNS = (
    "exceeded", "removed", "submit requirements", "invalid",
    "not found", "no such file", "failed to transfer",
)

EPOCH_RE = re.compile(
    r"Epoch\s+(\d+)/(\d+).*?R²=\s*([-0-9.]+).*?MAE=\s*([-0-9.]+)", re.I
)
OOM_RE = re.compile(r"CUDA out of memory|OOM|out of memory", re.I)
LOSS_ERR_RE = re.compile(r"Unknown loss '(\w+)'", re.I)
NAN_RE = re.compile(r"-3\.2796|nan|inf", re.I)

GPU_TIERS = [20000, 30000, 40000, 80000]  # MB


# ── SSH helpers ─────────────────────────────────────────────────────────
def _ssh_base() -> list[str]:
    return [
        "wsl", "bash", "-c",
        f"ssh -o BatchMode=yes -o ConnectTimeout={SSH_TIMEOUT} "
        f"-o ServerAliveInterval=10 "
        f"-o ControlPath={SSH_SOCKET} {HOST}"
    ]


def ssh_cmd(cmd: str, timeout: int = 180) -> subprocess.CompletedProcess:
    """Run a single SSH command via WSL."""
    full_cmd = _ssh_base()
    full_cmd[-1] += f" '{cmd}'"
    return subprocess.run(
        ["wsl", "bash", "-c", " ".join(full_cmd)],
        capture_output=True, text=True, timeout=timeout,
    )


def ssh_python(py_script: str, timeout: int = 180) -> tuple[int, str, str]:
    """Run a Python script on CRC via SSH stdin. Returns (rc, stdout, stderr)."""
    r = subprocess.run(
        ["wsl", "bash", "-c",
         f"ssh -o BatchMode=yes -o ConnectTimeout={SSH_TIMEOUT} "
         f"-o ServerAliveInterval=10 -o ControlPath={SSH_SOCKET} "
         f"{HOST} python3 -"],
        input=py_script.encode("utf-8"), capture_output=True, timeout=timeout,
    )
    return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")


def send_telegram(msg: str) -> None:
    """Send a Telegram notification."""
    if not BOT_TOKEN or not CHAT_ID:
        return
    import urllib.parse
    import urllib.request
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
    }).encode()
    try:
        urllib.request.urlopen(url, data, timeout=15)
    except Exception as exc:
        logging.warning("Telegram send failed: %s", exc)


# ── Poll script (runs on CRC) ──────────────────────────────────────────
POLL_SCRIPT = r'''# -*- coding: utf-8 -*-
import json, re, subprocess, os
from pathlib import Path

rb = Path("RB_PLACEHOLDER")
cluster = "CLUSTER_PLACEHOLDER"

# 1. Condor status
r = subprocess.run(["condor_q", cluster], capture_output=True, text=True)
condor_lines = r.stdout.strip().splitlines()[:6]

# 2. Held jobs
r2 = subprocess.run(
    ["condor_q", cluster, "-hold", "-af:j", "ProcId", "HoldReason"],
    capture_output=True, text=True,
)
held_lines = [l.strip() for l in r2.stdout.strip().splitlines() if l.strip()]

# 3. Per-run status from train.out
runs = []
for i in range(RUN_COUNT):
    d = rb / f"run_{i:02d}"
    op = d / "train.out"
    mp = d / "metrics.json"
    cp = d / "train_config.json"

    cfg = {}
    if cp.exists():
        try:
            cfg = json.loads(cp.read_text())
        except Exception:
            pass

    arch = cfg.get("arch_name", "?")
    loss = cfg.get("loss_name", "?")
    lr = cfg.get("lr", "?")
    bs = cfg.get("batch_size", 16)

    r2_val = None
    mae_val = None
    ep = 0
    status = "WAIT"
    error_type = None

    if mp.exists():
        status = "DONE"
        ep = 9999
    elif op.exists():
        content = op.read_text(errors="replace")
        epochs = re.findall(
            r"Epoch\s+(\d+)/\d+.*?R²=\s*([-0-9.]+).*?MAE=\s*([-0-9.]+)", content
        )
        if epochs:
            ep = int(epochs[-1][0])
            try:
                r2_val = float(epochs[-1][1])
                mae_val = float(epochs[-1][2])
            except ValueError:
                pass
            status = "DONE" if ep >= 9999 else "RUN"

            # DIVERGED: R² < 0 and ep > 30 (truly hopeless)
            if status == "RUN" and r2_val is not None and r2_val < 0 and ep > 30:
                error_type = "DIVERGED"
                status = "DIVERGED"

            # EARLY_STOP: train.py triggered early stop by time limit
            if "early_stop:" in content[-3000:]:
                m = re.search(r"early_stop:.*best_R²=([-0-9.]+).+baseline@ep\d+=([-0-9.]+)", content[-3000:])
                if m:
                    r2_val = float(m.group(1))
                error_type = "EARLY_STOP"
                status = "EARLY_STOP"

            # MAX_WALL: train.py hit max wall time
            if "max_wall_time:" in content[-3000:]:
                error_type = "MAX_WALL"
                status = "MAX_WALL"
        else:
            # Check for errors (no epochs found)
            if "CUDA out of memory" in content or "OOM" in content:
                error_type = "OOM"
                status = "OOM"
            elif "Unknown loss" in content:
                error_type = "LOSS_NAME"
                status = "ERR_LOSS"
            elif "Traceback" in content:
                error_type = "CRASH"
                status = "CRASH"
            else:
                status = "WAIT"
                ep = 0
    else:
        status = "WAIT"

    runs.append({
        "run": i, "arch": arch, "loss": loss, "lr": str(lr), "bs": bs,
        "ep": ep, "r2": r2_val, "mae": mae_val,
        "status": status, "error": error_type,
    })

result = {
    "condor": condor_lines,
    "held": held_lines,
    "runs": runs,
}
print(json.dumps(result))
'''


# ── State ───────────────────────────────────────────────────────────────
@dataclass
class RunState:
    run_id: int
    arch: str = ""
    loss: str = ""
    lr: str = ""
    bs: int = 16
    status: str = "WAIT"  # WAIT, RUN, DONE, OOM, ERR_LOSS, CRASH, DIVERGED, EARLY_STOP, MAX_WALL, ERR_UNKNOWN
    ep: int = 0
    r2: float | None = None
    mae: float | None = None
    error: str | None = None
    gpu_tier_idx: int = 0  # index into GPU_TIERS
    oom_retries: int = 0
    release_retries: int = 0
    notified: bool = False


@dataclass
class CampaignState:
    cluster: str
    campaign: str
    remote_base: str
    run_count: int
    runs: dict[int, RunState] = field(default_factory=dict)
    poll_count: int = 0
    start_time: float = 0.0
    last_progress_time: float = 0.0


# ── Core logic ──────────────────────────────────────────────────────────
def poll_all(state: CampaignState) -> dict | None:
    """Single SSH call to get all run statuses."""
    script = POLL_SCRIPT
    script = script.replace("RB_PLACEHOLDER", state.remote_base)
    script = script.replace("CLUSTER_PLACEHOLDER", state.cluster)
    script = script.replace("RUN_COUNT", str(state.run_count))

    rc, stdout, stderr = ssh_python(script, timeout=180)
    if rc != 0:
        logging.warning("Poll failed rc=%d: %s", rc, stderr[:200])
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        logging.warning("Poll returned non-JSON: %s", stdout[:200])
        return None


def update_state(state: CampaignState, data: dict) -> list[str]:
    """Update RunState from poll data. Returns list of actions taken."""
    actions = []

    for rdata in data.get("runs", []):
        rid = rdata["run"]
        if rid not in state.runs:
            rs = RunState(run_id=rid, arch=rdata["arch"], loss=rdata["loss"],
                          lr=rdata["lr"], bs=rdata.get("bs", 16))
            state.runs[rid] = rs
        else:
            rs = state.runs[rid]

        new_status = rdata["status"]
        new_ep = rdata["ep"]
        new_r2 = rdata["r2"]
        new_error = rdata.get("error")

        # Detect status transitions
        old_status = rs.status
        rs.ep = new_ep
        rs.r2 = new_r2
        rs.mae = rdata.get("mae")
        rs.error = new_error

        if new_status != old_status:
            rs.status = new_status
            if new_status in ("OOM", "ERR_LOSS", "CRASH", "DIVERGED", "EARLY_STOP", "MAX_WALL", "ERR_UNKNOWN"):
                actions.append(f"run_{rid:02d} {rs.arch} → {new_status} ({new_error or ''})")
                if not rs.notified:
                    send_telegram(
                        f"⚠️ run_{rid:02d} {rs.arch} {rs.loss}\n"
                        f"Status: {new_status}\n"
                        f"Error: {new_error or 'unknown'}"
                    )
                    rs.notified = True
            elif new_status == "DONE" and old_status != "DONE":
                r2_str = f"{new_r2:.4f}" if new_r2 is not None else "?"
                actions.append(f"run_{rid:02d} {rs.arch} DONE R²={r2_str}")

    return actions


def handle_held(state: CampaignState, held_lines: list[str]) -> list[str]:
    """Auto-release held jobs with permission errors."""
    actions = []
    for line in held_lines:
        if "permission denied" in line.lower():
            # Extract run dir from hold reason
            m = re.search(r"run_(\d+)", line)
            if not m:
                continue
            rid = int(m.group(1))
            rs = state.runs.get(rid)
            if rs and rs.release_retries >= MAX_RELEASES:
                if not rs.notified:
                    send_telegram(f"🔴 run_{rid:02d} HELD_PERMANENT: {line.strip()[:100]}")
                    rs.notified = True
                continue
            if rs:
                rs.release_retries += 1

            # Fix permissions
            fix_cmd = (
                f"cd {state.remote_base} && "
                f"d=run_{rid:02d} && "
                f"rm -f $d/train.out $d/train.err $d/train.log && "
                f"touch $d/train.out $d/train.err $d/train.log && "
                f"chmod 666 $d/train.out $d/train.err $d/train.log"
            )
            r = ssh_cmd(fix_cmd)
            if r.returncode == 0:
                # Release
                ssh_cmd(f"condor_release {state.cluster}")
                actions.append(f"run_{rid:02d} released (permission fix)")
            else:
                actions.append(f"run_{rid:02d} permission fix failed")
    return actions


def handle_oom(state: CampaignState) -> list[str]:
    """Auto-upgrade GPU tier or halve batch size for OOM runs."""
    actions = []
    for rid, rs in state.runs.items():
        if rs.status != "OOM" or rs.oom_retries >= MAX_OOM_RETRIES:
            continue
        rs.oom_retries += 1

        # Try upgrading GPU tier first
        if rs.gpu_tier_idx < len(GPU_TIERS) - 1:
            rs.gpu_tier_idx += 1
            new_gpu = GPU_TIERS[rs.gpu_tier_idx]
            # Update config _gpu_min_mb (not a real field, but resubmit script uses it)
            actions.append(f"run_{rid:02d} OOM → upgrading GPU to {new_gpu}MB")
        else:
            # Already at max GPU, halve batch
            if rs.bs > MIN_BATCH:
                rs.bs = max(rs.bs // 2, MIN_BATCH)
                actions.append(f"run_{rid:02d} OOM → batch_size={rs.bs}")
            else:
                actions.append(f"run_{rid:02d} OOM_LIMIT (min batch reached)")
                send_telegram(f"🔴 run_{rid:02d} {rs.arch} OOM_LIMIT")
                rs.status = "OOM_LIMIT"
                rs.notified = True
                continue

        # Clean and resubmit single run
        gpu_mb = GPU_TIERS[rs.gpu_tier_idx]
        resubmit_cmd = (
            f"cd {state.remote_base} && "
            f"d=run_{rid:02d} && "
            f"rm -f $d/train.out $d/train.err $d/train.log $d/metrics.json $d/FAILED && "
            f"touch $d/train.out $d/train.err $d/train.log && "
            f"chmod 666 $d/train.out $d/train.err $d/train.log && "
            f'echo "universe = vanilla\\n'
            f'executable = /bin/bash\\n'
            f'request_gpus = 1\\n'
            f'request_memory = 16 GB\\n'
            f'should_transfer_files = NO\\n'
            f'getenv = False\\n'
            f'+AccountingGroup = \\"group_kareem.[用户]\\"\\n'
            f'requirements = (GPUs_GlobalMemoryMb >= {gpu_mb}) && (has_scratch365 == true)\\n'
            f'output = $d/train.out\\n'
            f'error = $d/train.err\\n'
            f'log = $d/train.log\\n'
            f'arguments = {state.remote_base}/run_train.sh --config {state.remote_base}/$d/train_config.json\\n'
            f'queue 1" > $d/rerun.submit && '
            f"condor_submit $d/rerun.submit"
        )
        r = ssh_cmd(resubmit_cmd, timeout=60)
        if r.returncode == 0:
            rs.status = "WAIT"  # back to waiting
            rs.notified = False
        else:
            actions.append(f"run_{rid:02d} resubmit failed: {r.stderr[:100]}")

    return actions


def progress_report(state: CampaignState) -> str:
    """Generate a concise progress report."""
    done = sum(1 for rs in state.runs.values() if rs.status == "DONE")
    running = sum(1 for rs in state.runs.values() if rs.status == "RUN")
    failed = sum(1 for rs in state.runs.values()
                 if rs.status in ("OOM", "OOM_LIMIT", "CRASH", "DIVERGED", "EARLY_STOP", "MAX_WALL", "ERR_LOSS", "ERR_UNKNOWN"))
    waiting = sum(1 for rs in state.runs.values() if rs.status in ("WAIT",))

    # Top 5 by R²
    top5 = sorted(
        [rs for rs in state.runs.values() if rs.r2 is not None],
        key=lambda x: -x.r2
    )[:5]

    lines = [
        f"📊 <b>{state.campaign}</b> | Cluster {state.cluster}",
        f"✅ {done} | 🏃 {running} | ❌ {failed} | ⏳ {waiting}",
        "",
    ]
    for i, rs in enumerate(top5, 1):
        marker = "🔥" if rs.r2 and rs.r2 > 0.68 else "✅"
        ep_str = f"ep{rs.ep}" if rs.ep < 9999 else "200"
        lines.append(f"{marker} #{i} run_{rs.run_id:02d} {rs.arch[:18]} {ep_str} R²={rs.r2:.4f}")

    return "\n".join(lines)


def all_finished(state: CampaignState) -> bool:
    """Check if all runs are in terminal states."""
    terminal = {"DONE", "OOM_LIMIT", "CRASH", "DIVERGED", "EARLY_STOP", "MAX_WALL", "ERR_LOSS", "ERR_UNKNOWN", "HELD_PERMANENT"}
    return all(rs.status in terminal for rs in state.runs.values())


def final_summary(state: CampaignState) -> str:
    """Final summary when all runs are finished."""
    done = [rs for rs in state.runs.values() if rs.status == "DONE"]
    failed = [rs for rs in state.runs.values() if rs.status not in ("DONE",)]

    # Best R²
    with_r2 = [rs for rs in done if rs.r2 is not None]
    best = max(with_r2, key=lambda x: x.r2) if with_r2 else None

    lines = [
        f"🏁 <b>{state.campaign} FINISHED</b>",
        f"Done: {len(done)}/{state.run_count}",
    ]
    if failed:
        lines.append(f"Failed: {len(failed)}")
        for rs in failed:
            lines.append(f"  run_{rs.run_id:02d} {rs.arch}: {rs.status}")

    if best:
        lines.append(f"\n🏆 Best: run_{best.run_id:02d} {best.arch} R²={best.r2:.4f} MAE={best.mae:.4f}" if best.mae else
                     f"\n🏆 Best: run_{best.run_id:02d} {best.arch} R²={best.r2:.4f}")

    # Full leaderboard
    lines.append("\n<b>Leaderboard:</b>")
    sorted_runs = sorted(with_r2, key=lambda x: -x.r2)
    for i, rs in enumerate(sorted_runs[:15], 1):
        marker = "🔥" if rs.r2 > 0.68 else ("✅" if rs.r2 > 0.5 else "  ")
        lines.append(f"{marker}{i:>2}. run_{rs.run_id:02d} {rs.arch[:18]} R²={rs.r2:.4f}")

    return "\n".join(lines)


# ── Main loop ───────────────────────────────────────────────────────────
def run_monitor(cluster: str, campaign: str, remote_base: str, run_count: int,
                max_polls: int = 200) -> int:
    """Main monitor loop."""
    setup_logging(cluster, campaign)
    state = CampaignState(
        cluster=cluster, campaign=campaign, remote_base=remote_base,
        run_count=run_count, start_time=time.time(),
        last_progress_time=time.time(),
    )

    send_telegram(
        f"🚀 Monitor started for <b>{campaign}</b>\n"
        f"Cluster: {cluster} | {run_count} runs"
    )
    logging.info("Monitor started for %s cluster=%s runs=%d", campaign, cluster, run_count)

    while state.poll_count < max_polls:
        state.poll_count += 1
        logging.info("Poll #%d", state.poll_count)

        # Poll
        data = poll_all(state)
        if data is None:
            logging.warning("Poll failed, sleeping")
            time.sleep(POLL_INTERVAL)
            continue

        # Update state
        actions = update_state(state, data)
        for a in actions:
            logging.info("Action: %s", a)

        # Handle held
        held = data.get("held", [])
        if held:
            h_actions = handle_held(state, held)
            for a in h_actions:
                logging.info("Held: %s", a)

        # Handle OOM
        oom_actions = handle_oom(state)
        for a in oom_actions:
            logging.info("OOM: %s", a)

        # Progress report
        now = time.time()
        if now - state.last_progress_time >= PROGRESS_INTERVAL:
            report = progress_report(state)
            send_telegram(report)
            state.last_progress_time = now
            logging.info("Progress sent")

        # Check done
        if all_finished(state):
            summary = final_summary(state)
            send_telegram(summary)
            logging.info("All finished")
            return 0

        time.sleep(POLL_INTERVAL)

    # Timeout
    send_telegram(f"⏰ Monitor timeout for {campaign} after {max_polls} polls\n" + progress_report(state))
    return 1


def setup_logging(cluster: str, campaign: str) -> None:
    log_dir = Path(__file__).parent.parent / "tmp"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"monitor_{cluster}_{campaign}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


# ── CLI ─────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CRC campaign submit + monitor")
    parser.add_argument("cluster", help="Condor cluster ID")
    parser.add_argument("campaign", help="Campaign name (e.g. tier_cd_200ep)")
    parser.add_argument("--run-count", type=int, default=45)
    parser.add_argument("--remote-base", default=f"{BASE}/campaigns")
    parser.add_argument("--poll-interval", type=int, default=POLL_INTERVAL)
    parser.add_argument("--max-polls", type=int, default=200)
    args = parser.parse_args(argv)

    remote_base = f"{args.remote_base}/{args.campaign}"
    return run_monitor(
        cluster=args.cluster,
        campaign=args.campaign,
        remote_base=remote_base,
        run_count=args.run_count,
        max_polls=args.max_polls,
    )


if __name__ == "__main__":
    raise SystemExit(main())
