#!/usr/bin/env python3
"""Allocate one CPU Colab session and arm a verified independent stop timer.

Run from an approved project directory; outputs live only in --run-dir.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

# systemd user services do not inherit the interactive shell's ~/.local/bin PATH.
CLI = ["./.local/bin/colab", "--auth", "oauth2"]


def call(cmd, timeout=45, cwd=None):
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, cwd=cwd)
    return {"command": cmd, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def record(path, data):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stop_owned(args, reason):
    run = Path(args.run_dir)
    log = run / "hardstop_events.jsonl"
    config = str(run / "colab_state.json")
    base = CLI + ["--config", config]
    record(log, {"at": now(), "event": "fire", "reason": reason})
    for remote in args.pull:
        # Each artifact is optional; an unresponsive download must never block stop.
        target = run / ("deadline_" + Path(remote).name)
        if target.exists():
            record(log, {"at": now(), "event": "pull_skipped_existing", "path": str(target)})
            continue
        try:
            result = call(base + ["download", "-s", args.session, remote, str(target)], timeout=20)
            record(log, {"at": now(), "event": "pull", "target": str(target), **result})
        except subprocess.TimeoutExpired:
            record(log, {"at": now(), "event": "pull_timeout", "remote": remote})
    # Always stop, including on a missing completion marker or a failed download.
    try:
        result = call(base + ["stop", "-s", args.session], timeout=45)
        record(log, {"at": now(), "event": "stop", **result})
    except subprocess.TimeoutExpired:
        record(log, {"at": now(), "event": "stop_timeout"})
    try:
        result = call(base + ["sessions"], timeout=30)
        record(log, {"at": now(), "event": "private_sessions_after", **result})
    except subprocess.TimeoutExpired:
        record(log, {"at": now(), "event": "verify_timeout"})


def start(args):
    run = Path(args.run_dir).resolve()
    run.mkdir(parents=True, exist_ok=True)
    log = run / "hardstop_events.jsonl"
    config = run / "colab_state.json"
    if config.exists() or log.exists() or (run / ".hardstop_owner").exists():
        raise RuntimeError("exclusive run directory required (existing config/log/owner)")
    with (run / ".hardstop_owner").open("x") as f:
        f.write(f"{args.session} {now()}\n")
    pre = time.time()  # cap starts BEFORE the allocation HTTP call
    record(log, {"at": now(), "event": "preallocate", "session": args.session, "cap_seconds": args.cap_seconds})
    new = call(CLI + ["--config", str(config), "new", "-s", args.session], timeout=90,
               cwd=args.approved_cwd)
    record(log, {"at": now(), "event": "new", **new})
    if new["returncode"] != 0:
        raise RuntimeError("allocation failed: inspect log, then reconcile sessions before any retry")
    remaining = int(pre + args.cap_seconds - args.margin_seconds - time.time())
    if remaining < 30:
        stop_owned(args, "allocation_consumed_safety_margin")
        raise RuntimeError("no safe timer margin")
    unit = "hardstop-" + args.session
    cmd = ["systemd-run", "--user", "--unit", unit, f"--on-active={remaining}s",
           sys.executable, str(Path(__file__).resolve()), "fire", "--session", args.session,
           "--run-dir", str(run)]
    for remote in args.pull:
        cmd += ["--pull", remote]
    armed = call(cmd, timeout=20)
    record(log, {"at": now(), "event": "arm", "delay_seconds": remaining, **armed})
    timer = call(["systemctl", "--user", "show", unit + ".timer", "-p", "ActiveState",
                  "-p", "NextElapseUSecMonotonic", "-p", "Triggers"], timeout=15)
    service = call(["systemctl", "--user", "show", unit + ".service", "-p", "ActiveState",
                    "-p", "ExecMainStartTimestamp"], timeout=15)
    record(log, {"at": now(), "event": "arm_verification", "timer": timer, "service": service})
    if armed["returncode"] or "ActiveState=active" not in timer["stdout"] or "NextElapseUSecMonotonic=" not in timer["stdout"] or "ActiveState=active" in service["stdout"]:
        stop_owned(args, "timer_not_verified")
        raise RuntimeError("timer not armed in the future: session stopped; inspect log")
    print(json.dumps({"session": args.session, "unit": unit + ".timer", "preallocate_utc": dt.datetime.fromtimestamp(pre, dt.timezone.utc).isoformat(), "cap_seconds": args.cap_seconds, "fire_in_seconds": remaining, "log": str(log)}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    s = sub.add_parser("start")
    s.add_argument("--approved-cwd", required=True)
    s.add_argument("--session", required=True)
    s.add_argument("--run-dir", required=True)
    s.add_argument("--cap-seconds", type=int, required=True)
    s.add_argument("--margin-seconds", type=int, default=45)
    s.add_argument("--pull", action="append", default=[])
    f = sub.add_parser("fire")
    f.add_argument("--session", required=True)
    f.add_argument("--run-dir", required=True)
    f.add_argument("--pull", action="append", default=[])
    args = p.parse_args()
    if args.action == "start":
        if args.cap_seconds <= args.margin_seconds + 60:
            p.error("cap must exceed margin by at least 60 seconds")
        start(args)
    else:
        stop_owned(args, "timer_deadline")


if __name__ == "__main__":
    main()
